import os
import json
import base64
import re
from datetime import datetime, date
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from openai import OpenAI
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# Vercel 환경에서 루트의 templates 폴더를 찾을 수 있도록 경로 설정
app = Flask(__name__, template_folder='../templates')
CORS(app)

# ──────────────────────────────────────────────
# 유틸리티 함수
# ──────────────────────────────────────────────

def get_client(api_key=None):
    """OpenAI 클라이언트 반환"""
    # 사용자가 입력한 키가 있으면 우선 사용, 없으면 환경변수 사용
    key = api_key if api_key and api_key.strip() else os.getenv("OPENAI_API_KEY")
    
    if not key or key == "sk-your-api-key-here" or key.strip() == "":
        return None
    return OpenAI(api_key=key)

def extract_menu_from_image(client, image_b64):
    """급식표 이미지에서 날짜별 메뉴 추출 (GPT-4o Vision)"""
    prompt = """당신은 학교 급식표(식단표) OCR 전문가입니다.
이미지에서 날짜별 점심 메뉴를 찾아 아래 형식의 JSON으로만 반환하세요.
날짜 형식: "MM/DD(요일)" (예: "02/10(월)")
메뉴: 쉼표로 구분된 문자열
결과는 반드시 ```json ... ``` 블록 안에 넣으세요.
이미지에 급식표가 없다면 {}를 반환하세요."""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}
                    },
                ],
            }
        ],
        max_tokens=2000,
        temperature=0.1,
    )

    raw = response.choices[0].message.content
    json_match = re.search(r"```json\s*(.*?)\s*```", raw, re.DOTALL)
    if json_match:
        return json.loads(json_match.group(1))
    try:
        return json.loads(raw)
    except:
        return {}

def recommend_dinner(client, today_lunch, ingredients):
    """저녁 메뉴 추천 레시피 생성"""
    prompt = f"""[상황]
오늘 아이 급식: {today_lunch}
냉장고 재료: {ingredients}

[작업]
1. 점심과 주재료/조리방식이 겹치지 않는 저녁 메뉴 2개를 추천하세요.
2. 각 메뉴별 상세 레시피와 팁을 포함하세요.
3. 지친 부모님을 위한 따뜻한 응원 멘트로 마무리하세요.

[형식 - JSON]
{{
  "analysis": "점심 메뉴 분석",
  "recipes": [
    {{
      "name": "요리명",
      "desc": "한 줄 설명",
      "time": "분",
      "diff": "쉬움/보통/어려움",
      "ingredients": ["재료1", "재료2"],
      "steps": ["Step 1", "Step 2"],
      "tip": "꿀팁"
    }}
  ],
  "message": "응원 메시지"
}}
반드시 JSON 형식으로만 응답하세요."""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "당신은 따뜻한 요리 전문가 AI입니다."},
            {"role": "user", "content": prompt}
        ],
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)

# ──────────────────────────────────────────────
# API 라우트
# ──────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/config')
def get_config():
    """서버에 API 키가 설정되어 있는지 확인"""
    api_key = os.getenv("OPENAI_API_KEY")
    has_key = api_key is not None and api_key.strip() != "" and api_key != "sk-your-api-key-here"
    return jsonify({
        "hasServerKey": has_key,
        "demoMode": not has_key
    })

@app.route('/api/analyze', methods=['POST'])
def api_analyze():
    data = request.json
    api_key = data.get('apiKey')
    image_b64 = data.get('image').split(',')[-1] if ',' in data.get('image', '') else data.get('image')
    
    client = get_client(api_key)
    
    # 데모 모드: 키가 없으면 가짜 데이터 반환
    if not client:
        print("[! Demo Mode] No API Key found. Returning mock menu data.")
        mock_data = {
            "02/11(수)": "카레라이스, 미역국, 계란말이, 깍두기, 배",
            "02/12(목)": "비빔밥, 팽이버섯된장국, 떡갈비조림, 콩나물무침, 배추김치",
            "02/13(금)": "돈가스덮밥, 유부우동, 양배추샐러드, 단무지, 요구르트"
        }
        return jsonify(mock_data)
    
    try:
        menu_data = extract_menu_from_image(client, image_b64)
        return jsonify(menu_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/recommend', methods=['POST'])
def api_recommend():
    data = request.json
    api_key = data.get('apiKey')
    lunch = data.get('lunch')
    ingredients = data.get('ingredients')
    
    client = get_client(api_key)
    
    # 데모 모드: 키가 없으면 가짜 레시피 반환
    if not client:
        print("[! Demo Mode] No API Key found. Returning mock recipe data.")
        mock_recipe = {
            "analysis": f"오늘 점심은 '{lunch}'로 주재료가 카레와 계란인 것 같네요. 저녁은 겹치지 않게 담백한 국물 요리나 매콤한 볶음류를 추천합니다.",
            "recipes": [
                {
                    "name": "매콤 두부조림",
                    "desc": "냉장고에 있는 두부를 활용한 밥도둑 반찬",
                    "time": "15",
                    "diff": "쉬움",
                    "ingredients": ["두부", "대파", "고춧가루", "간장"],
                    "steps": ["두부를 먹기 좋게 썰어 구워줍니다.", "양념장을 올리고 졸여줍니다.", "대파를 뿌려 마무리합니다."],
                    "tip": "들기름에 구우면 훨씬 고소해요!"
                },
                {
                    "name": "스팸 애호박 고추장찌개",
                    "desc": "칼칼한 국물이 점심의 느끼함을 잡아줍니다",
                    "time": "20",
                    "diff": "보통",
                    "ingredients": ["스팸", "애호박", "고추장", "마늘"],
                    "steps": ["재료를 깍둑썰기합니다.", "고추장을 풀고 물을 넣습니다.", "재료를 넣고 푹 끓여줍니다."],
                    "tip": "스팸에서 짠맛이 나오니 소금 간은 나중에 하세요."
                }
            ],
            "message": "오늘도 고생 많으셨어요! 아이와 맛있는 건강한 저녁 식사 하세요. 당신은 최고의 부모님입니다! 💪"
        }
        return jsonify(mock_recipe)
    
    try:
        result = recommend_dinner(client, lunch, ingredients)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Flask 서버를 8080 포트로 실행 (5000번 포트 보안 차단 대비)
    print("--------------------------------------------------")
    print("Lunch-Check Dinner Bot Server Started!")
    print("Local URL: http://127.0.0.1:8080")
    print("--------------------------------------------------")
    app.run(debug=True, port=8080, host='127.0.0.1')
