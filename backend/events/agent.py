"""
이벤트 에이전트
입력: { query, genres, artists, mood }
출력: [ { title, location, date, thumbnail_url, detail_url, description, reason } ]
"""

import json
from datetime import date

import chromadb
from openai import OpenAI
from django.conf import settings
from django.db.models import Q, Case, When, IntegerField, Value
from django.utils import timezone

from events.models import Event

client = OpenAI(api_key=settings.OPENAI_API_KEY)

# ChromaDB 초기화 (없으면 벡터 검색 비활성화)
try:
    _chroma = chromadb.PersistentClient(path=str(settings.BASE_DIR / "chroma_db"))
    _collection = _chroma.get_collection("events")
except Exception:
    _collection = None

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

STOP_WORDS = {
    '팝업', '추천', '해줘', '알려줘', '보여줘', '있어', '어디', '뭐', '좀', '이번', '주변',
    '좋아하는', '좋아하는데', '좋아해', '보고싶어', '보고싶다', '원하는', '원해',
    '추천해줄래', '추천해줘', '찾아줘', '알고싶어', '궁금해', '해줄래', '줄래', '주세요',
}

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

# 사용자 입력 장르 → DB music_genre / new_sub_category 정규화
GENRE_SYNONYMS = {
    "kpop": "K-Pop", "k-pop": "K-Pop", "케이팝": "K-Pop", "k팝": "K-Pop",
    "힙합": "랩/힙합", "hiphop": "랩/힙합", "hip-hop": "랩/힙합", "랩": "랩/힙합",
    "인디": "인디", "indie": "인디", "인디밴드": "인디", "indie band": "인디",
    "팝": "팝", "pop": "팝",
    "락": "록/메탈", "록": "록/메탈", "rock": "록/메탈", "메탈": "록/메탈",
    "재즈": "재즈", "jazz": "재즈",
    "rnb": "R&B", "알앤비": "R&B", "r&b": "R&B",
    "클래식": "클래식", "classical": "클래식",
    "내한": "내한공연", "내한공연": "내한공연",
    "팬미팅": "팬클럽/팬미팅", "팬클럽": "팬클럽/팬미팅",
}

# 이벤트 타입 동의어 → new_main_category
EVENT_TYPE_SYNONYMS = {
    "콘서트": "공연", "라이브": "공연", "공연": "공연",
    "팝업스토어": "팝업스토어", "팝업": "팝업스토어",
    "전시": "전시", "갤러리": "전시", "미술관": "전시",
    "페스티벌": "페스티벌", "축제": "페스티벌",
}


def normalize_genres(raw_genres: list[str]) -> list[str]:
    """LLM이 뽑은 장르를 DB 값으로 정규화"""
    result = []
    for g in raw_genres:
        key = g.lower().strip()
        normalized = GENRE_SYNONYMS.get(key) or GENRE_SYNONYMS.get(g.strip())
        result.append(normalized if normalized else g.strip())
    return list(dict.fromkeys(result))  # 중복 제거


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


def llm_prefilter_candidates(candidates: list, mood: str, exclude_list: list[str]) -> list:
    """LLM의 K-Pop·연예계 지식으로 취향/연령/제외 조건에 맞는 후보만 추림.
    mood나 exclude가 없으면 즉시 원본 반환 (추가 LLM 호출 없음).
    """
    if not candidates or (not mood and not exclude_list):
        return candidates

    titles_text = "\n".join(f"{i+1}. {ev.title}" for i, ev in enumerate(candidates))
    exclude_str = ", ".join(exclude_list) if exclude_list else "없음"

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            max_tokens=150,
            messages=[{
                "role": "user",
                "content": (
                    "다음 이벤트 목록에서 아래 조건에 맞는 것의 번호를 JSON 배열로만 반환해줘.\n"
                    f"조건: {mood}\n"
                    f"제외(절대 포함 금지): {exclude_str}\n\n"
                    f"이벤트:\n{titles_text}\n\n"
                    "너의 K-Pop·연예계 지식으로 아티스트 연령·세대·스타일을 판단해. "
                    "예: '10,20대 아이돌' 조건이면 에픽하이(80년대생)·규현(88년생) 같은 올드 아티스트는 제외.\n"
                    "조건에 맞는 번호 배열만 반환 (예: [2, 4, 5]). 없으면 []."
                )
            }]
        )
        raw = resp.choices[0].message.content.strip()
        start, end = raw.find("["), raw.rfind("]") + 1
        indices = json.loads(raw[start:end]) if start != -1 else []
        filtered = [candidates[i - 1] for i in indices if isinstance(i, int) and 1 <= i <= len(candidates)]
        return filtered if filtered else candidates
    except Exception:
        return candidates


def vector_search(query: str, n_results: int = 20, category: str = None) -> list[Event]:
    """의미 기반 벡터 검색 — 키워드 매칭 실패 시 보완용"""
    if _collection is None:
        return []
    try:
        resp = client.embeddings.create(model="text-embedding-3-small", input=query)
        query_vec = resp.data[0].embedding
        results = _collection.query(query_embeddings=[query_vec], n_results=n_results)
        ids = [int(i) for i in results["ids"][0]]
        today = timezone.localdate()
        qs = Event.objects.filter(id__in=ids).filter(Q(end_date__gte=today) | Q(end_date__isnull=True))
        if category:
            qs = qs.filter(new_main_category=category)
        events = list(qs)
        id_order = {eid: idx for idx, eid in enumerate(ids)}
        events.sort(key=lambda ev: id_order.get(ev.id, 999))
        return events
    except Exception:
        return []


def search_events(query: str, mood: str, limit: int = 20, sub_category_filter: list = None,
                  event_type: str = None, genres: list = None) -> list[Event]:
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

    # 카테고리: 구조화 인텐트 우선, 없으면 키워드 감지
    detected_category = event_type
    if not detected_category:
        for kw, cat in CATEGORY_KEYWORDS.items():
            if kw in query or kw in mood:
                detected_category = cat
                break

    BRAND_KEYWORDS = {'패션', '브랜드', '쇼핑', '명품', '스트릿', '컬렉션'}
    user_wants_brand = any(kw in query or kw in mood for kw in BRAND_KEYWORDS)

    if detected_category:
        active_qs = active_qs.filter(new_main_category=detected_category)
        if detected_category == '전시':
            active_qs = active_qs.exclude(commerciality='브랜드')
        elif detected_category == '팝업스토어' and not user_wants_brand:
            non_brand = active_qs.exclude(commerciality='브랜드')
            brand = active_qs.filter(commerciality='브랜드')
            active_qs = non_brand | brand
    elif not user_wants_brand:
        non_brand = active_qs.exclude(commerciality='브랜드')
        brand = active_qs.filter(commerciality='브랜드')
        active_qs = non_brand | brand

    # 장르별 DB Q 필터 — 실제 DB 값(sub_category 기준)에 맞춰 매핑
    # 멜론 콘서트(91개)는 메타데이터 없지만 대부분 K-Pop 아티스트 → K-Pop 후보에 포함
    if genres:
        genre_filter = Q()
        for g in genres:
            if g == 'K-Pop':
                # 팬미팅 + 멜론 콘서트(K-Pop 아티스트 위주) + 내한공연
                genre_filter |= (
                    Q(sub_category='팬클럽/팬미팅') |
                    Q(sub_category='내한공연') |
                    (Q(source='melon') & Q(sub_category='콘서트'))
                )
            elif g == '팬클럽/팬미팅':
                genre_filter |= Q(sub_category='팬클럽/팬미팅')
            elif g == '인디':
                genre_filter |= Q(sub_category='인디')
            elif g == '내한공연':
                genre_filter |= Q(sub_category='내한공연')
            elif g == '랩/힙합':
                genre_filter |= (
                    Q(sub_category='랩/힙합') |
                    Q(music_genre__icontains='힙합') |
                    Q(title__icontains='힙합')
                )
            elif g == '클래식':
                genre_filter |= Q(sub_category__icontains='클래식')
            else:
                # 그 외: sub_category·music_genre·title 모두에서 일반 매칭
                genre_filter |= (
                    Q(sub_category__icontains=g) |
                    Q(music_genre__icontains=g) |
                    Q(title__icontains=g)
                )
        active_qs = active_qs.filter(genre_filter)

    # 공연 우선순위 — 실제 DB 값(sub_category·source) 기준으로 재정렬
    # 0: 팬미팅  1: 멜론/야놀자 콘서트(K-Pop 아티스트 다수)  2: 기타  3: 인디  4: dayforyou(뮤지컬/연극 등)
    if detected_category == '공연':
        active_qs = active_qs.annotate(
            concert_priority=Case(
                When(sub_category='팬클럽/팬미팅', then=Value(0)),
                When(sub_category='내한공연', then=Value(1)),
                When(source='melon', then=Value(1)),
                When(source='yanolja', then=Value(1)),
                When(sub_category='인디', then=Value(3)),
                When(source='dayforyou', then=Value(4)),
                default=Value(2),
                output_field=IntegerField(),
            )
        )
        order_fields = ['concert_priority', 'start_date']
    else:
        order_fields = ['start_date']

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
            return list(qs.order_by(*order_fields)[:limit])

    # 2단계: 위치만
    if detected_areas:
        qs = active_qs.filter(loc_filter)
        if qs.exists():
            return list(qs.order_by(*order_fields)[:limit])

    # 3단계: 키워드만
    if non_area_keywords:
        qs = active_qs.filter(kw_filter)
        if qs.exists():
            return list(qs.order_by(*order_fields)[:limit])

    # 최종 폴백: 장르·카테고리 조건은 유지한 채 키워드/위치 조건만 제거
    # (키워드가 DB에 없는 선호 표현일 때도 장르·카테고리 기반 결과 반환)
    return list(active_qs.order_by(*order_fields)[:limit])


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

위 후보 이벤트 중 사용자 취향과 실질적으로 관련 있는 이벤트만 최대 3개 선정하세요.
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
    """쿼리에서 구조화된 검색 인텐트 추출"""
    history = "\n".join(f"{m['role']}: {m['content'][:200]}" for m in messages[-4:])
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=400,
        temperature=0,
        messages=[{
            "role": "user",
            "content": (
                f"대화:\n{history}\nuser: {query}\n\n"
                "사용자가 찾는 이벤트 의도를 아래 규칙대로 JSON으로 뽑아줘.\n\n"
                "event_type 규칙:\n"
                "  '공연'·'콘서트'·'라이브'·'쇼'→'공연' / '팝업'·'팝업스토어'→'팝업스토어'\n"
                "  '전시'·'갤러리'·'미술관'→'전시' / '페스티벌'·'축제'·'풀파티'→'페스티벌'\n"
                "  해당 없으면 null. '공연'과 '페스티벌' 절대 혼동 금지.\n\n"
                "genres: 아래 유효값 중 가장 가까운 것으로 매핑. 없으면 [].\n"
                "  유효값: K-Pop, 랩/힙합, 인디, 팝, 록/메탈, 재즈, R&B, 클래식, 내한공연, 팬클럽/팬미팅\n"
                "  예: 'kpop'·'케이팝'→'K-Pop', '인디밴드'→'인디', '힙합'→'랩/힙합', '팬미팅'→'팬클럽/팬미팅'\n\n"
                "keywords: 이벤트 제목·태그에 등장할 만한 구체적 단어만 (예: '야외', '아트페어', '단독').\n"
                "  '좋아하는'·'보고싶어'·'추천해줄래' 등 선호·의도 표현은 절대 포함 금지. 없으면 ''.\n\n"
                "mood: 사용자가 표현한 취향·감성·선호·연령대 요약 (예: 'kpop 팬', '10,20대 아이돌 선호', '감성적 분위기'). 없으면 ''.\n\n"
                "exclude: 사용자가 명시적으로 거부·제외한 아티스트/이벤트명 목록.\n"
                "  거부 신호: '~빼고', '~말고', '~는 싫어', '~너무 늙었어', '~말고 다른 거', '~ 말고'\n"
                "  ※ 직전 추천(assistant 메시지)에 나온 이벤트를 사용자가 부정적으로 언급하면 그 이벤트의 아티스트명·키워드를 넣어.\n"
                "  예: 사용자가 '규현, 에픽하이 너무 늙었잖아' → ['규현', '에픽하이']\n"
                "  없으면 [].\n\n"
                "location: 언급된 지역명(홍대, 성수 등). 없으면 null.\n\n"
                "장르·이벤트 종류 힌트가 하나라도 있으면 action=search. "
                "아무 맥락 없이 '추천해줘'만이면 action=ask.\n\n"
                "반드시 아래 형식 중 하나로만 답해:\n"
                '{"action":"search","event_type":"공연","genres":["K-Pop"],"keywords":"","mood":"10,20대 아이돌 선호","exclude":["규현","에픽하이"],"location":null}\n'
                '{"action":"ask","message":"질문"}'
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
    intent = json.loads(raw[start:end])

    # 장르 정규화
    if intent.get("genres"):
        intent["genres"] = normalize_genres(intent["genres"])

    # event_type 정규화
    raw_type = intent.get("event_type") or ""
    if raw_type:
        intent["event_type"] = EVENT_TYPE_SYNONYMS.get(raw_type, raw_type) or None

    return intent


def chat(messages: list[dict], query: str) -> dict:
    """대화 맥락을 유지하며 이벤트 추천"""
    intent = extract_search_intent(messages, query)
    if intent.get("action") == "ask":
        return {"message": intent["message"], "events": []}

    event_type = intent.get("event_type")
    genres = intent.get("genres") or []
    intent_mood = intent.get("mood", "")  # 선호 표현 (DB 검색 아닌 LLM 컨텍스트용)
    exclude_list = intent.get("exclude") or []  # 사용자가 거부한 아티스트·키워드
    # keywords만 DB 검색어로 사용. 의도가 잡혔으면 원본 쿼리 통째로 넘기지 않음
    search_query = intent.get("keywords") or ("" if (event_type or genres) else query)

    # 위치: 구조화 인텐트 우선, 없으면 원본 쿼리에서 감지
    intent_location = intent.get("location")
    detected_areas = ([intent_location] if intent_location else []) or [area for area in SEOUL_AREAS if area in query]
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

    # mood/제외 조건이 있으면 더 많은 후보 확보 (사전 필터링 여유분)
    search_limit = 30 if (intent_mood or exclude_list) else 20

    sub_cat_filter = detect_subcategory_filter(query, search_query)
    candidates = search_events(
        query=search_query, mood="",
        sub_category_filter=sub_cat_filter,
        event_type=event_type,
        genres=genres,
        limit=search_limit,
    )

    # 장르 필터 결과 없으면 장르 조건 완화 후 재시도
    if not candidates and genres:
        candidates = search_events(
            query=search_query, mood="",
            sub_category_filter=sub_cat_filter,
            event_type=event_type,
            genres=[],
            limit=search_limit,
        )

    # 키워드 검색 결과 없으면 벡터 검색으로 보완 (카테고리 필터 유지)
    if not candidates:
        candidates = vector_search(query, category=event_type)

    # LLM 사전 필터링: K-Pop 지식으로 취향/연령/제외 조건에 맞는 후보만 추림
    # mood나 exclude가 없으면 추가 LLM 호출 없이 건너뜀
    candidates = llm_prefilter_candidates(candidates, intent_mood, exclude_list)

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

    combined_taste = ", ".join(filter(None, [intent_mood, user_taste]))
    taste_instruction = (
        f"\n사용자 취향 힌트: {combined_taste}\n"
        "취향을 반영해서 추천하고, message에 취향과 연결된 한 문장을 넣어줘."
        if combined_taste else ""
    )
    exclude_instruction = (
        f"\n⚠️ 절대 추천 금지: {', '.join(exclude_list)} — 사용자가 명시적으로 거부함. "
        "이 키워드가 title에 포함된 이벤트는 절대 추천하지 마."
        if exclude_list else ""
    )

    llm_messages = [
        {"role": "system", "content": (
            SYSTEM_PROMPT +
            "\n반드시 캐주얼하고 친근한 존댓말(~요, ~세요, ~드릴게요)로만 응답해. 절대 반말 쓰지 마. "
            "아래 후보 이벤트들 중 최대 3개를 골라 추천해줘. 후보가 있으면 반드시 1개 이상 추천해야 해. "
            "후보 이벤트 중 최대 3개를 골라 추천해줘. 후보가 있으면 반드시 1개 이상 추천해. "
            "사용자 취향(mood)을 최대한 반영해서 가장 잘 맞는 것 우선으로 골라. "
            "추천 이유는 이벤트의 실제 제목·장소·설명에 있는 내용만 써. 없는 내용 지어내지 마. "
            + taste_instruction + exclude_instruction +
            "\n반드시 아래 JSON 형식으로만 응답해. message는 추천 이유 없이 짧은 감탄/안내 문장 하나만:\n"
            '{"message": "딱 맞는 공연 찾았어요!", "recommendations": [{"index": 1, "title": "후보 이벤트 제목 그대로", "reason": "추천 이유"}]}'
        )}
    ] + [
        {"role": m["role"], "content": m["content"]}
        for m in messages[-6:]
    ] + [{
        "role": "user",
        # 원본 쿼리 대신 구조화된 의도만 전달 → LLM의 쿼리 파라프레이즈 방지
        "content": f"[검색 조건] 카테고리: {event_type or '전체'}, 장르: {', '.join(genres) if genres else '전체'}\n\n[후보 이벤트 목록]\n{events_context}"
    }]

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=1500,
        temperature=0,
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
        # LLM이 자체적으로 안내 메시지를 줬으면 그걸 우선 사용 (취향과 연결된 자연스러운 안내)
        llm_msg = (data.get("message") or "").strip()
        return {
            "message": llm_msg or "딱 맞는 이벤트를 못 찾겠어요 😅 장르나 아티스트, 원하는 지역을 더 알려주시면 더 잘 찾아드릴게요!",
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
