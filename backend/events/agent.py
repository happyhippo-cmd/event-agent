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
사용자의 취향을 잘 이해하고, 서울에서 열리는 다양한 이벤트 중에서 가장 적합한 것을 추천하는 역할을 합니다.
사용자의 말이 애매하면 추가 질문을 통해 취향을 더 구체적으로 파악하려고 노력하세요.
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


def extract_search_intent(messages: list[dict], query: str) -> dict:
    """쿼리가 명확하면 검색, 애매하면 질문 반환"""
    history = "\n".join(f"{m['role']}: {m['content'][:200]}" for m in messages[-4:])
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=150,
        messages=[{
            "role": "user",
            "content": (
                f"대화:\n{history}\nuser: {query}\n\n"
                "이 대화에서 이벤트 검색 키워드를 뽑아줘.\n"
                "사용자가 조금이라도 힌트를 줬으면 그걸로 검색해. 키워드가 애매해도 최대한 search를 선택해.\n"
                "사용자가 아무 맥락도 없이 첫 마디부터 '추천해줘'처럼 완전히 비어있을 때만 ask를 선택해.\n"
                "반드시 아래 JSON 형식 중 하나로만 답해:\n"
                '{"action": "search", "keywords": "검색어"} 또는 {"action": "ask", "message": "질문 내용"}'
            )
        }]
    )
    raw = resp.choices[0].message.content.strip()
    start = raw.find("{")
    depth, end = 0, start
    for i, ch in enumerate(raw[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    return json.loads(raw[start:end])


def chat(messages: list[dict], query: str) -> dict:
    """대화 맥락을 유지하며 이벤트 추천"""
    intent = extract_search_intent(messages, query)
    if intent.get("action") ==  "ask":
        return {"message": intent["message"], "events": []}
    search_query = intent.get("keywords", query)
    candidates = search_events(query=search_query, mood="")

    if not candidates:
        return {
            "message": "앗, 딱 맞는 이벤트를 못 찾겠어요 😅 다른 지역이나 분위기로 찾아볼까요?",
            "events": []
        }

    events_context = build_context(candidates, {}) if candidates else "검색 결과 없음"

    llm_messages = [
        {"role": "system", "content": (
            SYSTEM_PROMPT +
            "\n대화 형식으로 자연스럽게 응답하세요. "
            "추천 이유는 반드시 해당 이벤트의 실제 제목·장소·설명에 있는 내용만 사용하세요. "
            "다른 이벤트의 내용을 섞거나 없는 내용을 지어내지 마세요. "
            "반드시 아래 JSON 형식으로만 응답하세요:\n"
            '{"message": "대화형 소개 문장", "recommendations": [{"index": 1, "reason": "추천 이유"}]}'
        )}
    ] + [
        {"role": m["role"], "content": m["content"]}
        for m in messages[-6:]
    ] + [{
        "role": "user",
        "content": f"{query}\n\n[후보 이벤트 목록]\n{events_context}"
    }]

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=1500,
        messages=llm_messages,
    )

    raw = resp.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    # 응답 중간에 JSON이 섞인 경우 { } 범위만 추출
    start = raw.find("{")
    end = raw.rfind("}") + 1
    try:
        data = json.loads(raw[start:end]) if start != -1 else {}
    except json.JSONDecodeError:
        return {"message": raw.strip(), "events": []}

    events = []
    for rec in data.get("recommendations", []):
        idx = rec.get("index", 0) - 1
        if 0 <= idx < len(candidates):
            ev = candidates[idx]
            date_str = str(ev.start_date) if ev.start_date else ""
            if ev.end_date:
                date_str += f" ~ {ev.end_date}"
            events.append({
                "title": ev.title,
                "location": ev.location,
                "date": date_str,
                "thumbnail_url": ev.thumbnail_url,
                "detail_url": ev.detail_url,
                "store_url": ev.store_url,
                "hashtags": ev.hashtags,
                "reason": rec.get("reason", ""),
            })

    return {"message": data.get("message", ""), "events": events}


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
