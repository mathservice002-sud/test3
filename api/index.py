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
        
        has_ingredients = bool(ingredients.strip())
        ing_list = [i.strip() for i in ingredients.split(',') if i.strip()]
        
        # --- 1. 고품질 전용 템플릿 (특정 키워드 매칭) ---
        
        # 고등어 + 무
        if "고등어" in ingredients and "무" in ingredients:
            return jsonify({
                "analysis": "고등어와 무의 찰떡궁합! 비린내 없이 시원하고 칼칼한 조림 어떠세요?",
                "recipes": [{"name": "고등어 무조림", "desc": "양념이 잘 밴 무가 더 맛있는 밥도둑", "time": "30", "diff": "보통", "ingredients": ["고등어", "무", "간장", "고춧가루", "파"], "steps": ["무를 깔고 토막 낸 고등어를 올린다", "양념장을 붓고 국물이 자작해질 때까지 졸인다"], "tip": "무를 먼저 살짝 익힌 후 고등어를 넣으면 더 맛있어요"}],
                "message": "시원한 무조림 한 점에 오늘 하루의 스트레스도 싹 날려버리세요. 정말 훌륭한 메뉴 선택입니다! 🐟"
            })
        
        # 소고기 + 떡
        elif "소고기" in ingredients and ("떡" in ingredients or "가래떡" in ingredients):
            return jsonify({
                "analysis": "냉장고에 있는 소고기와 가래떡으로 아이들이 정말 좋아하는 단짠단짠 궁중 떡볶이를 만들 수 있어요.",
                "recipes": [{"name": "궁중 떡볶이", "desc": "맵지 않아 아이들도 잘 먹는 고급스러운 떡볶이", "time": "20", "diff": "보통", "ingredients": ["가래떡", "소고기(불고기용)", "양파", "표고버섯", "간장소스"], "steps": ["떡은 말랑하게 불리고 고기는 밑간을 한다", "채소와 함께 볶다가 간장 소스로 간을 맞춘다"], "tip": "마지막에 참기름 한 방울과 통깨를 뿌리면 고소함이 폭발해요"}],
                "message": "영양 가득한 소고기와 쫀득한 떡의 조화처럼, 오늘 저녁 가족들과의 시간도 쫀득하고 행복하시길 바라요. 요리하느라 고생 많으셨습니다! 🍖"
            })

        # --- 2. 스마트 동적 생성 (어떤 재료든 대응) ---
        
        elif has_ingredients:
            # 첫 번째 재료를 메인으로 사용하여 그럴싸한 레시피 생성
            main_item = ing_list[0]
            sub_items = ", ".join(ing_list[1:3]) if len(ing_list) > 1 else "각종 채소"
            
            # 요리 스타일 랜덤 결정
            style = random.choice(["볶음", "조림", "전", "덮밥"])
            
            return jsonify({
                "analysis": f"준비된 {main_item}와(과) {sub_items} 등을 활용해 맛있는 {main_item} {style}을(를) 만들어보세요!",
                "recipes": [{
                    "name": f"든든한 {main_item} {style}",
                    "desc": f"{main_item} 본연의 맛을 살린 영양 가득한 한 끼 식사",
                    "time": "15",
                    "diff": "보통",
                    "ingredients": ing_list + ["간장", "올리고당", "참기름"],
                    "steps": [
                        f"준비된 {main_item}을(를) 먹기 좋은 크기로 손질합니다.",
                        f"팬에 기름을 두르고 {main_item}와(과) 나머지 채소들을 함께 넣고 익힙니다.",
                        "기호에 맞게 양념을 넣어 간을 맞춘 뒤 마무리합니다."
                    ],
                    "tip": f"{main_item}의 식감을 살리려면 너무 오래 익히지 않는 것이 포인트예요!"
                }],
                "message": f"입력하신 {main_item}에 딱 맞춘 맞춤형 추천입니다. 실제 AI 버전은 더 정교한 조리법을 제안해 드려요! ✨"
            })

        # --- 3. 기본 폴백 (재료가 없을 때) ---
        else:
            return jsonify({
                "analysis": "오늘 무엇을 할지 고민될 때는 누구나 좋아하는 든든한 한 끼를 추천드려요.",
                "recipes": [{"name": "영양 가득 계란말이", "desc": "채소를 듬뿍 넣어 영양과 색감을 모두 잡은 반찬", "time": "15", "diff": "보통", "ingredients": ["계란", "당근", "파", "소금"], "steps": ["계란을 풀고 잘게 썬 채소를 섞는다", "팬에 조금씩 부어가며 돌돌 말아 익힙니다"], "tip": "약불에서 천천히 말아야 모양이 예쁘게 잡혀요"}],
                "message": "무엇을 만들어도 당신의 정성이 최고의 조미료입니다. 오늘 밤은 가족과 함께 오순도순 따뜻한 식탁 되시길 바라요. 🍀"
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
