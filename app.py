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

app = Flask(__name__)
CORS(app)

def get_client(api_key=None):
    """OpenAI 클라이언트 반환 (키 형식 검증 강화)"""
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
        if "카레" in lunch:
            return jsonify({
                "analysis": "점심에 향긋한 카레를 먹었으니, 저녁은 자극적이지 않고 부드러운 메뉴가 좋겠어요.",
                "recipes": [{"name": "애호박 계란국", "desc": "부드럽고 고소한 국물로 속을 편안하게", "time": "15", "diff": "쉬움", "ingredients": ["애호박", "계란"], "steps": ["애호박을 썰어 육수에 넣고 끓인다", "계란을 풀어 줄을 치듯 넣는다"], "tip": "새우젓으로 간을 하면 감칠맛이 살아나요"}],
                "message": "카레 향에 가득했던 아이의 입맛을 부드럽게 감싸줄 저녁이에요. 오늘 하루도 고군분투하신 당신, 국물 한 모금에 시름도 잊으시길 바라요. 수고하셨습니다! ❤️"
            })
        elif "비빔밥" in lunch:
            return jsonify({
                "analysis": "점심에 신선한 나물을 듬뿍 먹었네요! 저녁은 아이들이 좋아하는 든든한 고기 반찬 어떠세요?",
                "recipes": [{"name": "스팸 양파 볶음", "desc": "단짠의 정석, 밥도둑 메뉴", "time": "10", "diff": "매우 쉬움", "ingredients": ["스팸", "양파", "올리고당"], "steps": ["스팸과 양파를 깍둑썰기한다", "노릇하게 볶다가 올리고당 한 스푼!"], "tip": "검은깨를 솔솔 뿌리면 더 먹음직스러워요"}],
                "message": "비빔밥만큼이나 다채로운 하루를 보내셨을 당신께, 오늘은 조금 쉬운 요리를 선물하고 싶네요. 아이의 '맛있다'는 한마디에 오늘의 피로가 싹 가시길 응원합니다! ✨"
            })
        else:
            return jsonify({
                "analysis": "점심과 겹치지 않으면서 냉장고 재료를 활용한 최적의 레시피입니다.",
                "recipes": [{"name": "두부 스테이크", "desc": "겉바속촉, 건강하고 맛있는 한 끼", "time": "20", "diff": "보통", "ingredients": ["두부", "전분가루", "간장소스"], "steps": ["두부 물기를 제거하고 전분을 묻힌다", "팬에 구운 후 소스를 졸인다"], "tip": "어린잎 채소를 곁들이면 레스토랑 분위기가 나요"}],
                "message": "오늘도 훌륭하게 하루를 버텨내셨네요. 당신의 정성이 가득 담긴 식탁이 아이에게는 가장 큰 행복입니다. 편안하고 따뜻한 밤 되세요. 🍀"
            })

    prompt = f"""[상황] 오늘 아이 점심: {lunch}, 냉장고 재료: {ingredients}. 점심과 겹치지 않는 저녁 메뉴 2개와 레시피, 그리고 지친 부모님을 위한 맞춤형 응원 멘트를 JSON으로 작성해줘."""
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": "공감 능력이 뛰어난 요리 전문가입니다."}, {"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    return jsonify(json.loads(response.choices[0].message.content))

if __name__ == '__main__':
    print("--------------------------------------------------")
    print("Lunch-Check Dinner Bot Server Started!")
    print("Local URL: http://127.0.0.1:8080")
    print("--------------------------------------------------")
    app.run(debug=True, port=8080, host='127.0.0.1')
