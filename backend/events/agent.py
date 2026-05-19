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

SYSTEM_PROMPT = """너는 K-Dive 서비스의 이벤트 큐레이터다.
서울의 팝업스토어·전시·공연·페스티벌 중 사용자 요청과 맞는 후보를 골라 '왜 이게 좋은지'를 자연스럽게 설명한다.

철칙:
1) 후보 데이터(description, hashtags, mood_tags)에 명시되지 않은 사실은 절대 만들지 않는다.
   작가·브랜드·아티스트의 외부 정보도 추측 금지.
2) 추천 이유는 이벤트의 '컨셉/의도'를 먼저 드러내고, 그 다음 사용자 요청과 연결한다.
3) 기계적·체크리스트형 표현 금지. "카테고리 부합", "키워드 매칭", "당신이 좋아하시는 'X'" 같은
   메타적 설명 대신 이벤트의 실제 내용으로 설득한다.
4) 친근한 존댓말(~요, ~세요, ~드릴게요) 유지. 반말(~해, ~야, ~줄게) 금지.
5) description이 빈약한 콘서트는 무리해서 길게 쓰지 말고 사실 위주로 짧게."""


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
    '전시회': '전시',
    # 페스티벌 & 약어
    '페스티벌': '페스티벌',
    '페스타': '페스티벌',
    '락페': '페스티벌',
    '락 페스티벌': '페스티벌',
    '재페': '페스티벌',
    '재즈 페스티벌': '페스티벌',
    '뮤직페스티벌': '페스티벌',
    '뮤직 페스티벌': '페스티벌',
    '뮤페': '페스티벌',
    'EDM 페스티벌': '페스티벌',
    'festival': '페스티벌',
    'FESTIVAL': '페스티벌',
    # 공연 & 약어
    '공연': '공연',
    '콘서트': '공연',
    '내한공연': '공연',
    '내한': '공연',
    '팬미팅': '공연',
    '팬콘': '공연',
    # 기타
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


def search_events(
    query: str,
    mood: str,
    limit: int = 20,
    sub_category_filter: list = None,
    raw_query: str = "",
    category_override: str = None,
    performance_type: str = None,
) -> list[Event]:
    """
    단계별 검색:
    1단계) 위치 + 키워드 모두 매칭
    2단계) 키워드만 매칭 (위치 조건 완화)
    3단계) 진행 중인 이벤트 최신순 (완전 폴백)

    raw_query: LLM 가공 전 원본 사용자 발화. 카테고리 감지 fallback에 사용.
    category_override: LLM이 직접 분류한 카테고리. 있으면 substring 매칭 건너뜀.
    performance_type: 공연 세부유형 ('음악'|'연극'|'뮤지컬'|'클래식'). 공연 카테고리 안에서 추가 필터링.
    """
    today = timezone.localdate()
    active_qs = Event.objects.filter(
        Q(end_date__gte=today) | Q(end_date__isnull=True)
    )

    # 카테고리 결정: LLM 분류 결과 우선, 없으면 substring 매칭 fallback
    detected_category = category_override
    if not detected_category:
        detection_text = f"{query} {mood} {raw_query}"
        for kw, cat in CATEGORY_KEYWORDS.items():
            if kw in detection_text:
                detected_category = cat
                break

    if detected_category:
        active_qs = active_qs.filter(new_main_category=detected_category)
        if detected_category == '전시':
            active_qs = active_qs.exclude(commerciality='브랜드')
        # 공연 세부유형 필터 (콘서트 vs 연극 vs 뮤지컬 vs 클래식)
        if detected_category == '공연' and performance_type:
            if performance_type == '음악':
                # 음악 공연: new_sub_category='음악' 또는 sub_category가 음악 관련
                active_qs = active_qs.filter(
                    Q(new_sub_category='음악')
                    | Q(sub_category__icontains='콘서트')
                    | Q(sub_category__icontains='랩/힙합')
                    | Q(sub_category__icontains='내한공연')
                    | Q(sub_category__icontains='인디')
                    | Q(sub_category__icontains='팬클럽')
                    | Q(sub_category__icontains='페스티벌')
                )
            elif performance_type == '연극':
                active_qs = active_qs.filter(sub_category__icontains='연극')
            elif performance_type == '뮤지컬':
                active_qs = active_qs.filter(sub_category__icontains='뮤지컬')
            elif performance_type == '클래식':
                active_qs = active_qs.filter(
                    Q(sub_category__icontains='클래식')
                    | Q(sub_category__icontains='오페라')
                    | Q(sub_category__icontains='발레')
                )

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
        mood_tags = getattr(ev, "new_mood_tags", None) or getattr(ev, "mood_tags", []) or []
        audience_tags = getattr(ev, "new_audience_tags", None) or getattr(ev, "audience_tags", []) or []
        category = getattr(ev, "new_main_category", None) or getattr(ev, "main_category", "") or ""
        subcategory = getattr(ev, "new_sub_category", None) or getattr(ev, "sub_category", "") or ""
        events_str += (
            f"{i}. [{ev.title}]\n"
            f"   카테고리: {category} / {subcategory}\n"
            f"   장소: {ev.location}\n"
            f"   기간: {date_str}\n"
            f"   분위기: {', '.join(mood_tags[:5]) if mood_tags else '-'}\n"
            f"   타겟: {', '.join(audience_tags[:5]) if audience_tags else '-'}\n"
            f"   설명: {ev.description[:500]}\n"
            f"   해시태그: {' '.join(ev.hashtags[:5])}\n\n"
        )

    return f"[사용자 취향]\n{pref_str}\n\n[후보 이벤트]\n{events_str}"


def curate_with_llm(events: list[Event], preference: dict, query: str) -> list[dict]:
    """LLM으로 취향 기반 추천 이유 생성"""
    if not events:
        return []

    context = build_context(events, preference)

    prompt = f"""[사용자 질문] "{query}"

{context}

위 후보 중 사용자 요청에 가장 잘 맞는 이벤트를 최대 5개 고르세요.

각 이벤트에 대해 다음 순서로 사고하세요:
  1) [의도] 이 이벤트가 '왜 열리는지/어떤 컨셉인지' description에서 추출해 한 문장으로 정리
  2) [매칭] 사용자 질문/취향과 자연스럽게 이어지는 포인트를 description·태그 안에서 찾기
  3) [추천 이유] 의도와 매칭을 자연스러운 문장으로 엮기 (2-3문장, 존댓말)

**작성 규칙:**
- description, hashtags, mood_tags에 실제로 있는 내용만 사용 (지어내기 금지)
- 어색한 표현 금지: "당신이 좋아하시는 'X'", "~카테고리에 부합", "평소 선호하시는 동선"
- 키워드를 따옴표로 박아넣지 않기 → 자연스러운 문장으로 녹이기
- 작가명/브랜드명/컨셉 등 구체 정보를 우선 활용
- "~한 분께 잘 맞아요" 같은 부드러운 연결 사용
- 콘서트는 description이 빈약하므로 제목·아티스트·장소·날짜 중심으로 짧게

억지로 연결하지 마세요. 관련 이벤트가 없으면 빈 배열을 반환하세요.
반드시 JSON만 출력하세요:

[
  {{
    "index": 1,
    "intent": "이벤트의 의도/컨셉 한 문장",
    "match_points": ["매칭 근거 1", "매칭 근거 2"],
    "reason": "2-3문장의 자연스러운 추천 이유"
  }}
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
    """
    사용자 발화를 구조화된 검색 의도로 분류한다.

    반환 예시:
      검색 가능:
        {"action": "search",
         "category": "페스티벌" | "공연" | "전시" | "팝업스토어" | "박람회" | null,
         "performance_type": "음악" | "연극" | "뮤지컬" | "클래식" | null,  # category="공연"일 때만 의미 있음
         "genre_hint": "락" | "재즈" | "K-Pop" | "아이돌" | ... | null,
         "location": "성수" | "홍대" | ... | null,
         "keywords": "추가 검색어"}
      질문 필요:
        {"action": "ask", "message": "..."}

    LLM이 카테고리/세부유형을 직접 분류하므로 새 약어/표현에 자동 대응.
    """
    history = "\n".join(f"{m['role']}: {m['content'][:200]}" for m in messages[-4:])
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=300,
        response_format={"type": "json_object"},
        messages=[{
            "role": "user",
            "content": (
                f"대화:\n{history}\nuser: {query}\n\n"
                "사용자 발화의 검색 의도를 분류해서 JSON으로만 답해.\n\n"
                "[action 결정]\n"
                "- 사용자가 조금이라도 힌트(카테고리/장르/지역/분위기)를 줬으면 'search'\n"
                "- 첫 마디부터 '추천해줘'처럼 완전히 비어있을 때만 'ask'\n"
                "- ask일 때 message는 캐주얼한 존댓말. 예: '어떤 거 찾으세요? 팝업, 전시, 공연 등 다양하게 있어요!'\n\n"
                "[category 분류 - 'search'일 때만]\n"
                "반드시 아래 중 하나 또는 null:\n"
                "- '전시' : 전시, 전시회, 미술관, 갤러리 등\n"
                "- '공연' : 콘서트, 연극, 뮤지컬, 클래식, 내한, 팬콘, 팬미팅 등 모든 공연\n"
                "- '페스티벌' : 페스티벌, 페스타, 락페, 재페, 뮤페, EDM 페스, rock fest 등\n"
                "- '팝업스토어' : 팝업, 팝업스토어\n"
                "- '박람회' : 박람회, 엑스포\n"
                "- null : 카테고리 단서가 전혀 없을 때\n\n"
                "[performance_type - category='공연'일 때만 채워라. 그 외엔 null]\n"
                "공연 안에서 어떤 종류인지 구체화:\n"
                "- '음악' : 콘서트, 아이돌, K-Pop, 힙합, 재즈, 락밴드, 인디, 발라드, 내한공연, 팬콘, 팬미팅 등 음악 공연\n"
                "- '연극' : 연극\n"
                "- '뮤지컬' : 뮤지컬\n"
                "- '클래식' : 클래식, 오페라, 발레\n"
                "- null : 공연 종류가 명시 안 됨\n"
                "예: '아이돌 콘서트' → category='공연', performance_type='음악'\n"
                "예: '재즈 공연' → category='공연', performance_type='음악'\n"
                "예: '뮤지컬 보고싶어' → category='공연', performance_type='뮤지컬'\n\n"
                "[genre_hint - 음악 장르나 전시/팝업 테마]\n"
                "예: 락페 → genre_hint='락', 아이돌 콘서트 → genre_hint='아이돌'\n"
                "예: 패션 팝업 → genre_hint='패션'\n"
                "없으면 null.\n\n"
                "[location - 서울/경기 지역명만]\n"
                "예: '성수', '홍대', '강남', '잠실' 등. 일반 단어('서울')는 null.\n\n"
                "[keywords - 위에 들어가지 않은 추가 검색어]\n"
                "예: 분위기, 아티스트명, 브랜드명 등. 없으면 빈 문자열.\n\n"
                "반환 예시:\n"
                '{"action":"search","category":"공연","performance_type":"음악","genre_hint":"아이돌","location":null,"keywords":""}\n'
                '{"action":"search","category":"페스티벌","performance_type":null,"genre_hint":"락","location":null,"keywords":""}\n'
                '{"action":"search","category":"공연","performance_type":"뮤지컬","genre_hint":null,"location":null,"keywords":""}\n'
                '{"action":"ask","message":"어떤 거 찾으세요? 팝업, 전시, 공연 등 다양하게 있어요!"}'
            )
        }]
    )
    raw = resp.choices[0].message.content.strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {"action": "search", "category": None, "performance_type": None, "genre_hint": None, "location": None, "keywords": query}
    if data.get("action") == "search":
        data.setdefault("category", None)
        data.setdefault("performance_type", None)
        data.setdefault("genre_hint", None)
        data.setdefault("location", None)
        data.setdefault("keywords", "")
    return data


def chat(messages: list[dict], query: str) -> dict:
    """대화 맥락을 유지하며 이벤트 추천"""
    intent = extract_search_intent(messages, query)
    if intent.get("action") == "ask":
        return {"message": intent["message"], "events": []}

    # LLM이 분류한 구조화 의도 (카테고리, 공연 세부유형, 장르, 지역, 부가 키워드)
    category_override = intent.get("category")  # '페스티벌' | '공연' | '전시' | '팝업스토어' | '박람회' | None
    performance_type = intent.get("performance_type")  # '음악' | '연극' | '뮤지컬' | '클래식' | None (category='공연'일 때만)
    genre_hint = intent.get("genre_hint") or ""
    intent_location = intent.get("location") or ""
    extra_keywords = intent.get("keywords") or ""

    # 검색용 키워드 문자열: 장르 힌트와 추가 키워드 합치기
    search_query = " ".join(filter(None, [genre_hint, extra_keywords])).strip() or query

    # 위치는 LLM이 뽑은 지역 우선, 없으면 원본에서 감지
    detected_areas = []
    if intent_location and intent_location in SEOUL_AREAS:
        detected_areas = [intent_location]
    else:
        detected_areas = [area for area in SEOUL_AREAS if area in query]
    broad_location = '서울' if '서울' in query and not detected_areas else ""
    location_str = detected_areas[0] if detected_areas else (broad_location or "서울")

    # 팝업 카테고리인데 세부 분류 없음 → 카테고리 선택 화면
    if category_override == '팝업스토어' and not detect_subcategory_filter(query, search_query):
        categories = get_available_categories(detected_areas, broad_location)
        return {
            "message": f"{location_str} 팝업이 정말 다양해요! 어떤 종류 팝업 관심 있으세요?",
            "events": [],
            "categories": categories,
            "category_type": "popup",
            "location": location_str,
        }

    sub_cat_filter = detect_subcategory_filter(query, search_query)
    candidates = search_events(
        query=search_query,
        mood="",
        sub_category_filter=sub_cat_filter,
        raw_query=query,
        category_override=category_override,
        performance_type=performance_type,
    )

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
            "\n\n[현재 작업]\n"
            "후보 이벤트는 이미 사용자 검색어와 매칭됐어. 이 중 최대 5개를 골라 추천해.\n"
            "후보가 있으면 반드시 1개 이상 추천. 관련 없으면 빈 배열.\n\n"
            "[추천 이유 작성 절차 - 각 이벤트마다]\n"
            "1) [의도] 이 이벤트가 '왜 열리는지/어떤 컨셉인지' description에서 추출해 한 문장으로 정리\n"
            "2) [매칭] 사용자 질문/취향과 자연스럽게 이어지는 포인트를 description·태그 안에서 찾기\n"
            "3) [이유] 의도와 매칭을 자연스러운 문장으로 엮어 2-3문장의 reason 작성\n\n"
            "[금지 표현]\n"
            "- \"당신이 좋아하시는 'X'\", \"~카테고리에 부합\", \"평소 선호하시는 동선\"\n"
            "- 키워드를 따옴표로 박아넣기 → 자연스러운 문장으로 녹이기\n\n"
            "[권장 표현]\n"
            "- 작가명/브랜드명/컨셉 등 구체 정보 우선 사용\n"
            "- \"~한 분께 잘 맞아요\" 같은 부드러운 연결\n"
            "- 콘서트(공연)는 description 빈약하니 제목·아티스트·장소·날짜 위주로 짧게\n"
            + taste_instruction +
            "\n반드시 아래 JSON 형식으로만 응답해:\n"
            '{"message": "대화형 소개 문장", "recommendations": [{"index": 1, "title": "후보 이벤트 제목 그대로", "intent": "이벤트의 의도/컨셉 한 문장", "reason": "2-3문장의 자연스러운 추천 이유"}]}'
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
