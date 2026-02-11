# 🍽️ 급식 해결사: 저녁 메뉴 고민 끝!

> Lunch-Check Dinner Bot — 학교 점심과 겹치지 않는 스마트한 저녁 식단 가이드

## ✨ 주요 기능

| 기능 | 설명 |
|------|------|
| 📸 급식표 OCR | 급식표 사진을 업로드하면 AI가 자동으로 날짜별 메뉴 추출 |
| 🚫 중복 필터링 | 점심과 겹치는 주재료/조리방식을 자동 제외 |
| 🥬 냉털 레시피 | 냉장고 재료를 활용한 맞춤 저녁 레시피 추천 |
| 💪 응원 멘트 | 퇴근 후 지친 부모님을 위한 따뜻한 한마디 |

## 🚀 빠른 시작

### 1. 의존성 설치
```bash
pip install -r requirements.txt
```

### 2. API 키 설정
`.env.example`을 복사하여 `.env` 파일을 만들고 OpenAI API 키를 입력하세요:
```bash
cp .env.example .env
# .env 파일을 열어 API 키 입력
```

또는 앱 사이드바에서 직접 입력할 수 있습니다.

### 3. 앱 실행
```bash
streamlit run app.py
```

## 📁 프로젝트 구조
```
.
├── app.py                  # 메인 Streamlit 앱
├── requirements.txt        # Python 의존성
├── .env.example            # 환경변수 예시
├── .gitignore
├── .streamlit/
│   └── config.toml         # Streamlit 테마 설정
└── README.md
```

## 🛠️ 기술 스택

- **Frontend**: Streamlit
- **AI/OCR**: OpenAI GPT-4o mini (Vision)
- **Language**: Python 3.10+

## 📝 사용법

1. **API 키 입력**: 사이드바에서 OpenAI API 키를 입력합니다
2. **급식표 업로드**: 학교 급식표 사진을 업로드하거나, 오늘 점심 메뉴를 직접 입력합니다
3. **재료 입력**: 냉장고에 있는 재료를 콤마(,)로 구분하여 입력합니다
4. **추천 받기**: "저녁 메뉴 추천받기" 버튼을 클릭합니다
5. **요리 시작**: 추천된 레시피로 맛있는 저녁을 준비하세요! 🍳

## 📜 라이선스

MIT License
