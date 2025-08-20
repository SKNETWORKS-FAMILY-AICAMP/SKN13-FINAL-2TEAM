import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
model = "gpt-4o-mini"

def recommend_clothing_by_weather(weather_description: str, gender: str) -> dict:
    """
    날씨 상황과 성별에 따라 의류를 추천합니다.

    Args:
        weather_description (str): LLM이 분류한 날씨 상황 설명 (예: "한여름, 매우 더운 날씨").
        gender (str): 사용자 성별 ("남성" 또는 "여성").

    Returns:
        dict: 추천 의류 목록 (대분류/소분류 체계에 따름).
              예: {"상의": ["반팔", "얇은 셔츠"], "하의": ["반바지"]}
    """
    # LLM을 사용하여 의류 추천 로직
    system_prompt = f"""당신은 의류 스타일리스트입니다.
    주어진 날씨 상황과 성별에 따라 적합한 의류 아이템을 추천해주세요.
    추천은 다음 카테고리 내에서 이루어져야 합니다:
    - 상의: 후드티, 셔츠블라우스, 긴소매, 반소매, 피케카라, 니트스웨터, 슬리브리스, 애슬레저
    - 하의: 데님 팬츠, 트레이닝/조거 팬츠, 코튼 팬츠, 슈트 팬츠/슬랙스, 숏 팬츠, 레깅스
    - 원피스 (여성만): 미니원피스, 미디원피스, 맥시원피스
    - 스커트 (여성만): 미니스커트, 미디스커트, 롱스커트

    남성에게 '셔츠블라우스'는 '셔츠'로, '슬리브리스'는 '애슬레저'로 해석해주세요.
    '긴소매'와 '반소매'는 일반적인 긴팔/반팔 상의를 의미합니다.

    응답은 반드시 다음 JSON 형식으로만 해주세요:
    {{
        "상의": ["아이템1", "아이템2"],
        "하의": ["아이템3", "아이템4"]{f', "원피스": ["아이템5"]' if gender == "여성" else ''}{f', "스커트": ["아이템6"]' if gender == "여성" else ''}
    }}
    """
    user_prompt = f"날씨 상황: {weather_description}, 성별: {gender}"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.7,
            response_format={"type": "json_object"}
        )
        raw_llm_response_content = response.choices[0].message.content
        print(f"DEBUG: Raw LLM response content: {raw_llm_response_content}")
        recommended_items = json.loads(raw_llm_response_content)
        print(f"DEBUG: Parsed recommended_items: {recommended_items}")
        return recommended_items
    except Exception as e:
        print(f"LLM 의류 추천 요청 오류: {e}")
        # 오류 시 기본값 또는 빈 목록 반환
        return {"상의": [], "하의": []}

if __name__ == "__main__":
    # 테스트 코드
    print("--- 남성 의류 추천 ---")
    print(f"쌀쌀한 날씨: {recommend_clothing_by_weather('쌀쌀한 날씨', '남성')}")
    print(f"선선한 날씨: {recommend_clothing_by_weather('선선한 날씨', '남성')}")
    print(f"따뜻한 날씨: {recommend_clothing_by_weather('따뜻한 날씨', '남성')}")
    print(f"매우 더운 날씨: {recommend_clothing_by_weather('매우 더운 날씨', '남성')}")

    print("\n--- 여성 의류 추천 ---")
    print(f"쌀쌀한 날씨: {recommend_clothing_by_weather('쌀쌀한 날씨', '여성')}")
    print(f"선선한 날씨: {recommend_clothing_by_weather('선선한 날씨', '여성')}")
    print(f"따뜻한 날씨: {recommend_clothing_by_weather('따뜻한 날씨', '여성')}")
    print(f"매우 더운 날씨: {recommend_clothing_by_weather('매우 더운 날씨', '여성')}")