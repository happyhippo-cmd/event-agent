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

SYSTEM_PROMPT = """너는 K-Dive 서비스의 이벤트 큐레이터야.
서울에서 열리는 팝업스토어·전시·이벤트 중 사용자 취향에 딱 맞는 걸 추천해줘.
반드시 캐주얼하고 친근한 존댓말(~요, ~세요, ~드릴게요)을 사용해. 절대 반말(~해, ~야, ~줄게, ~있어)을 쓰지 마.
각 이벤트마다 사용자 취향과 연결되는 추천 이유를 2~3문장으로 써줘.
감성적이고 공감 가게 쓰되, 과장하거나 없는 내용 지어내지 마."""


# 서울 주요 지역명 — 쿼리에서 장소 의도를 감지하는 데 사용
SEOUL_AREAS = [
    '성수', '홍대', '강남', '이태원', '명동', '신촌', '합정', '망원',
    '북촌', '인사동', '압구정', '청담', '한남', '용산', '여의도',
    '종로', '광화문', '동대문', '신사', '가로수길', '잠실', '건대',
    '마포', '연남', '을지로', '익선동', '서촌', '뚝섬', '송파',
]

STOP_WORDS = {'팝업', '추천', '해줘', '알려줘', '보여줘', '있어', '어디', '뭐', '좀', '이번', '주변'}

# 사용자에게 보여줄 카테고리명 → DB 서브카테고리 매핑
POPUP_SUBCATEGORIES = {
    '패션': ['패션'],
    '미식': ['식음료', '음식음료'],
    '라이프스타일': ['라이프스타일', '리빙', '홈데코', '홈 인테리어'],
    '캐릭터': ['캐릭터굿즈', '캐릭터'],
    '뷰티': ['뷰티', '향수'],
    '아티스트': ['아티스트', '음악'],
    '스포츠': ['스포츠', '아웃도어'],
    '체험': ['체험', '체험형'],
}

EXHIBITION_SUBCATEGORIES = {
    '아트/회화': ['아트', '회화전'],
    '설치미술': ['설치미술'],
    '사진전': ['사진전', '사진'],
    '미디어아트': ['미디어아트'],
    '체험형': ['체험형전시', '체험전시'],
    '캐릭터': ['캐릭터전시'],
}

BROAD_RESULT_THRESHOLD = 10  # 이 이상이면 결과 많다고 판단

CATEGORY_KEYWORDS = {
    '전시': '전시',
    '페스티벌': '페스티벌',
    '공연': '공연',
    '박람회': '박람회',
    '팝업스토어': '팝업스토어',
    '팝업': '팝업스토어',
}


def is_vague_popup_query(query: str, search_query: str) -> bool:
    """팝업 관련인데 세부 카테고리 지정이 없는 경우"""
    combined = query + " " + search_query
    has_popup = any(kw in combined for kw in ['팝업', '팝업스토어'])
    has_subcategory = any(kw in combined for kw in POPUP_SUBCATEGORIES.keys())
    return has_popup and not has_subcategory


def _apply_location_filter(qs, detected_areas, broad_location=""):
    if detected_areas:
        loc_filter = Q()
        for area in detected_areas:
            loc_filter |= Q(location__icontains=area)
        return qs.filter(loc_filter)
    if broad_location:
        return qs.filter(location__icontains=broad_location)
    return qs


def get_available_categories(detected_areas: list[str], broad_location: str = "") -> list[str]:
    """해당 지역에서 진행 중인 팝업의 카테고리 목록 반환"""
    today = timezone.localdate()
    qs = Event.objects.filter(new_main_category='팝업스토어').filter(
        Q(end_date__gte=today) | Q(end_date__isnull=True)
    )
    qs = _apply_location_filter(qs, detected_areas, broad_location)
    existing = set(qs.values_list('new_sub_category', flat=True).distinct())
    return [name for name, db_vals in POPUP_SUBCATEGORIES.items() if any(v in existing for v in db_vals)]


def extract_user_taste(messages: list[dict]) -> str:
    """대화 히스토리에서 사용자 취향 키워드 추출"""
    if len(messages) < 2:
        return ""
    history = "\n".join(f"{m['role']}: {m['content'][:150]}" for m in messages[-6:])
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=80,
        messages=[{
            "role": "user",
            "content": (
                f"대화:\n{history}\n\n"
                "이 대화에서 사용자가 직접 좋아한다고 말한 것(아티스트, 장르, 분위기 등) 키워드를 3개 이내로 뽑아줘.\n"
                "단, 사용자가 검색하거나 클릭한 카테고리(아트/회화, 설치미술, 미디어아트, 사진전, 체험형, 캐릭터, 팝업, 전시, 공연, 페스티벌 등 이벤트 종류 자체)는 취향으로 절대 포함하지 마.\n"
                "없으면 빈 문자열로만 답해. 있으면 키워드만 쉼표로 구분해서 답해. 예: 감성적, 뉴진스"
            )
        }]
    )
    result = resp.choices[0].message.content.strip()
    return "" if result in ("없음", "none", "", "-", "없어", "모름") else result


def get_exhibition_categories(detected_areas: list[str], broad_location: str = "") -> list[str]:
    """해당 지역에서 진행 중인 전시의 카테고리 목록 반환"""
    today = timezone.localdate()
    qs = Event.objects.filter(new_main_category='전시').filter(
        Q(end_date__gte=today) | Q(end_date__isnull=True)
    )
    qs = _apply_location_filter(qs, detected_areas, broad_location)
    existing = set(qs.values_list('new_sub_category', flat=True).distinct())
    return [name for name, db_vals in EXHIBITION_SUBCATEGORIES.items() if any(v in existing for v in db_vals)]


def extract_keywords(text: str) -> list[str]:
    """불용어를 제거한 의미 있는 키워드 추출"""
    words = [w.strip() for w in text.split() if w.strip()]
    return [w for w in words if not any(sw in w for sw in STOP_WORDS) and len(w) > 1]


def detect_subcategory_filter(query: str, search_query: str) -> list[str]:
    """쿼리에서 명시된 서브카테고리의 DB 값 목록 반환"""
    combined = f" {query} {search_query} "  # 앞뒤 공백으로 단어 경계 처리

    def word_match(word: str) -> bool:
        return f" {word} " in combined or combined.startswith(f" {word} ") or combined.endswith(f" {word} ")

    is_exhibition = word_match("전시")
    is_popup = word_match("팝업") or word_match("팝업스토어")
    first, second = (EXHIBITION_SUBCATEGORIES, POPUP_SUBCATEGORIES) if is_exhibition else (POPUP_SUBCATEGORIES, EXHIBITION_SUBCATEGORIES)

    for display_name, db_vals in first.items():
        normalized = display_name.replace("/", " ")
        if word_match(display_name) or word_match(normalized) or any(word_match(v) for v in db_vals):
            return db_vals
    if not is_exhibition and not is_popup:
        for display_name, db_vals in second.items():
            normalized = display_name.replace("/", " ")
            if word_match(display_name) or word_match(normalized) or any(word_match(v) for v in db_vals):
                return db_vals
    return []


def search_events(query: str, mood: str, limit: int = 20, sub_category_filter: list = None) -> list[Event]:
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

    # 서브카테고리 필터 (캐릭터전시, 설치미술 등 명시된 경우)
    if sub_category_filter:
        active_qs = active_qs.filter(new_sub_category__in=sub_category_filter)

    # 쿼리에서 위치명 감지
    detected_areas = [area for area in SEOUL_AREAS if area in query]

    # 위치 필터
    loc_filter = Q()
    if detected_areas:
        for area in detected_areas:
            loc_filter |= Q(location__icontains=area)

    # 키워드 필터 (위치명·카테고리명·광역명 제외한 나머지 단어 + mood)
    keywords = extract_keywords(f"{query} {mood}")
    category_kws = set(CATEGORY_KEYWORDS.keys())
    non_area_keywords = [kw for kw in keywords if kw not in SEOUL_AREAS and kw not in category_kws and kw != '서울']

    # "서울" 광역 필터 — 특정 지역명 없이 서울만 언급한 경우 서울 내 이벤트로 제한
    if '서울' in query and not detected_areas:
        active_qs = active_qs.filter(location__icontains='서울')

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

    # 완전 폴백: 키워드도 지역도 없을 때만 (의도가 있는데 결과 없으면 빈 목록 반환)
    if not non_area_keywords and not detected_areas:
        return list(active_qs.order_by('start_date')[:limit])
    return []


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

위 후보 이벤트 중 사용자 취향과 실질적으로 관련 있는 이벤트만 최대 5개 선정하세요.
억지로 연결고리를 만들지 마세요. 관련 없는 이벤트는 제외하고, 관련 이벤트가 없으면 빈 배열을 반환하세요.
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
                "ask를 선택할 때 message는 반드시 캐주얼한 존댓말(~요, ~세요)로 써줘. 절대 반말 금지. 예: '어떤 거 찾으세요? 팝업, 전시, 공연 등 다양하게 있어요!'\n"
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
    if intent.get("action") == "ask":
        return {"message": intent["message"], "events": []}

    search_query = intent.get("keywords", query)
    detected_areas = [area for area in SEOUL_AREAS if area in query]
    broad_location = '서울' if '서울' in query and not detected_areas else ""
    location_str = detected_areas[0] if detected_areas else (broad_location or "서울")

    # 팝업 애매한 경우 → 카테고리 먼저 (전시 쿼리면 제외)
    if is_vague_popup_query(query, search_query) and '전시' not in query and '전시' not in search_query:
        categories = get_available_categories(detected_areas, broad_location)
        return {
            "message": f"{location_str} 팝업이 정말 다양해요! 어떤 종류 팝업 관심 있으세요?",
            "events": [],
            "categories": categories,
            "category_type": "popup",
            "location": location_str,
        }

    sub_cat_filter = detect_subcategory_filter(query, search_query)
    candidates = search_events(query=search_query, mood="", sub_category_filter=sub_cat_filter)

    if not candidates:
        return {
            "message": "딱 맞는 이벤트를 못 찾겠어요 😅 장르나 아티스트, 원하는 지역을 더 알려주시면 더 잘 찾아드릴게요!",
            "events": [],
        }

    # 대화 히스토리에서 취향 추출
    user_taste = extract_user_taste(messages)

    # 이미 세부 카테고리가 지정된 경우 다시 좁히지 않음
    combined = query + " " + search_query
    has_specific_subcategory = (
        any(k in combined for k in EXHIBITION_SUBCATEGORIES)
        or any(v in combined for vals in EXHIBITION_SUBCATEGORIES.values() for v in vals)
        or any(k in combined for k in POPUP_SUBCATEGORIES)
        or any(v in combined for vals in POPUP_SUBCATEGORIES.values() for v in vals)
    )

    # 결과 많고 취향 모를 때 → 카테고리로 좁히기
    if len(candidates) > BROAD_RESULT_THRESHOLD and not user_taste and not has_specific_subcategory:
        is_exhibition = '전시' in search_query or '전시' in query
        if is_exhibition:
            categories = get_exhibition_categories(detected_areas, broad_location)
            if categories:
                return {
                    "message": f"{location_str}에 전시가 엄청 많아요! 어떤 스타일 좋아하세요?",
                    "events": [],
                    "categories": categories,
                    "category_type": "exhibition",
                    "location": location_str,
                }
        elif is_vague_popup_query(query, search_query):
            categories = get_available_categories(detected_areas, broad_location)
            return {
                "message": f"{location_str} 팝업이 정말 다양해요! 어떤 종류 관심 있으세요?",
                "events": [],
                "categories": categories,
                "category_type": "popup",
                "location": location_str,
            }

    # 취향 정보를 컨텍스트에 포함
    preference = {"genres": [], "artists": [], "mood": user_taste}
    events_context = build_context(candidates, preference)

    taste_instruction = (
        f"\n사용자 취향 힌트: {user_taste}\n"
        "취향을 반영해서 추천하고, message에 '너 스타일엔 이게 딱일 것 같아!' 같이 취향 언급해줘."
        if user_taste else ""
    )

    llm_messages = [
        {"role": "system", "content": (
            SYSTEM_PROMPT +
            "\n반드시 캐주얼하고 친근한 존댓말(~요, ~세요, ~드릴게요)로만 응답해. 절대 반말(~해, ~야, ~줄게, ~있어, ~보여줄게) 쓰지 마. "
            "아래 후보 이벤트들은 이미 사용자 검색어와 매칭된 이벤트들이야. "
            "이 중에서 최대 5개를 골라 추천해줘. 후보가 있으면 반드시 1개 이상 추천해야 해. "
            "추천 이유는 반드시 해당 이벤트의 실제 제목·장소·설명에 있는 내용만 써. "
            "없는 내용은 지어내지 마. "
            + taste_instruction +
            "\n반드시 아래 JSON 형식으로만 응답해:\n"
            '{"message": "대화형 소개 문장", "recommendations": [{"index": 1, "title": "후보 이벤트 제목 그대로", "reason": "추천 이유"}]}'
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
    start = raw.find("{")
    end = raw.rfind("}") + 1
    try:
        data = json.loads(raw[start:end]) if start != -1 else {}
    except json.JSONDecodeError:
        return {"message": raw.strip(), "events": []}

    events = []
    for rec in data.get("recommendations", []):
        idx = rec.get("index", 0) - 1
        if not (0 <= idx < len(candidates)):
            continue
        ev = candidates[idx]
        llm_title = rec.get("title", "")
        # 타이틀 불일치 시 실제 해당 이벤트 탐색
        if llm_title and llm_title not in ev.title and ev.title not in llm_title:
            matched = next(
                (c for c in candidates if llm_title in c.title or c.title in llm_title),
                None
            )
            if matched:
                ev = matched
            else:
                continue
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

    if not events:
        return {
            "message": "딱 맞는 이벤트를 못 찾겠어요 😅 장르나 아티스트, 원하는 지역을 더 알려주시면 더 잘 찾아드릴게요!",
            "events": [],
        }
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
