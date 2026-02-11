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

    # OpenAI 클라이언트가 없으면(데모 모드) 기본 데이터 반환 (오늘부터 7일치)
    if not openai_client:
        from datetime import datetime, timedelta
        mock_data = {}
        days_ko = ["월", "화", "수", "목", "금", "토", "일"]
        for i in range(7):
            date = datetime.now() + timedelta(days=i)
            date_str = date.strftime("%m/%d") + f"({days_ko[date.weekday()]})"
            # 샘플 데이터 순환 배치
            samples = [
                "카레라이스, 미역국, 계란말이",
                "비빔밥, 된장찌개, 떡갈비",
                "돈가스, 우동, 양배추샐러드",
                "제육덮밥, 콩나물국, 감자채볶음",
                "생선구이, 육개장, 시금치나물",
                "볶음밥, 짬뽕국, 단무지무침",
                "불고기덮밥, 만두국, 김치"
            ]
            mock_data[date_str] = samples[i % len(samples)]
        return mock_data

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
        import random
        # 데모 모드: 입력된 재료에 맞춰 지능적이고 다양한 가짜 데이터 반환
        
        # 프론트엔드에서 누적 클릭 횟수를 보내준다고 가정 (없으면 기본 0)
        click_count = data.get('clickCount', 0)
        
        has_ingredients = bool(ingredients.strip())
        ing_list = [i.strip() for i in ingredients.split(',') if i.strip()]
        
        # --- 변수 제어: 3번까지만 다른 메뉴를 보여줌 ---
        if click_count >= 3:
            return jsonify({
                "analysis": "현재 준비된 모든 추천을 확인하셨습니다!",
                "recipes": [],
                "message": "데모 데이터베이스에 더 이상의 추천 메뉴가 없습니다. 실제 서비스에서는 무한한 조합이 가능해요! 😉"
            })

        # --- 고밀도 추천 조합 (클래식 매칭) ---
        # 1. 고등어 + 무
        if "고등어" in ingredients and "무" in ingredients:
            options = [
                {
                    "analysis": "고등어와 무의 찰떡궁합! 칼칼한 조림 어떠세요?",
                    "recipes": [{"name": "매콤 고등어 무조림", "desc": "입맛 돋우는 밥도둑", "time": "30", "ingredients": ["고등어", "무", "고춧가루"], "steps": ["무를 깔고 고등어를 올린 뒤 졸인다"], "tip": "무가 투명해질 때까지 푹 익히세요"}],
                    "message": "밥 두 그릇 예약! 시원한 무와 고속한 고등어의 만남입니다. 🐟"
                },
                {
                    "analysis": "오늘처럼 쌀쌀한 날에는 시원한 생선 지리탕이 최고죠.",
                    "recipes": [{"name": "맑은 고등어 무국", "desc": "비린내 없이 시원한 국물 요리", "time": "20", "ingredients": ["고등어", "무", "쑥갓"], "steps": ["무로 육수를 내고 싱싱한 고등어를 넣는다"], "tip": "다진 마늘을 충분히 넣어 잡내를 잡으세요"}],
                    "message": "아이들도 좋아하는 시원담백한 국물이에요. 🍲"
                }
            ]
            return jsonify(options[click_count % len(options)])
        
        # 2. 소고기 + 떡
        elif "소고기" in ingredients and ("떡" in ingredients or "가래떡" in ingredients):
            options = [
                {
                    "analysis": "단짠단짠 궁중 떡볶이로 아이들 입맛을 사로잡으세요!",
                    "recipes": [{"name": "궁중 떡볶이", "desc": "맵지 않은 고급 떡볶이", "time": "20", "ingredients": ["소고기", "떡", "간장"], "steps": ["고기와 떡을 달콤한 간장 양념에 볶는다"], "tip": "참기름 한 방울로 마무리!"}],
                    "message": "쫀득한 식감에 대화도 쫀득해지는 저녁 되세요! 🍖"
                },
                {
                    "analysis": "든든한 소고기 떡국으로 따뜻한 한 끼 추천합니다.",
                    "recipes": [{"name": "진한 소고기 떡국", "desc": "진한 사골 육수맛이 나는 국물 요리", "time": "15", "ingredients": ["소고기", "떡", "계란"], "steps": ["소고기를 볶다가 물을 붓고 떡을 넣어 끓인다"], "tip": "계란 지단을 올리면 더 예뻐요"}],
                    "message": "사계절 언제 먹어도 든든한 보양식이죠! 🍲"
                }
            ]
            return jsonify(options[click_count % len(options)])

        # --- 3. 스마트 동적 생성 (어떤 재료든 대응) ---
        elif has_ingredients:
            main_item = ing_list[0]
            sub_item = ing_list[1] if len(ing_list) > 1 else "야채"
            
            variants = [
                {"style": "볶음", "emoji": "🔥", "msg": "불맛 가득한 저녁!"},
                {"style": "전", "emoji": "🍳", "msg": "고소한 냄새가 진동할 거예요."},
                {"style": "비빔밥", "emoji": "🥗", "msg": "깔끔하게 비벼먹는 한 끼!"}
            ]
            
            v = variants[click_count % len(variants)]
            return jsonify({
                "analysis": f"준비하신 {main_item}와(과) {sub_item}의 조화를 살린 {v['style']} 요리입니다.",
                "recipes": [{
                    "name": f"스페셜 {main_item} {sub_item} {v['style']}",
                    "desc": f"재료 본연의 맛을 극대화한 {v['style']} 세트",
                    "time": "15",
                    "ingredients": ing_list + ["기본 양념"],
                    "steps": [f"{main_item}와 {sub_item}을 손질한다", "적당한 온도의 팬에 볶거나 부친다"],
                    "tip": "재료가 타지 않게 주의하세요!"
                }],
                "message": f"{v['msg']} 맛있게 드세요! {v['emoji']}"
            })

        # --- 4. 기본 폴백 ---
        else:
            return jsonify({
                "analysis": "오늘의 추천 메뉴입니다.",
                "recipes": [{"name": "영양 계란찜", "desc": "부드러운 식감의 국민 반찬", "time": "10", "ingredients": ["계란", "파"], "steps": ["계란을 풀고 찜기에 찐다"], "tip": "우유를 조금 넣으면 더 부드러워요"}],
                "message": "간편하지만 든든한 한 끼 되세요! 🐣"
            })

    # 실제 AI 추천 로직
    prompt = f"""[상황] 오늘 아이 점심: {lunch}, 냉장고 재료: {ingredients}. 점심과 겹치지 않는 저녁 메뉴 2개와 레시피, 그리고 지친 부모님을 위한 맞춤형 응원 멘트를 JSON으로 작성해줘."""
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": "공감 능력이 뛰어난 요리 전문가입니다."}, {"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    return jsonify(json.loads(response.choices[0].message.content))

# Vercel을 위한 핸들러
app = app
