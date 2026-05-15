"""
이벤트 에이전트
입력: { query, genres, artists, mood }
출력: [ { title, location, date, thumbnail_url, detail_url, description, reason } ]
"""

import json
from datetime import date

from openai import OpenAI
from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from events.models import Event

client = OpenAI(api_key=settings.OPENAI_API_KEY)

SYSTEM_PROMPT = """당신은 K-Dive 서비스의 이벤트 큐레이터입니다.
사용자의 K-pop 취향(장르, 아티스트, 분위기)을 바탕으로 팝업스토어·전시·이벤트를 추천합니다.
각 이벤트마다 사용자 취향과 연결되는 추천 이유를 한국어로 2~3문장 이내로 작성하세요.
감성적이고 공감가는 문체로 작성하되, 과장하지 마세요."""


# 서울 주요 지역명 — 쿼리에서 장소 의도를 감지하는 데 사용
SEOUL_AREAS = [
    '성수', '홍대', '강남', '이태원', '명동', '신촌', '합정', '망원',
    '북촌', '인사동', '압구정', '청담', '한남', '용산', '여의도',
    '종로', '광화문', '동대문', '신사', '가로수길', '잠실', '건대',
    '마포', '연남', '을지로', '익선동', '서촌', '뚝섬', '송파',
]

STOP_WORDS = {'팝업', '추천', '해줘', '알려줘', '보여줘', '있어', '어디', '뭐', '좀', '이번', '주변'}

CATEGORY_KEYWORDS = {
    '전시': '전시',
    '페스티벌': '페스티벌',
    '공연': '공연',
    '박람회': '박람회',
    '팝업스토어': '팝업스토어',
    '팝업': '팝업스토어',
}


def extract_keywords(text: str) -> list[str]:
    """불용어를 제거한 의미 있는 키워드 추출"""
    words = [w.strip() for w in text.split() if w.strip()]
    return [w for w in words if w not in STOP_WORDS and len(w) > 1]


def search_events(query: str, mood: str, limit: int = 20) -> list[Event]:
    """
    단계별 검색:
    1단계) 위치 + 키워드 모두 매칭
    2단계) 키워드만 매칭 (위치 조건 완화)
    3단계) 진행 중인 이벤트 최신순 (완전 폴백)
    """
    today = timezone.localdate()
    active_qs = Event.objects.filter(
        Q(end_date__gte=today) | Q(end_date__isnull=True)
    )

    # 쿼리에서 카테고리 감지
    detected_category = None
    for kw, cat in CATEGORY_KEYWORDS.items():
        if kw in query or kw in mood:
            detected_category = cat
            break

    if detected_category:
        active_qs = active_qs.filter(new_main_category=detected_category)
        if detected_category == '전시':
            active_qs = active_qs.exclude(commerciality='브랜드')

    # 쿼리에서 위치명 감지
    detected_areas = [area for area in SEOUL_AREAS if area in query]

    # 위치 필터
    loc_filter = Q()
    if detected_areas:
        for area in detected_areas:
            loc_filter |= Q(location__icontains=area)

    # 키워드 필터 (위치명 제외한 나머지 단어 + mood)
    keywords = extract_keywords(f"{query} {mood}")
    non_area_keywords = [kw for kw in keywords if kw not in SEOUL_AREAS]

    kw_filter = Q()
    for kw in non_area_keywords:
        kw_filter |= (
            Q(title__icontains=kw) |
            Q(description__icontains=kw) |
            Q(hashtags__icontains=kw) |
            Q(mood_tags__icontains=kw) |
            Q(activity_tags__icontains=kw) |
            Q(theme_tags__icontains=kw) |
            Q(space_tags__icontains=kw) |
            Q(audience_tags__icontains=kw) |
            Q(music_genre__icontains=kw) |
            Q(new_mood_tags__icontains=kw) |
            Q(new_audience_tags__icontains=kw) |
            Q(new_main_category__icontains=kw) |
            Q(new_sub_category__icontains=kw) |
            Q(region__icontains=kw)
        )

    # 1단계: 위치 + 키워드
    if detected_areas and non_area_keywords:
        qs = active_qs.filter(loc_filter & kw_filter)
        if qs.count() >= 3:
            return list(qs.order_by('start_date')[:limit])

    # 2단계: 위치만 (위치 지정 시 위치 조건 유지)
    if detected_areas:
        qs = active_qs.filter(loc_filter)
        if qs.exists():
            return list(qs.order_by('start_date')[:limit])

    # 3단계: 키워드만 (위치 미지정 시)
    if non_area_keywords:
        qs = active_qs.filter(kw_filter)
        if qs.exists():
            return list(qs.order_by('start_date')[:limit])

    # 완전 폴백: 카테고리 내 전체
    return list(active_qs.order_by('start_date')[:limit])


def build_context(events: list[Event], preference: dict) -> str:
    """LLM에 넘길 이벤트 목록 + 취향 컨텍스트 문자열 생성"""
    pref_str = (
        f"장르: {', '.join(preference.get('genres', []))}\n"
        f"아티스트: {', '.join(preference.get('artists', []))}\n"
        f"분위기: {preference.get('mood', '')}"
    )

    events_str = ""
    for i, ev in enumerate(events, 1):
        date_str = ""
        if ev.start_date:
            date_str = str(ev.start_date)
            if ev.end_date:
                date_str += f" ~ {ev.end_date}"
        events_str += (
            f"{i}. [{ev.title}]\n"
            f"   장소: {ev.location}\n"
            f"   기간: {date_str}\n"
            f"   설명: {ev.description[:200]}\n"
            f"   해시태그: {' '.join(ev.hashtags[:5])}\n\n"
        )

    return f"[사용자 취향]\n{pref_str}\n\n[후보 이벤트]\n{events_str}"


def curate_with_llm(events: list[Event], preference: dict, query: str) -> list[dict]:
    """LLM으로 취향 기반 추천 이유 생성"""
    if not events:
        return []

    context = build_context(events, preference)

    prompt = f"""사용자 질문: "{query}"

{context}

위 후보 이벤트 중 사용자 취향에 가장 잘 맞는 이벤트를 최대 5개 선정하고,
아래 JSON 형식으로 응답하세요. 반드시 JSON만 출력하세요.

[
  {{
    "index": 1,
    "reason": "추천 이유 (2~3문장)"
  }},
  ...
]"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=1024,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    )

    raw = response.choices[0].message.content.strip()
    # JSON 파싱
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    selections = json.loads(raw.strip())

    results = []
    for sel in selections:
        idx = sel.get("index", 0) - 1
        if 0 <= idx < len(events):
            ev = events[idx]
            date_str = ""
            if ev.start_date:
                date_str = str(ev.start_date)
                if ev.end_date:
                    date_str += f" ~ {ev.end_date}"
            results.append({
                "title": ev.title,
                "location": ev.location,
                "date": date_str,
                "thumbnail_url": ev.thumbnail_url,
                "detail_url": ev.detail_url,
                "store_url": ev.store_url,
                "description": ev.description[:300],
                "hashtags": ev.hashtags,
                "reason": sel.get("reason", ""),
            })

    return results


def run(query: str, genres: list[str] = None, artists: list[str] = None, mood: str = "") -> list[dict]:
    """
    이벤트 에이전트 메인 함수
    Supervisor 또는 API 뷰에서 이 함수를 호출합니다.

    Args:
        query:   사용자 자연어 질문
        genres:  K-pop 장르 목록 (예: ['idol', 'hiphop'])
        artists: 좋아하는 아티스트 목록 (예: ['BTS', 'NewJeans'])
        mood:    분위기 키워드 (예: '활기찬', '감성적인')

    Returns:
        추천 이벤트 카드 목록
    """
    preference = {
        "genres": genres or [],
        "artists": artists or [],
        "mood": mood,
    }

    candidates = search_events(query=query, mood=mood)
    if not candidates:
        return []

    return curate_with_llm(candidates, preference, query)
