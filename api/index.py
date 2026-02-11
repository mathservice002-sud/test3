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
    """OpenAI 클라이언트 반환 (키 형식 검증)"""
    key = api_key if api_key and api_key.strip() else os.getenv("OPENAI_API_KEY")
    if not key or not str(key).startswith("sk-") or key == "sk-your-api-key-here":
        return None
    try:
        return OpenAI(api_key=key)
    except:
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
    
    if raw_text:
        prompt = f"아래 텍스트에서 날짜별 점심 메뉴를 찾아 JSON 형식으로 정리해줘.\n날짜: MM/DD(요일)\n텍스트: {raw_text}\n결과는 ```json ... ``` 블록에 넣어줘."
    else:
        prompt = "이미지의 급식표를 분석해서 날짜별 메뉴를 JSON으로 정리해줘. 결과는 ```json ... ``` 블록에 넣어줘."

    messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
    if not raw_text:
        messages[0]["content"].append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}})

    # OpenAI 클라이언트가 없으면(데모 모드) 기본 데이터 반환
    if not openai_client:
        return {
            "02/11(수)": "카레라이스, 미역국, 계란말이",
            "02/12(목)": "비빔밥, 된장찌개, 떡갈비",
            "02/13(금)": "돈가스, 우동, 양배추샐러드"
        }

    response = openai_client.chat.completions.create(model="gpt-4o-mini", messages=messages, max_tokens=1000)
    raw = response.choices[0].message.content
    match = re.search(r"```json\s*(.*?)\s*```", raw, re.DOTALL)
    return json.loads(match.group(1)) if match else {}

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/config')
def get_config():
    api_key = os.getenv("OPENAI_API_KEY")
    has_key = api_key is not None and str(api_key).startswith("sk-")
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
        # 데모 모드: 입력된 재료에 맞춰 조금 더 지능적인 가짜 데이터 반환
        if "감자" in ingredients:
            return jsonify({
                "analysis": "냉장고에 있는 감자를 활용해 점심의 돈가스와 잘 어울리는 고소한 메뉴를 골라봤어요.",
                "recipes": [{"name": "쫀득 감자전", "desc": "밀가루 없이 감자만으로 만드는 건강 간식", "time": "20", "diff": "보통", "ingredients": ["감자", "소금", "식용유"], "steps": ["감자를 강판에 갈아 물기를 뺀다", "가라앉은 전분과 섞어 팬에 굽는다"], "tip": "겉은 바삭하게 속은 쫀득하게 구워주세요"}],
                "message": "감자의 포근함처럼 아이를 감싸안아주는 저녁 시간 되세요. 감자 깎느라 고생하셨을 손길에 따뜻한 응원을 보냅니다! 🥔"
            })
        elif "배추" in ingredients:
            return jsonify({
                "analysis": "신선한 배추로 시원하고 달큰한 국물을 만들어 점심의 기름진 맛을 씻어내요.",
                "recipes": [{"name": "달큰한 배추 된장국", "desc": "속이 뻥 뚫리는 시원한 맛", "time": "15", "diff": "쉬움", "ingredients": ["배추", "된장", "멸치육수"], "steps": ["육수에 된장을 풀고 배추를 넣는다", "배추가 부드러워질 때까지 푹 끓인다"], "tip": "청양고추 반 개를 넣으면 어른들도 좋아해요"}],
                "message": "시원한 국물 한 모금에 오늘 쌓인 피로도 훌훌 털어버리세요. 따뜻한 집밥만큼 좋은 보약은 없답니다. 오늘도 수고 많으셨어요! 🥬"
            })
        elif "스팸" in ingredients or "햄" in ingredients:
            return jsonify({
                "analysis": "아이들이 제일 좋아하는 스팸으로 뚝딱! 점심과는 또 다른 짭짤한 매력을 느껴보세요.",
                "recipes": [{"name": "스팸 양파 볶음", "desc": "실패 없는 밥도둑 반찬", "time": "10", "diff": "매우 쉬움", "ingredients": ["스팸", "양파", "올리고당"], "steps": ["스팸과 양파를 구워 볶는다", "마지막에 올리고당을 살짝 뿌린다"], "tip": "양파를 충분히 볶아야 달콤해요"}],
                "message": "짧은 조리 시간만큼 아이와 더 많이 눈을 맞추는 저녁 되시길 바라요. 빠르고 맛있는 식탁, 당신의 지혜가 빛나는 순간입니다! ✨"
            })
        elif "카레" in lunch:
            return jsonify({
                "analysis": "점심에 향긋한 카레를 먹었으니, 저녁은 자극적이지 않고 부드러운 메뉴가 좋겠어요.",
                "recipes": [{"name": "애호박 계란국", "desc": "부드럽고 고소한 국물로 속을 편안하게", "time": "15", "diff": "쉬움", "ingredients": ["애호박", "계란"], "steps": ["애호박을 썰어 육수에 넣고 끓인다", "계란을 풀어 줄을 치듯 넣는다"], "tip": "새우젓으로 간을 하면 감칠맛이 살아나죠"}],
                "message": "카레 향에 가득했던 아이의 입맛을 부드럽게 감싸줄 저녁이에요. 오늘 하루도 고군분투하신 당신, 국물 한 모금에 시름도 잊으시길 바라요. ❤️"
            })
        else:
            return jsonify({
                "analysis": "점심과 겹치지 않으면서 냉장고 재료를 활용할 수 있는 추천 메뉴입니다.",
                "recipes": [{"name": "계란말이 샌드위치", "desc": "반찬으로도 간식으로도 최고", "time": "15", "diff": "보통", "ingredients": ["계란", "식빵", "마요네즈"], "steps": ["두툼하게 계란말이를 만든다", "빵 사이에 마요네즈와 함께 넣는다"], "tip": "설탕을 살짝 뿌리면 훨씬 맛있어요"}],
                "message": "무엇을 만들어도 당신의 사랑이 담겨있다면 최고의 만찬입니다. 고단한 하루 끝, 평안한 저녁 식사 되세요. 🍀"
            })

    # 실제 AI 추천 로직
    prompt = f"""[상황]
오늘 아이 점심: {lunch}
냉장고 재료: {ingredients}

[작업]
1. 점심과 주재료/조리방식이 겹치지 않는 저녁 메뉴 2개를 추천하세요.
2. 각 메뉴별 상세 레시피와 팁을 포함하세요.
3. 지친 부모님을 위한 따뜻한 응원 멘트를 작성하세요. 
   - 추천한 메뉴의 특성에 맞춰 (예: "매콤한 맛으로 스트레스 풀기", "따뜻한 국물로 몸 녹이기" 등) 아주 구체적이고 다정한 멘트여야 합니다.

[형식 - JSON]
{{
  "analysis": "점심 메뉴 분석",
  "recipes": [
    {{
      "name": "요리명",
      "desc": "설명",
      "time": "분",
      "diff": "난이도",
      "ingredients": ["재료"],
      "steps": ["단계"],
      "tip": "팁"
    }}
  ],
  "message": "메뉴 맞춤형 다정한 응원 멘트"
}}
반드시 JSON 형식으로만 응답하세요."""

    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "당신은 육아에 지친 부모님을 위로하는 공감 능력이 뛰어난 요리 전문가입니다."},
            {"role": "user", "content": prompt}
        ],
        response_format={"type": "json_object"}
    )
    return jsonify(json.loads(response.choices[0].message.content))

# Vercel을 위한 핸들러
app = app
