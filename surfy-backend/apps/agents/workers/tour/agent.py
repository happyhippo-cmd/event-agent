"""
Tour Worker Agent — entry node
흐름: 자연어 입력 → [LLM] 위치+취향 추출 → DB 조회
      DB 있으면 → DB 주변 검색 → [LLM] 선별 → JSON
      DB 없으면 → Kakao API 검색 → [LLM] 선별 → JSON
"""

import os
import sqlite3
import math
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[4]
load_dotenv(BASE_DIR / ".env")

DB_PATH       = os.getenv("TOURISM_DB_PATH", str(BASE_DIR / "data" / "merged_tourism.db"))
KAKAO_API_KEY = os.getenv("KAKAO_REST_API_KEY")
KAKAO_HEADERS = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}
KAKAO_KW_URL  = "https://dapi.kakao.com/v2/local/search/keyword.json"
KAKAO_CAT_URL = "https://dapi.kakao.com/v2/local/search/category.json"

_client = None


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI

        _client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _client

# AT4: 관광명소, CT1: 문화시설
KAKAO_TOURIST_CATEGORIES = ["AT4", "CT1"]

ONBOARDING_FIXED_PLACES = ("경복궁", "남산서울타워")
GENERAL_AREA_HINTS = {
    "서울": ("서울", "서울특별시"),
    "서울특별시": ("서울", "서울특별시"),
    "한국": ("서울", "서울특별시"),
    "대한민국": ("서울", "서울특별시"),
}
GENERAL_TOUR_TERMS = ("꼭", "대표", "필수", "처음", "여행", "명소", "관광지", "가야")
GENERAL_MUST_VISIT_PLACES = (
    "경복궁", "남산서울타워", "북촌한옥마을", "창덕궁", "덕수궁",
    "인사동", "명동거리", "DDP", "동대문디자인플라자", "광장시장",
)
MUSIC_PLACE_SEEDS = {
    "청춘": ("서울숲", "한강", "연남", "공원"),
    "선명": ("광화문", "서울숲", "한강"),
    "애틋": ("정동", "덕수궁", "남산", "돌담길"),
    "시네마": ("덕수궁", "정동", "남산", "극장"),
    "강렬": ("홍대", "성수", "광화문", "DDP"),
    "대담": ("압구정", "이태원", "강남", "전망대"),
    "디지털": ("DDP", "코엑스", "동대문", "강남"),
    "쿨": ("성수", "한남", "압구정", "강남"),
    "레트로": ("인사동", "익선동", "을지로", "시장"),
    "벅찬": ("한강", "남산", "서울광장", "광화문"),
    "키치": ("성수", "홍대", "연남", "소품"),
    "발랄": ("연남", "홍대", "성수", "공원"),
    "몰입": ("부암", "숲", "한강", "북서울"),
    "애절": ("정동", "남산", "한강", "부암"),
    "감각": ("성수", "한남", "DDP", "압구정"),
    "리드미컬": ("한강", "성수", "동대문", "공연"),
    "블루": ("청계천", "석촌", "한강", "물"),
    "폭발": ("잠실", "광화문", "DDP", "경기장"),
    "영웅": ("남산", "경복궁", "광화문", "전망대"),
    "반짝": ("남산", "롯데월드타워", "야경", "광화문"),
    "따뜻": ("선유도", "서울숲", "한강", "공원"),
    "달콤": ("연남", "서울숲", "디저트", "카페거리"),
    "몽환": ("서울숲", "아쿠아리움", "한강", "온실"),
    "찬란": ("광화문", "남산", "전망대", "서울광장"),
    "청량": ("한강", "노들섬", "서울숲", "공원"),
    "빈티지": ("부암", "정동", "인사동", "을지로"),
    "희망": ("서울광장", "여의도", "한강", "공원"),
    "극적": ("청계천", "대교", "문화비축기지", "야경"),
    "서정": ("성북", "연희", "경의선숲길", "정동"),
    "담담": ("망원", "서촌", "한강", "골목"),
    "경쾌": ("명동", "한강", "극장", "거리"),
    "싱그": ("서울숲", "연남", "난지", "공원"),
    "웅장": ("잠실", "광화문", "DDP", "경기장"),
    "사이키": ("문래", "을지로", "노들섬", "공연"),
    "도회": ("압구정", "한남", "성수", "강남"),
    "축제": ("강남", "코엑스", "잠실", "광장"),
    "글로벌": ("이태원", "성수", "한강", "문화"),
}

# ── LLM 시스템 프롬프트 ───────────────────────────────────────────────────────

INTENT_SYSTEM_PROMPT = """
당신은 한국 관광지 추천 어시스턴트입니다.
사용자의 메시지(한국어 또는 영어)를 분석하여 여행 의도를 구조화된 형태로 추출하세요.

반드시 아래 형식의 JSON만 반환하세요:
{
  "location": "한국어 장소명 (예: 경복궁, 한강공원, 광화문)",
  "preferences": ["사용자의 선호 키워드 (한국어), 예: 역사, 자연, 가족, 힐링"],
  "category_keywords": ["DB 필터용 카테고리 키워드, 아래 목록에서 선택: 문화유적, 고궁, 박물관, 미술관, 공원, 산, 숲, 계곡, 동물원, 테마파크, 전망대, 절,사찰, 등산로, 카페거리, 수목원, 도보여행"]
}

규칙:
- location은 구체적인 한국어 장소명만 입력하세요 (설명 없이)
- 선호 정보가 없으면 preferences와 category_keywords는 빈 배열로 반환하세요
- category_keywords는 실제 DB 카테고리에 포함된 문자열과 일치해야 합니다
""".strip()

RANKING_SYSTEM_PROMPT = """
당신은 한국 관광지 추천 전문가입니다.
사용자의 요청과 주변 관광지 목록을 바탕으로, 가장 적합한 장소를 선별하고 순위를 매기세요.

반드시 아래 형식의 JSON만 반환하세요:
{
  "ranked_ids": ["id1", "id2", ...],
  "reason": "선별 기준을 한국어로 간단히 설명"
}

규칙:
- ranked_ids는 제공된 장소 목록의 ID만 사용하세요 (최대 5개)
- 사용자의 선호에 얼마나 잘 맞는지를 기준으로 순서를 정하세요
- 선호 정보가 없으면 카테고리 다양성과 거리를 기준으로 순위를 매기세요
""".strip()


# ── LLM ① : 위치 + 취향 구조화 추출 ─────────────────────────────────────────
def extract_intent_llm(user_message: str) -> dict:
    response = _get_client().chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": INTENT_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )
    return json.loads(response.choices[0].message.content)


# ── LLM ② : 후보 장소 선별·재정렬 ───────────────────────────────────────────
def rank_places_llm(places: list[dict], user_message: str,
                    preferences: list[str]) -> tuple[list[dict], str]:
    summaries = [
        {
            "id": p["id"],
            "name": p["place_name"],
            "category": p.get("category_name", ""),
            "distance_km": p["distance_km"],
            "overview": (p.get("overview") or "")[:120],
        }
        for p in places
    ]
    user_content = (
        f"User request: {user_message}\n"
        f"Preferences: {preferences}\n\n"
        f"Nearby places:\n{json.dumps(summaries, ensure_ascii=False, indent=2)}"
    )
    response = _get_client().chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": RANKING_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )
    result = json.loads(response.choices[0].message.content)
    ranked_ids = result.get("ranked_ids", [])
    reason = result.get("reason", "")
    id_to_place = {p["id"]: p for p in places}
    ranked = [id_to_place[rid] for rid in ranked_ids if rid in id_to_place]
    return ranked, reason


# ── Haversine 거리 계산 (km) ──────────────────────────────────────────────────
def _haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


# ── DB: 위치명으로 좌표 조회 ──────────────────────────────────────────────────
def get_location_from_db(location_name: str) -> dict:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT place_name, CAST(x AS REAL), CAST(y AS REAL), address_name
        FROM tourists
        WHERE place_name LIKE ? AND x != '' AND y != ''
        LIMIT 1
        """,
        (f"%{location_name}%",),
    )
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "found": True, "source": "db",
            "place_name": row[0], "longitude": row[1],
            "latitude": row[2], "address": row[3],
        }
    return {"found": False}


# ── DB: 좌표 기반 주변 관광지 조회 ───────────────────────────────────────────
def search_nearby_from_db(latitude: float, longitude: float,
                          radius_km: float = 3.0, limit: int = 20,
                          preferences: list[str] | None = None) -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    deg_lat = radius_km / 111.0
    deg_lon = radius_km / (111.0 * math.cos(math.radians(latitude)))

    pref_sql, pref_params = "", []
    if preferences:
        clauses = []
        for kw in preferences:
            clauses.append("category_name LIKE ?")
            pref_params.append(f"%{kw}%")
            clauses.append("overview LIKE ?")
            pref_params.append(f"%{kw}%")
        pref_sql = f"AND ({' OR '.join(clauses)})"

    cursor.execute(
        f"""
        SELECT * FROM tourists
        WHERE CAST(x AS REAL) BETWEEN ? AND ?
          AND CAST(y AS REAL) BETWEEN ? AND ?
          AND x != '' AND y != ''
          {pref_sql}
        """,
        [longitude - deg_lon, longitude + deg_lon,
         latitude - deg_lat, latitude + deg_lat] + pref_params,
    )
    columns = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()
    conn.close()

    results = []
    for row in rows:
        record = dict(zip(columns, row))
        dist = _haversine(latitude, longitude, float(record["y"]), float(record["x"]))
        if dist <= radius_km:
            record["distance_km"] = round(dist, 2)
            results.append(record)

    results.sort(key=lambda r: r["distance_km"])
    return results[:limit]


def search_representative_from_db(
    area: str = "서울",
    preferences: list[str] | None = None,
    limit: int = 20,
) -> list[dict]:
    """Return broad, non-distance tourist picks for pre-trip exploration."""

    area_aliases = GENERAL_AREA_HINTS.get(area, (area,))
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    area_clauses = []
    params: list[str] = []
    for alias in area_aliases:
        area_clauses.extend(["area LIKE ?", "address_name LIKE ?", "road_address_name LIKE ?"])
        params.extend([f"%{alias}%", f"%{alias}%", f"%{alias}%"])

    pref_sql, pref_params = "", []
    if preferences:
        clauses = []
        for kw in preferences:
            clauses.append("category_name LIKE ?")
            pref_params.append(f"%{kw}%")
            clauses.append("overview LIKE ?")
            pref_params.append(f"%{kw}%")
        pref_sql = f"AND ({' OR '.join(clauses)})"

    cursor.execute(
        f"""
        SELECT * FROM tourists
        WHERE place_name IS NOT NULL
          AND place_name != ''
          AND x != ''
          AND y != ''
          AND ({' OR '.join(area_clauses)})
          {pref_sql}
        """,
        params + pref_params,
    )
    columns = [desc[0] for desc in cursor.description]
    rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
    conn.close()

    ranked = []
    for row in rows:
        name = row.get("place_name") or ""
        if not name:
            continue
        score = _representative_score(row)
        ranked.append((score, {**row, "distance_km": None}))

    ranked.sort(key=lambda item: item[0], reverse=True)
    deduped = []
    seen: set[str] = set()
    for _, row in ranked:
        canonical_name = _canonical_representative_name(row.get("place_name") or "")
        if canonical_name in seen:
            continue
        seen.add(canonical_name)
        deduped.append(row)
        if len(deduped) >= limit:
            break
    return deduped


def _representative_score(row: dict) -> int:
    name = row.get("place_name") or ""
    category = row.get("category_name") or ""
    score = 0
    must_score = 0
    for index, must_name in enumerate(GENERAL_MUST_VISIT_PLACES):
        if name == must_name:
            must_score = max(must_score, 200 - index)
        elif must_name in name or name in must_name:
            must_score = max(must_score, 120 - index)
    score += must_score
    if row.get("firstimage"):
        score += 20
    if row.get("source") == "korea":
        score += 8
    if any(term in category for term in ("고궁", "문화유적", "전망대", "테마거리", "공원", "시장")):
        score += 10
    return score


def _canonical_representative_name(name: str) -> str:
    if "DDP" in name or "동대문디자인플라자" in name:
        return "DDP"
    for must_name in GENERAL_MUST_VISIT_PLACES:
        if name == must_name or must_name in name or name in must_name:
            return must_name
    return name


# ── Kakao API: 장소명으로 위치 검색 ──────────────────────────────────────────
def get_location_from_kakao(location_name: str) -> dict:
    try:
        res = requests.get(
            KAKAO_KW_URL, headers=KAKAO_HEADERS,
            params={"query": location_name, "size": 1}, timeout=5,
        )
        res.raise_for_status()
        docs = res.json().get("documents", [])
    except Exception:
        return {"found": False}

    if not docs:
        return {"found": False}

    doc = docs[0]
    return {
        "found": True, "source": "kakao_api",
        "place_name": doc.get("place_name", ""),
        "longitude": float(doc.get("x", 0)),
        "latitude": float(doc.get("y", 0)),
        "address": doc.get("address_name", ""),
    }


# ── Kakao API: 주변 관광지 검색 ──────────────────────────────────────────────
def search_nearby_from_kakao(latitude: float, longitude: float,
                              radius_km: float = 3.0, limit: int = 20) -> list[dict]:
    radius_m = int(radius_km * 1000)
    results, seen_ids = [], set()

    for cat_code in KAKAO_TOURIST_CATEGORIES:
        try:
            res = requests.get(
                KAKAO_CAT_URL, headers=KAKAO_HEADERS,
                params={
                    "category_group_code": cat_code,
                    "x": longitude, "y": latitude,
                    "radius": radius_m, "size": 15, "sort": "distance",
                },
                timeout=5,
            )
            res.raise_for_status()
            docs = res.json().get("documents", [])
        except Exception:
            continue

        for doc in docs:
            pid = doc.get("id", "")
            if pid in seen_ids:
                continue
            seen_ids.add(pid)
            dist_m = doc.get("distance", "0")
            results.append({
                "id": pid, "source": "kakao_api",
                "place_name": doc.get("place_name", ""),
                "phone": doc.get("phone", ""),
                "address_name": doc.get("address_name", ""),
                "road_address_name": doc.get("road_address_name", ""),
                "x": doc.get("x", ""), "y": doc.get("y", ""),
                "category_name": doc.get("category_name", ""),
                "category_group_code": doc.get("category_group_code", ""),
                "category_group_name": doc.get("category_group_name", ""),
                "place_url": doc.get("place_url", ""),
                "overview": None, "firstimage": None, "firstimage2": None,
                "homepage": None, "usetime": None, "restdate": None, "parking": None,
                "distance_km": round(int(dist_m) / 1000, 2) if dist_m else 0.0,
            })

    results.sort(key=lambda r: r["distance_km"])
    return results[:limit]


def recommend_places_for_music_keywords(
    tracks: list[dict],
    per_keyword: int = 3,
    fixed_count: int = 2,
) -> dict:
    """Select onboarding tourist places from the tourism DB for selected music vibes."""

    rows = _load_onboarding_tour_rows()
    used_names: set[str] = set()
    places: list[dict] = []

    for fixed_name in ONBOARDING_FIXED_PLACES[:fixed_count]:
        row = _best_fixed_row(rows, fixed_name, used_names)
        if row:
            used_names.add(row["place_name"])
            places.append(
                _onboarding_place_from_row(
                    row=row,
                    source_keyword="Korea essential",
                    label="필수",
                    category="must",
                    reason="처음 한국을 여행할 때 동선에 넣기 좋은 대표 장소예요.",
                )
            )

    for track in tracks:
        keyword = _track_keyword(track)
        terms = _terms_for_track(track)
        candidates = _rank_rows_for_terms(rows, terms, used_names)[:per_keyword]
        for row in candidates:
            used_names.add(row["place_name"])
            places.append(
                _onboarding_place_from_row(
                    row=row,
                    source_keyword=keyword,
                    label="음악",
                    category="keyword",
                    reason=f"{keyword} 무드와 이어지는 관광지 후보예요.",
                )
            )

    return {"status": "ok", "places": places}


def _load_onboarding_tour_rows() -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT id, place_name, category_name, area, address_name, road_address_name,
               x, y, firstimage, firstimage2, place_url, source
        FROM tourists
        WHERE place_name IS NOT NULL
          AND place_name != ''
          AND x != ''
          AND y != ''
        """
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def _track_keyword(track: dict) -> str:
    return str(track.get("vibe") or track.get("keyword") or track.get("title") or "음악").strip()


def _terms_for_track(track: dict) -> list[str]:
    keyword = _track_keyword(track)
    terms = [
        item.strip()
        for chunk in keyword.replace("/", "·").split("·")
        for item in (chunk.strip(),)
        if item.strip()
    ]
    for place in track.get("seed_places") or []:
        if isinstance(place, str):
            terms.append(place)
        elif place.get("name"):
            terms.append(place["name"])

    expanded = list(terms)
    for term in terms:
        normalized = term.replace("한", "").replace("의", "")
        for marker, seeds in MUSIC_PLACE_SEEDS.items():
            if marker in term or marker in normalized:
                expanded.extend(seeds)
    return list(dict.fromkeys(expanded))


def _best_row_for_terms(rows: list[dict], terms: list[str], used_names: set[str]) -> dict | None:
    ranked = _rank_rows_for_terms(rows, terms, used_names)
    return ranked[0] if ranked else None


def _best_fixed_row(rows: list[dict], fixed_name: str, used_names: set[str]) -> dict | None:
    exact = [
        row
        for row in rows
        if row.get("place_name") == fixed_name and row.get("place_name") not in used_names
    ]
    if exact:
        exact.sort(key=lambda row: 1 if row.get("firstimage") else 0, reverse=True)
        return exact[0]
    return _best_row_for_terms(rows, [fixed_name], used_names)


def _rank_rows_for_terms(rows: list[dict], terms: list[str], used_names: set[str]) -> list[dict]:
    scored = []
    for row in rows:
        name = row.get("place_name") or ""
        if name in used_names:
            continue
        haystack = " ".join(
            str(row.get(key) or "")
            for key in ("place_name", "category_name", "address_name", "road_address_name", "area")
        )
        score = 0
        for term in terms:
            if not term:
                continue
            if term in name:
                score += 8
            elif term in haystack:
                score += 4
        if row.get("firstimage"):
            score += 5
        if row.get("source") == "korea":
            score += 1
        if score > 0:
            scored.append((score, row))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [row for _, row in scored]


def _onboarding_place_from_row(
    row: dict,
    source_keyword: str,
    label: str,
    category: str,
    reason: str,
) -> dict:
    name = row.get("place_name") or "추천 장소"
    address = row.get("road_address_name") or row.get("address_name") or ""
    photo_urls = [url for url in (row.get("firstimage"), row.get("firstimage2")) if url]
    if category == "must":
        curation = f"{_topic_label(name)} {reason}"
    else:
        curation = f"{_topic_label(name)} 선택한 노래의 {source_keyword} 무드와 이어지는 관광지 후보예요."
    return {
        "key": f"tourist::{name}::{row.get('id') or name}",
        "id": row.get("id") or name,
        "source_agent": "tourist",
        "name": name,
        "category": category,
        "label": label,
        "source_keyword": source_keyword,
        "address": address,
        "area": row.get("area") or "",
        "lat": _float_or_none(row.get("y")),
        "lng": _float_or_none(row.get("x")),
        "photo_url": photo_urls[0] if photo_urls else None,
        "photo_urls": photo_urls,
        "desc": curation,
        "curation": curation,
        "place_url": row.get("place_url") or "",
    }


def _topic_label(name: str) -> str:
    last = name[-1] if name else ""
    if "가" <= last <= "힣" and (ord(last) - ord("가")) % 28:
        return f"{name}은"
    return f"{name}는"


def _float_or_none(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _general_area_from_text(text: str) -> str:
    for area in GENERAL_AREA_HINTS:
        if area in text:
            return "서울" if area in ("한국", "대한민국", "서울특별시") else area
    return ""


def _is_general_tour_request(text: str) -> bool:
    return any(term in text for term in GENERAL_TOUR_TERMS)


def _general_tour_response(
    area: str,
    user_message: str,
    preferences: list[str],
    category_keywords: list[str],
) -> dict:
    candidates = search_representative_from_db(
        area=area or "서울",
        preferences=category_keywords or None,
        limit=20,
    )
    if not candidates and category_keywords:
        candidates = search_representative_from_db(area=area or "서울", limit=20)

    ranked = candidates[:5]
    reason = (
        f"{area or '서울'}을 처음 둘러볼 때 동선에 넣기 좋은 대표 명소를 우선으로 골랐어요."
        if ranked else "대표 명소 후보 없음"
    )
    return {
        "current_location": area or "서울",
        "latitude": None,
        "longitude": None,
        "address": area or "서울",
        "data_source": "db_general",
        "preferences": preferences,
        "llm_selection_reason": reason,
        "recommended_places": ranked,
        "query_type": "general_tour",
        "original_query": user_message,
    }


# ── Agent 진입점 ──────────────────────────────────────────────────────────────
def run(user_message: str, radius_km: float = 3.0) -> dict:
    """
    Tour agent entry node.
    Returns a dict with current_location, recommended_places, data_source, etc.
    """
    # Step 1: LLM — 위치 + 취향 추출
    intent = extract_intent_llm(user_message)
    location_name     = intent.get("location", "").strip()
    preferences       = intent.get("preferences", [])
    category_keywords = intent.get("category_keywords", [])
    general_area = _general_area_from_text(user_message) or _general_area_from_text(location_name)

    if not location_name:
        if general_area or _is_general_tour_request(user_message):
            return _general_tour_response(general_area or "서울", user_message, preferences, category_keywords)
        return {"error": "위치를 인식하지 못했습니다."}

    if location_name in GENERAL_AREA_HINTS:
        return _general_tour_response(general_area or location_name, user_message, preferences, category_keywords)

    # Step 2: DB 위치 조회
    coord = get_location_from_db(location_name)
    if not coord["found"]:
        coord = get_location_from_db(location_name.replace(" ", ""))

    # Step 3: DB 없으면 Kakao API fallback
    if not coord["found"]:
        coord = get_location_from_kakao(location_name)
    if not coord["found"]:
        return {"error": f"'{location_name}'을(를) DB와 Kakao API 모두에서 찾지 못했습니다."}

    lat, lon = coord["latitude"], coord["longitude"]

    # Step 4: 주변 관광지 검색
    if coord["source"] == "db":
        candidates = search_nearby_from_db(lat, lon, radius_km=radius_km,
                                           preferences=category_keywords or None)
    else:
        candidates = search_nearby_from_kakao(lat, lon, radius_km=radius_km)

    candidates = [p for p in candidates if p["place_name"] != coord["place_name"]]

    # Step 5: LLM — 최적 장소 선별
    if candidates:
        ranked, reason = rank_places_llm(candidates, user_message, preferences)
    else:
        ranked, reason = [], "후보 없음"

    return {
        "current_location": coord["place_name"],
        "latitude": lat,
        "longitude": lon,
        "address": coord["address"],
        "data_source": coord["source"],
        "preferences": preferences,
        "llm_selection_reason": reason,
        "recommended_places": ranked,
    }
