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
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

DB_PATH       = os.getenv("TOURISM_DB_PATH", "merged_tourism.db")
KAKAO_API_KEY = os.getenv("KAKAO_REST_API_KEY")
KAKAO_HEADERS = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}
KAKAO_KW_URL  = "https://dapi.kakao.com/v2/local/search/keyword.json"
KAKAO_CAT_URL = "https://dapi.kakao.com/v2/local/search/category.json"

_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# AT4: 관광명소, CT1: 문화시설
KAKAO_TOURIST_CATEGORIES = ["AT4", "CT1"]

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
    response = _client.chat.completions.create(
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
    response = _client.chat.completions.create(
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

    if not location_name:
        return {"error": "위치를 인식하지 못했습니다."}

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
