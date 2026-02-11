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
        # 데모 모드 전용 고정 레시피 라이브러리 (실제 존재하는 메뉴들)
        RECIPE_LIBRARY = [
            {
                "name": "고등어 무조림",
                "ingredients": ["고등어", "무", "간장", "고춧가루", "파"],
                "analysis": "고등어와 무의 환상적인 조합! 비린내 없이 칼칼한 저녁 어떠세요?",
                "desc": "양념이 잘 밴 무가 일품인 밥도둑 조림",
                "time": "30", "diff": "보통",
                "steps": ["무를 깔고 고등어를 올린 뒤 양념장 투하", "중불에서 국물이 자작할 때까지 졸인다"],
                "tip": "무를 먼저 살짝 익히면 더 맛있어요",
                "message": "시원한 무와 고소한 고등어, 오늘 저녁 최고의 선택입니다! 🐟"
            },
            {
                "name": "바삭 고등어 구이",
                "ingredients": ["고등어", "굵은소금", "식초/레몬"],
                "analysis": "겉은 바삭하고 속은 촉촉한 고등어 구이로 영양을 보충해보세요.",
                "desc": "집에서도 에어프라이어로 간단하게 만드는 건강식",
                "time": "15", "diff": "쉬움",
                "steps": ["고등어에 소금 밑간을 한다", "팬이나 에어프라이어에 노릇하게 굽는다"],
                "tip": "밀가루를 살짝 묻히면 더 바삭해요",
                "message": "고소한 냄새가 온 집안에 솔솔~ 맛있는 식사 되세요! ✨"
            },
            {
                "name": "소고기 뭇국",
                "ingredients": ["소고기", "무", "참기름", "국간장"],
                "analysis": "깊고 시원한 국물 맛! 아이들도 잘 먹는 맑은 소고기 뭇국입니다.",
                "desc": "언제 먹어도 속이 편안하고 든든한 한국인의 소울푸드",
                "time": "25", "diff": "보통",
                "steps": ["참기름에 소고기와 무를 볶는다", "물을 붓고 거품을 걷어내며 푹 끓인다"],
                "tip": "무를 얇게 썰어야 국물이 빨리 우러나요",
                "message": "따뜻한 국물 한 그릇에 오늘 하루의 고단함도 녹아내리길.. 🍲"
            },
            {
                "name": "궁중 떡볶이",
                "ingredients": ["떡", "소고기", "파프리카", "간장", "양파"],
                "analysis": "아이들이 좋아하는 달콤 짭짤한 궁중 떡볶이입니다.",
                "desc": "맵지 않아 온 가족이 함께 즐기는 품격 있는 간식 겸 식사",
                "time": "20", "diff": "보통",
                "steps": ["떡은 불리고 고기와 채소를 손질한다", "간장 베이스 소스로 달달하게 볶아낸다"],
                "tip": "마지막에 참기름과 깨를 듬뿍 뿌려주세요",
                "message": "쫀득한 떡과 소고기의 환상 조화! 행복한 저녁 되세요! 🍖"
            },
            {
                "name": "두부 계란 부침",
                "ingredients": ["두부", "계란", "소금", "파"],
                "analysis": "냉장고에 항상 있는 두부와 계란으로 만드는 고소한 반찬입니다.",
                "desc": "보들보들한 식감으로 아이들 반찬 걱정 끝!",
                "time": "10", "diff": "매우 쉬움",
                "steps": ["두부 물기를 빼고 계란물을 입힌다", "기름 두른 팬에 앞뒤로 노릇하게 부친다"],
                "tip": "쑥갓이나 홍고추를 올리면 보기에도 예뻐요",
                "message": "간단하지만 영양 만점, 당신의 정성이 듬뿍 담겼네요! 🍳"
            },
            {
                "name": "포슬포슬 감자채 볶음",
                "ingredients": ["감자", "양파", "햄", "파프리카"],
                "analysis": "아삭하고 고소한 감자채 볶음으로 밥상을 채워보세요.",
                "desc": "남녀노소 누구나 좋아하는 국민 밑반찬",
                "time": "15", "diff": "쉬움",
                "steps": ["감자를 채 썰어 전분기를 뺀 뒤 볶는다", "양파와 햄을 넣고 소금으로 간한다"],
                "tip": "감자를 먼저 살짝 데치면 볶을 때 부서지지 않아요",
                "message": "아삭아삭 씹히는 맛이 예술! 오늘도 고생 많으셨습니다! 🥔"
            },
            {
                "name": "부드러운 계란찜",
                "ingredients": ["계란", "파", "당근", "우유"],
                "analysis": "속이 편안해지는 따뜻하고 부드러운 계란찜입니다.",
                "desc": "아이들 식사에 빠질 수 없는 단골 메뉴",
                "time": "10", "diff": "매우 쉬움",
                "steps": ["계란을 잘 풀고 한 번 체에 거른다", "중불에서 김이 오를 때까지 쪄낸다"],
                "tip": "우유를 조금 넣으면 훨씬 고소하고 부드러워요",
                "message": "부들부들한 식감처럼 기분 좋은 저녁 되세요! 💛"
            },
            {
                "name": "두부 김치 덮밥",
                "ingredients": ["두부", "김치", "돼지고기", "양파"],
                "analysis": "매콤한 김치와 담백한 두부의 조화! 입맛 돋우는 덮밥입니다.",
                "desc": "별다른 반찬 없이 한 그릇으로 뚝딱 해결하는 식사",
                "time": "20", "diff": "보통",
                "steps": ["김치와 고기를 볶다가 두부를 깍둑썰어 넣는다", "밥 위에 듬뿍 올려 비벼 먹는다"],
                "tip": "설탕을 반 스푼 넣으면 김치의 신맛을 잡을 수 있어요",
                "message": "매콤 담백한 조화가 일품! 든든하게 드시고 힘내세요! 🔥"
            },
            {
                "name": "알록달록 파프리카 볶음",
                "ingredients": ["파프리카", "소시지", "양파", "굴소스"],
                "analysis": "색감이 예뻐 아이들도 흥미를 갖는 달콤한 채소 볶음입니다.",
                "desc": "파프리카의 아삭함과 소시지의 짭짤함이 만난 반찬",
                "time": "10", "diff": "쉬움",
                "steps": ["파프리카와 소시지를 한입 크기로 썬다", "강한 불에 빠르게 볶아 아삭함을 살린다"],
                "tip": "마지막에 올리고당을 살짝 넣으면 윤기가 나요",
                "message": "비주얼도 맛도 만점! 즐거운 식사 시간 되세요! 🌈"
            },
            {
                "name": "아삭 무생채",
                "ingredients": ["무", "고춧가루", "식초", "설탕"],
                "analysis": "입맛 없을 때 최고! 새콤달콤 아삭한 무생채입니다.",
                "desc": "갓 지은 밥에 슥슥 비벼 먹기 좋은 밑반찬",
                "time": "10", "diff": "매우 쉬움",
                "steps": ["무를 채 썰어 소금에 살짝 절인다", "양념을 넣고 조물조물 버무린다"],
                "tip": "기호에 따라 미나리를 넣으면 향긋해요",
                "message": "상큼한 무생채로 식탁에 활력을 불어넣어 보세요! 🥬"
            }
        ]
        
        click_count = data.get('clickCount', 0)
        # 콤마, 공백, 슬래시 등으로 구분된 재료 리스트 추출
        ing_list = [i.strip() for i in ingredients.replace(',', ' ').replace('/', ' ').split() if i.strip()]
        
        # 1. 매칭 알고리즘: 사용자가 입력한 재료가 포함된 레시피 찾기
        matches = []
        if ing_list:
            for r in RECIPE_LIBRARY:
                # 더 엄격한 매칭: 글자 수가 너무 적으면(1자) 완전 일치만 허용, 길면 부분 일치 허용
                score = 0
                for user_ing in ing_list:
                    for recipe_ing in r['ingredients']:
                        if len(user_ing) == 1:
                            if user_ing == recipe_ing: # 1글자면 완전 일치
                                score += 2
                        else:
                            if user_ing in recipe_ing: # 2글자 이상이면 부분 일치 허용
                                score += 2
                    
                    # 제목 매칭 가산점
                    if user_ing in r['name']:
                        score += 1

                if score > 0:
                    matches.append((score, r))
            
            # 매칭된 결과 점수순 정렬
            matches.sort(key=lambda x: x[0], reverse=True)
            results = [m[1] for m in matches]
        else:
            # 입력 재료가 아예 없으면 기본 추천 (전체 라이브러리)
            results = RECIPE_LIBRARY.copy()
            random.shuffle(results)
        
        # 2. 결과 처리
        if not results:
            return jsonify({
                "analysis": f"입력하신 재료({', '.join(ing_list)})와 매칭되는 고정 레시피가 데모 데이터에 없습니다.",
                "recipes": [],
                "message": "데모 모드에서는 '고등어', '무', '소고기', '떡', '두부', '계란', '감자', '파프리카' 위주로 준비되어 있어요. 실제 버전은 모든 재료를 완벽 분석합니다! 🍀"
            })
            
        if click_count >= len(results):
            return jsonify({
                "analysis": "현재 조합으로 가능한 모든 실존 레시피를 확인하셨습니다!",
                "recipes": [],
                "message": "더 이상의 추천이 없습니다. 다른 재료를 추가하거나 초기화해 보세요! 😊"
            })

        chosen = results[click_count]
        return jsonify({
            "analysis": chosen['analysis'],
            "recipes": [chosen],
            "message": chosen['message']
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
