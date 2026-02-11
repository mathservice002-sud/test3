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
        
        # 1. 고등어 + 무 (사용자 피드백 반영)
        if "고등어" in ingredients and "무" in ingredients:
            return jsonify({
                "analysis": "고등어와 무의 찰떡궁합! 비린내 없이 시원하고 칼칼한 조림 어떠세요?",
                "recipes": [{"name": "고등어 무조림", "desc": "양념이 잘 밴 무가 더 맛있는 밥도둑", "time": "30", "diff": "보통", "ingredients": ["고등어", "무", "간장", "고춧가루", "파"], "steps": ["무를 깔고 토막 낸 고등어를 올린다", "양념장을 붓고 국물이 자작해질 때까지 졸인다"], "tip": "무를 먼저 살짝 익힌 후 고등어를 넣으면 더 맛있어요"}],
                "message": "시원한 무조림 한 점에 오늘 하루의 스트레스도 싹 날려버리세요. 정말 훌륭한 메뉴 선택입니다! 🐟"
            })
        
        # 2. 고등어 단독
        elif "고등어" in ingredients:
            return jsonify({
                "analysis": "등푸른 생선 고등어로 아이들 두뇌 발달에도 좋은 영양 만점 식단을 준비해봐요.",
                "recipes": [{"name": "바삭 고등어 구이", "desc": "겉바속촉, 소금만 있으면 끝나는 간단 건강식", "time": "15", "diff": "쉬움", "ingredients": ["고등어", "굵은소금", "레몬즙"], "steps": ["팬이나 에어프라이어에 노릇하게 굽는다", "마지막에 레몬즙을 뿌려 비린내를 잡는다"], "tip": "밀가루를 살짝 묻혀 구우면 더 바삭해요"}],
                "message": "고소한 생선 굽는 냄새가 가득한 저녁, 아이들과 함께 맛있는 식사 시간 되시길 바랍니다! ✨"
            })

        # 3. 무 단독
        elif "무" in ingredients:
            return jsonify({
                "analysis": "시원하고 아삭한 무를 활용해 속이 편한 국이나 반찬을 만들어보세요.",
                "recipes": [{"name": "아삭 무생채", "desc": "입맛 돋우는 새콤달콤한 밑반찬", "time": "10", "diff": "매우 쉬움", "ingredients": ["무", "고춧가루", "식초", "설탕"], "steps": ["무를 채 썰어 양념에 버무린다", "상온에 잠시 두어 숨을 죽인다"], "tip": "소금에 먼저 5분 정도 절여야 물이 덜 생겨요"}],
                "message": "심플하지만 확실한 맛, 당신의 손맛이 더해져 최고의 반찬이 될 거예요. 오늘도 화이팅입니다! 🥬"
            })

        # 4. 소고기 + 떡
        elif "소고기" in ingredients and ("떡" in ingredients or "가래떡" in ingredients):
            return jsonify({
                "analysis": "냉장고에 있는 소고기와 가래떡으로 아이들이 정말 좋아하는 단짠단짠 궁중 떡볶이를 만들 수 있어요.",
                "recipes": [{"name": "궁중 떡볶이", "desc": "맵지 않아 아이들도 잘 먹는 고급스러운 떡볶이", "time": "20", "diff": "보통", "ingredients": ["가래떡", "소고기(불고기용)", "양파", "표고버섯", "간장소스"], "steps": ["떡은 말랑하게 불리고 고기는 밑간을 한다", "채소와 함께 볶다가 간장 소스로 간을 맞춘다"], "tip": "마지막에 참기름 한 방울과 통깨를 뿌리면 고소함이 폭발해요"}],
                "message": "영양 가득한 소고기와 쫀득한 떡의 조화처럼, 오늘 저녁 가족들과의 시간도 쫀득하고 행복하시길 바라요. 요리하느라 고생 많으셨습니다! 🍖"
            })

        # 5. 소고기 단독
        elif "소고기" in ingredients:
            return jsonify({
                "analysis": "준비된 소고기로 국물 맛이 일품인 소고기 뭇국을 끓여보세요. 속이 확 풀릴 거예요.",
                "recipes": [{"name": "맑은 소고기 뭇국", "desc": "누구나 좋아하는 시원하고 담백한 국물 요리", "time": "30", "diff": "보통", "ingredients": ["소금", "무", "국거리 소고기", "다진 마늘"], "steps": ["소고기와 무를 참기름에 볶는다", "물을 붓고 거품을 걷어내며 푹 끓인다"], "tip": "무를 얇게 썰면 조리 시간을 단축할 수 있어요"}],
                "message": "따뜻한 국물 한 그릇에 오늘 하루의 고단함도 사르르 녹아내리길 바랍니다. 당신의 따뜻한 마음이 아이에게도 전달될 거예요. 🍲"
            })

        # 6. 감자 / 파프리카 등 야채
        elif "감자" in ingredients or "파프리카" in ingredients:
            keyword = "감자" if "감자" in ingredients else "파프리카"
            return jsonify({
                "analysis": f"신선한 {keyword}를 활용해 아이들 입맛에 딱 맞는 고소한 볶음 요리를 추천합니다.",
                "recipes": [{"name": f"{keyword} 야채 볶음", "desc": "색깔도 예쁘고 영양도 가득한 반찬", "time": "15", "diff": "쉬움", "ingredients": [keyword, "양파", "햄 또는 베이컨", "굴소스"], "steps": ["모든 재료를 채 썬 뒤 팬에서 볶는다", "마지막에 꿀 또는 올리고당을 살짝 넣는다"], "tip": "센 불에서 빠르게 볶아야 아삭함이 살아요"}],
                "message": "알록달록 예쁜 밥상 위에 당신의 사랑도 가득 담겼네요. 아이들과 웃음 가득한 저녁 되세요! ✨"
            })

        # 7. 계란 / 두부
        elif "계란" in ingredients or "두부" in ingredients:
            keyword = "계란" if "계란" in ingredients else "두부"
            return jsonify({
                "analysis": f"단백질이 풍부한 {keyword}로 속 편하고 부드러운 한 끼를 준비해보세요.",
                "recipes": [{"name": f"보들보들 {keyword} 요리", "desc": "아이들이 소화하기 쉬운 건강한 추천 식단", "time": "10", "diff": "매우 쉬움", "ingredients": [keyword, "파", "참기름", "새우젓 또는 간장"], "steps": ["재료를 손질해 육수나 팬에 넣고 조리한다", "부드러운 식감이 살아나도록 불 조절을 한다"], "tip": "참기름 한 방울이 고소한 풍미의 비결입니다"}],
                "message": "간단하지만 가장 든든한 한 끼, 당신의 지혜가 빛나는 순간입니다. 고생 많으셨어요! ❤️"
            })

        # 재료가 입력되었는데 매칭되는 레시피가 없는 경우
        if has_ingredients:
            return jsonify({
                "analysis": f"입력하신 재료({ingredients})로 만들 수 있는 색다른 추천입니다.",
                "recipes": [{"name": "나만의 아이디어 만찬", "desc": "냉장고 속 재료들을 모아 만드는 세상에 하나뿐인 요리", "time": "20", "diff": "보통", "ingredients": [ingredients], "steps": ["준비된 모든 재료를 깨끗이 씻어 손질한다", "익는 순서대로 센 불에서 볶거나 푹 끓인다"], "tip": "어떤 재료든 당신의 정성이 들어가면 최고의 요리가 됩니다"}],
                "message": "데모 모드에 없는 재료도 실제 AI 버전에서는 완벽하게 분석해 드립니다! 지금은 당신의 창의력을 믿어보세요. 응원합니다! 🍀"
            })

        # 재료가 비어있을 때 (기본 추천)
        return jsonify({
            "analysis": "오늘 무엇을 할지 고민될 때는 누구나 좋아하는 든든한 한 끼를 추천드려요.",
            "recipes": [{"name": "영양 가득 계란말이", "desc": "채소를 듬뿍 넣어 영양과 색감을 모두 잡은 반찬", "time": "15", "diff": "보통", "ingredients": ["계란", "당근", "파", "소금"], "steps": ["계란을 풀고 잘게 썬 채소를 섞는다", "팬에 조금씩 부어가며 돌돌 말아 익힌다"], "tip": "약불에서 천천히 말아야 모양이 예쁘게 잡혀요"}],
            "message": "무엇을 만들어도 당신의 정성이 최고의 조미료입니다. 오늘 밤은 가족과 함께 오순도순 따뜻한 식탁 되시길 바라요. 🍀"
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
