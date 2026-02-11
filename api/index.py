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
        # 데모 모드: 입력된 재료에 맞춰 지능적인 가짜 데이터 반환
        if "소고기" in ingredients and ("떡" in ingredients or "가래떡" in ingredients):
            return jsonify({
                "analysis": "냉장고에 있는 소고기와 가래떡으로 아이들이 정말 좋아하는 단짠단짠 궁중 떡볶이를 만들 수 있어요.",
                "recipes": [{"name": "궁중 떡볶이", "desc": "맵지 않아 아이들도 잘 먹는 고급스러운 떡볶이", "time": "20", "diff": "보통", "ingredients": ["가래떡", "소고기(불고기용)", "양파", "표고버섯", "간장소스"], "steps": ["떡은 말랑하게 불리고 고기는 밑간을 한다", "채소와 함께 볶다가 간장 소스로 간을 맞춘다"], "tip": "마지막에 참기름 한 방울과 통깨를 뿌리면 고소함이 폭발해요"}],
                "message": "영양 가득한 소고기와 쫀득한 떡의 조화처럼, 오늘 저녁 가족들과의 시간도 쫀득하고 행복하시길 바라요. 요리하느라 고생 많으셨습니다! 🍖"
            })
        elif "소고기" in ingredients:
            return jsonify({
                "analysis": "준비된 소고기로 국물 맛이 일품인 소고기 뭇국을 끓여보세요. 속이 확 풀릴 거예요.",
                "recipes": [{"name": "맑은 소고기 뭇국", "desc": "누구나 좋아하는 시원하고 담백한 국물 요리", "time": "30", "diff": "보통", "ingredients": ["소금", "무", "국거리 소고기", "다진 마늘"], "steps": ["소고기와 무를 참기름에 볶는다", "물을 붓고 거품을 걷어내며 푹 끓인다"], "tip": "무를 얇게 썰면 조리 시간을 단축할 수 있어요"}],
                "message": "따뜻한 국물 한 그릇에 오늘 하루의 고단함도 사르르 녹아내리길 바랍니다. 당신의 따뜻한 마음이 아이에게도 전달될 거예요. 🍲"
            })
        elif "떡" in ingredients or "가래떡" in ingredients:
            return jsonify({
                "analysis": "가래떡으로 간단하면서도 맛있는 간장 떡볶이를 만들어보세요.",
                "recipes": [{"name": "간장 떡볶이", "desc": "부드럽고 달콤한 아이들 맞춤 간식 겸 식사", "time": "15", "diff": "쉬움", "ingredients": ["가래떡", "간장", "설탕", "참기름"], "steps": ["떡을 물에 살짝 데친다", "팬에 양념장과 함께 졸이듯이 볶는다"], "tip": "파기름을 먼저 내면 풍미가 훨씬 좋아집니다"}],
                "message": "말랑말랑한 떡처럼 오늘 밤은 부드럽고 편안한 휴식 시간이 되시길 응원합니다. 수고 많으셨어요! 🍡"
            })
        elif "감자" in ingredients:
            return jsonify({
                "analysis": "냉장고에 있는 감자를 활용해 점심과 어울리는 고소하고 포근한 메뉴를 추천합니다.",
                "recipes": [{"name": "포근포근 감자조림", "desc": "남녀노소 좋아하는 국민 밑반찬", "time": "20", "diff": "쉬움", "ingredients": ["감자", "간장", "올리고당", "물"], "steps": ["감자를 깍둑썰기해 물에 담가 전분을 뺀다", "양념장과 함께 감자가 익을 때까지 졸인다"], "tip": "마지막에 꿀을 한 스푼 넣으면 윤기가 좌르르 흘러요"}],
                "message": "부드러운 감자 요리처럼 아이의 일상도 당신의 사랑으로 포근하게 채워질 거예요. 오늘도 정말 고생 많으셨습니다! 🥔"
            })
        elif "배추" in ingredients:
            return jsonify({
                "analysis": "신선한 배추로 시원하고 달큰한 국물을 만들어보세요.",
                "recipes": [{"name": "배추 된장국", "desc": "자극 없이 시원한 맛", "time": "15", "diff": "쉬움", "ingredients": ["배추", "된장", "멸치육수"], "steps": ["육수에 된장을 풀고 배추를 넣는다", "배추가 부드러워질 때까지 끓인다"], "tip": "들깨가루를 한 스푼 넣으면 더 구수해요"}],
                "message": "시원한 국물에 오늘 하루 쌓인 피로도 훌훌 털어내시길 바라요. 당신의 정성이 최고의 보약입니다. 🥬"
            })
        elif "스팸" in ingredients or "햄" in ingredients:
            return jsonify({
                "analysis": "아이들이 좋아하는 스팸으로 든든한 고기 반찬을 준비해 보세요.",
                "recipes": [{"name": "스팸 양파 볶음", "desc": "실패 없는 짭조름한 밥도둑", "time": "10", "diff": "매우 쉬움", "ingredients": ["스팸", "양파", "올리고당"], "steps": ["스팸과 양질의 양파를 볶는다", "올리고당을 살짝 넣어 코팅한다"], "tip": "통깨를 뿌려 마무리하세요"}],
                "message": "빠르게 뚝딱 만들어낸 요리지만, 그 안에 담긴 사랑은 결코 가볍지 않죠. 고생한 자신을 위해 맛있는 저녁 되세요! ✨"
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
    prompt = f"""[상황] 오늘 아이 점심: {lunch}, 냉장고 재료: {ingredients}. 점심과 겹치지 않는 저녁 메뉴 2개와 레시피, 그리고 지친 부모님을 위한 맞춤형 응원 멘트를 JSON으로 작성해줘."""
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": "공감 능력이 뛰어난 요리 전문가입니다."}, {"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    return jsonify(json.loads(response.choices[0].message.content))

# Vercel을 위한 핸들러
app = app
