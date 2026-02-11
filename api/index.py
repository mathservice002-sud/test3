import os
import json
import base64
import re
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from openai import OpenAI
from dotenv import load_dotenv
from google.cloud import vision

# 환경 변수 로드
load_dotenv()

# Vercel 환경에서 templates 폴더 위치를 정확히 지정
template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates'))
app = Flask(__name__, template_folder=template_dir)
CORS(app)

def get_client(api_key=None):
    """API 클라이언트 생성 (실제 AI 모드 전용)"""
    key = api_key if api_key and api_key.strip() else os.getenv("OPENAI_API_KEY")
    if key and len(str(key)) > 5:
        try:
            return OpenAI(api_key=str(key).strip())
        except Exception as e:
            print(f"Client Init Error: {e}")
            return None
    return None

def extract_menu_google_vision(image_b64):
    """Google Cloud Vision OCR (구글 프로젝트 ID 기반)"""
    try:
        content = base64.b64decode(image_b64)
        image = vision.Image(content=content)
        client = vision.ImageAnnotatorClient()
        response = client.text_detection(image=image)
        texts = response.text_annotations
        return texts[0].description if texts else ""
    except Exception as e:
        print(f"Google Vision Error: {e}")
        return None

def extract_menu_from_image(openai_client, image_b64):
    """이미지 분석 (Google OCR + AI 정리)"""
    raw_text = extract_menu_google_vision(image_b64)
    
    # 1. 공통 텍스트 검증 로직 (전처리)
    if raw_text:
        non_menu_keywords = ["구하시오", "정답", "문제", "수학", "계산", "풀이"]
        menu_keywords = ["식단", "급식", "메뉴", "반찬", "밥", "우유", "칼로리", "영양", "초등학교", "중학교", "고등학교"]
        
        # 부정 키워드 발견 시 즉시 차단
        if any(k in raw_text for k in non_menu_keywords):
            return {"error": "급식표가 아닌 이미지가 감지되었습니다. (수학 문제 등으로 판독됨)"}
        
        # 긍정 키워드가 너무 없으면 의심 (텍스트가 일정 이상일 때만 수행)
        if len(raw_text) > 20 and not any(k in raw_text for k in menu_keywords):
             return {"error": "급식표로 보기 어려운 이미지입니다. 식단표를 다시 확인해 주세요."}

    # 2. 프롬프트 구성 (AI용 지시사항 강화)
    valid_instruction = "먼저 이 이미지가 학교 급식표(식단표)가 맞는지 판단해줘. 만약 급식표가 아니거나 음식 관련 내용이 없다면 반드시 {\"error\": \"이미지 판독 불가 메시지\"} 형식으로만 응답해줘. 급식표가 맞다면 날짜별 메뉴를 JSON으로 정리해줘."
    if raw_text:
        prompt = f"{valid_instruction}\n날짜: MM/DD(요일)\n텍스트: {raw_text}\n결과는 ```json ... ``` 블록에 넣어줘."
    else:
        prompt = f"{valid_instruction} 결과를 ```json ... ``` 블록에 넣어줘."

    messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
    if not raw_text:
        messages[0]["content"].append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}})

    # 3. 실제 AI 분석 (GPT-4o-mini)
    if not openai_client:
        return {"error": "실제 AI 버전을 사용하려면 유효한 OpenAI API 키가 필요합니다."}

    try:
        response = openai_client.chat.completions.create(model="gpt-4o-mini", messages=messages, max_tokens=1000)
        raw = response.choices[0].message.content
        match = re.search(r"```json\s*(.*?)\s*```", raw, re.DOTALL)
        result = json.loads(match.group(1)) if match else {}
        
        if "error" in result:
            return result
        return result
    except Exception as e:
        print(f"OpenAI API Error: {e}")
        return {"error": f"AI 분석 중 오류가 발생했습니다. 키를 확인해 주세요. ({str(e)})"}

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/config')
def get_config():
    api_key = os.getenv("OPENAI_API_KEY")
    # 키가 존재하면 AI 모드 활성화
    has_key = api_key is not None and len(str(api_key)) > 5
    return jsonify({"hasServerKey": has_key, "demoMode": not has_key})

@app.route('/api/analyze', methods=['POST'])
def api_analyze():
    data = request.json
    api_key = data.get('apiKey')
    image_b64 = data.get('image').split(',')[-1] if ',' in data.get('image', '') else data.get('image')
    openai_client = get_client(api_key)
    return jsonify(extract_menu_from_image(openai_client, image_b64))

@app.route('/api/recommend', methods=['POST'])
def api_recommend():
    data = request.json
    lunch = data.get('lunch', '')
    ingredients = data.get('ingredients', '')
    openai_client = get_client(data.get('apiKey'))
    
    if not openai_client:
        return jsonify({
            "analysis": "실제 AI 버전을 위해 API 키가 필요합니다.",
            "recipes": [],
            "message": "설정에서 유효한 OpenAI API 키를 입력해 주세요."
        })

    # 실제 AI 추천 로직
    try:
        prompt = f"""[상황] 오늘 아이 점심: {lunch}, 냉장고 재료: {ingredients}. 점심과 겹치지 않는 저녁 메뉴 1개와 레시피, 그리고 지친 부모님을 위한 맞춤형 응원 멘트를 JSON으로 작성해줘."""
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "공감 능력이 뛰어난 요리 전문가입니다."}, {"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        return jsonify(json.loads(response.choices[0].message.content))
    except Exception as e:
        print(f"OpenAI Recommendation Error: {e}")
        return jsonify({
            "analysis": "AI 추천 서버와 연결할 수 없습니다.",
            "recipes": [],
            "message": f"API 키 오류가 발생했습니다: {str(e)}"
        })

# Vercel을 위한 핸들러
app = app
