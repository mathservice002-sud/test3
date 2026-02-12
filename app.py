import os
import json
import base64
import re
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from openai import OpenAI
from dotenv import load_dotenv
import google.generativeai as genai
from google.cloud import vision

# 환경 변수 로드
load_dotenv()

app = Flask(__name__)
CORS(app)

def get_client(api_key=None):
    """API 클라이언트 생성 (OpenAI sk- 또는 Google AIza- 지원)"""
    key = api_key if api_key and api_key.strip() else os.getenv("OPENAI_API_KEY")
    if not key or len(str(key)) < 5:
        return None
    
    key = str(key).strip()
    try:
        if key.startswith("sk-"):
            return {"type": "openai", "client": OpenAI(api_key=key)}
        elif key.startswith("AIza"):
            genai.configure(api_key=key)
            return {"type": "gemini", "client": genai.GenerativeModel('gemini-flash-latest')}
    except Exception as e:
        print(f"Client Init Error: {e}")
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

def extract_menu_from_image(ai_client, image_b64):
    """이미지 분석 (Google OCR + AI 정리)"""
    raw_text = extract_menu_google_vision(image_b64)
    
    # 1. 공통 텍스트 검증 로직
    if raw_text:
        non_menu_keywords = ["구하시오", "정답", "문제", "수학", "계산", "풀이"]
        menu_keywords = ["식단", "급식", "메뉴", "반찬", "밥", "우유", "칼로리", "영양", "초등학교", "중학교", "고등학교"]
        if any(k in raw_text for k in non_menu_keywords):
            return {"error": "급식표가 아닌 이미지가 감지되었습니다. (수학 문제 등으로 판독됨)"}
        if len(raw_text) > 20 and not any(k in raw_text for k in menu_keywords):
             return {"error": "급식표로 보기 어려운 이미지입니다. 식단표를 다시 확인해 주세요."}

    # 2. 프롬프트 구성
    valid_instruction = "이 이미지가 학교 급식표(식단표)가 맞는지 판단하고, 맞다면 날짜별 메뉴를 JSON으로 정리해줘. 급식표가 아니면 {\"error\": \"판독 불가\"} 응답해줘."
    prompt = f"{valid_instruction}\n텍스트: {raw_text}\n결과는 ```json ... ``` 블록에 넣어줘." if raw_text else f"{valid_instruction} 결과를 ```json ... ``` 블록에 넣어줘."

    # 3. 실제 AI 분석
    if not ai_client:
        return {"error": "실제 AI 버전을 사용하려면 유효한 API 키(OpenAI 또는 Google)가 필요합니다."}

    try:
        if ai_client["type"] == "openai":
            messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
            if not raw_text:
                messages[0]["content"].append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}})
            response = ai_client["client"].chat.completions.create(model="gpt-4o-mini", messages=messages, max_tokens=1000)
            raw = response.choices[0].message.content
        else: # Gemini
            if not raw_text:
                response = ai_client["client"].generate_content([prompt, {"mime_type": "image/jpeg", "data": base64.b64decode(image_b64)}])
            else:
                response = ai_client["client"].generate_content(prompt)
            raw = response.text

        match = re.search(r"```json\s*(.*?)\s*```", raw, re.DOTALL)
        result = json.loads(match.group(1)) if match else {}
        return result
    except Exception as e:
        print(f"AI API Error: {e}")
        return {"error": f"AI 분석 중 오류가 발생했습니다. 키를 확인해 주세요. ({str(e)})"}

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/config')
def get_config():
    api_key = os.getenv("OPENAI_API_KEY")
    # 키가 존재하면 AI 모드 활성화 (데모 배지 숨김)
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
    ai_client = get_client(data.get('apiKey'))
    
    if not ai_client:
        return jsonify({
            "analysis": "실제 AI 버전을 위해 올바른 API 키가 필요합니다.",
            "recipes": [],
            "message": "설정에서 유효한 OpenAI(sk-) 또는 Google(AIza) 키를 입력해 주세요."
        })

    # 실제 AI 추천 로직
    try:
        prompt = f"""[상황] 오늘 아이 점심: {lunch}, 냉장고 재료: {ingredients}.
[지침]
1. 입력된 냉장고 재료 중 하나라도 활용하여 점심 메뉴와 겹치지 않는 맛있는 저녁 메뉴 1개를 추천해줘.
2. 냉장고 재료 외에 만약 더 필요한 재료가 있다면 'more_ingredients' 항목에 따로 나열해줘.
3. 응답은 반드시 아래 JSON 형식을 지켜줘:
{{
  "analysis": "오늘의 식단 분석 및 조언",
  "recipes": [
    {{
      "name": "메뉴명",
      "desc": "선정이유 및 설명",
      "time": 소요시간(분),
      "diff": "난이도(쉬움/보통/어려움)",
      "ingredients": ["사용된 냉장고 재료"],
      "more_ingredients": ["추가로 필요한 재료"],
      "steps": ["레시피 단계1", "레시피 단계2", ...],
      "tip": "전문가의 팁"
    }}
  ],
  "message": "부모님을 위한 따뜻한 응원 멘트"
}}"""
        if ai_client["type"] == "openai":
            response = ai_client["client"].chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": "공감 능력이 뛰어난 요리 전문가입니다."}, {"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            res_content = response.choices[0].message.content
        else: # Gemini
            response = ai_client["client"].generate_content(prompt + " 응답은 반드시 순수 JSON 객체로 해줘.")
            res_content = response.text
            # Gemini는 가끔 ```json ... ```를 붙이므로 제거
            res_content = re.sub(r'```json\s*|\s*```', '', res_content, flags=re.DOTALL)

        return jsonify(json.loads(res_content))
    except Exception as e:
        print(f"AI Recommendation Error: {e}")
        return jsonify({
            "analysis": "AI 추천 중 오류가 발생했습니다.",
            "recipes": [],
            "message": f"API 오류: {str(e)}"
        })

if __name__ == '__main__':
    print("--------------------------------------------------")
    print("Lunch-Check Dinner Bot Server Started!")
    print("Local URL: http://127.0.0.1:8080")
    print("--------------------------------------------------")
    app.run(debug=True, port=8080, host='127.0.0.1')
