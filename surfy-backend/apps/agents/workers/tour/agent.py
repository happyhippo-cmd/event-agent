"""
Tour Worker Agent — LangGraph 버전
흐름: 자연어 입력 → [LLM] 위치+취향 추출 → DB/Kakao 검색
      → [filter] LLM 선별 → [curate] 큐레이션 카드 생성 → dict

노드 구성:
  extract_intent → (일반 지역) → general_tour → END
                → (특정 장소) → lookup_location → search_nearby
                                               → rank_and_curate → build_response → END
"""

from __future__ import annotations

import math
import os
import sqlite3
import json
import requests
from pathlib import Path
from typing import TypedDict
from dotenv import load_dotenv

try:
    from langsmith import traceable
    from langsmith.wrappers import wrap_openai
except ImportError:
    def traceable(**_kwargs):
        def decorator(fn):
            return fn
        return decorator
    wrap_openai = lambda client: client  # noqa: E731

from langgraph.graph import StateGraph, END

from apps.agents.utils import haversine_km, topic_label
from apps.agents.state import KDiveState, AGENT_TOURIST
from .filter import rank_tour_places
from .curate import curate_tour_items, check_visitability, build_card_text

BASE_DIR = Path(__file__).resolve().parents[4]
load_dotenv(BASE_DIR / ".env")

_raw_db_path = os.getenv("TOURIST_DB_PATH", "data/filtered_merged_tourism_deduped.db")
DB_PATH      = _raw_db_path if os.path.isabs(_raw_db_path) else str(BASE_DIR / _raw_db_path)
KAKAO_API_KEY = os.getenv("KAKAO_REST_API_KEY")
KAKAO_HEADERS = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}
KAKAO_KW_URL  = "https://dapi.kakao.com/v2/local/search/keyword.json"
KAKAO_CAT_URL = "https://dapi.kakao.com/v2/local/search/category.json"

_client = None

KAKAO_TOURIST_CATEGORIES = ["AT4", "CT1"]
ONBOARDING_FIXED_PLACES  = ("경복궁", "남산서울타워")
GENERAL_AREA_HINTS = {
    "서울":    ("서울", "서울특별시"),
    "서울특별시": ("서울", "서울특별시"),
    "한국":    ("서울", "서울특별시"),
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

# ── LLM 클라이언트 ────────────────────────────────────────────────────────────

def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI
        _client = wrap_openai(OpenAI(api_key=os.getenv("OPENAI_API_KEY")))
    return _client


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


@traceable(name="extract_intent")
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


# ── AgentState ────────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    # 입력
    user_message: str
    radius_km: float
    user_lat: float | None
    user_lng: float | None
    taste_context: dict | None
    sort_by: str
    # 의도 추출 결과
    location_name: str
    preferences: list[str]
    category_keywords: list[str]
    is_general_tour: bool
    general_area: str
    # 위치 조회 결과
    coord: dict
    # 후보 장소
    candidates: list[dict]
    # 선별·큐레이션 결과
    ranked: list[dict]
    reason: str
    curation_map: dict[str, dict]
    # 최종 출력
    result: dict
    error: str | None


# ── DB 헬퍼 ──────────────────────────────────────────────────────────────────

def get_location_from_db(location_name: str) -> dict:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT place_name, CAST(x AS REAL), CAST(y AS REAL), address
        FROM tourists
        WHERE place_name LIKE ? AND x IS NOT NULL AND x != '' AND y IS NOT NULL AND y != ''
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
        SELECT * FROM (
            SELECT *,
                   ROW_NUMBER() OVER (
                       PARTITION BY place_name
                       ORDER BY CASE source WHEN 'korea' THEN 1 ELSE 2 END
                   ) AS _rn
            FROM tourists
            WHERE CAST(x AS REAL) BETWEEN ? AND ?
              AND CAST(y AS REAL) BETWEEN ? AND ?
              AND x IS NOT NULL AND x != '' AND y IS NOT NULL AND y != ''
              {pref_sql}
        ) WHERE _rn = 1
        """,
        [longitude - deg_lon, longitude + deg_lon,
         latitude - deg_lat,  latitude + deg_lat] + pref_params,
    )
    columns = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()
    conn.close()

    results = []
    for row in rows:
        record = dict(zip(columns, row))
        record.pop("_rn", None)
        dist = haversine_km(latitude, longitude, float(record["y"]), float(record["x"]))
        if dist <= radius_km:
            record["distance_km"] = round(dist, 2)
            results.append(record)

    results.sort(key=lambda r: (0 if r.get("source") == "korea" else 1, r["distance_km"]))
    return results[:limit]


def enrich_korea_images(places: list[dict]) -> list[dict]:
    """kakao 행에 대해 source='korea' 행의 firstimage·firstimage2·usetime을 보강한다."""
    names = [p["place_name"] for p in places if p.get("source") != "korea"]
    if not names:
        return places

    conn = sqlite3.connect(DB_PATH)
    placeholders = ",".join("?" * len(names))
    rows = conn.execute(
        f"""
        SELECT place_name, firstimage, firstimage2, usetime
        FROM tourists
        WHERE source = 'korea' AND place_name IN ({placeholders})
        """,
        names,
    ).fetchall()
    conn.close()

    korea_data = {r[0]: {"firstimage": r[1], "firstimage2": r[2], "usetime": r[3]} for r in rows}
    for place in places:
        if place.get("source") == "korea":
            continue
        korea = korea_data.get(place["place_name"])
        if not korea:
            continue
        if korea.get("firstimage") and not place.get("firstimage"):
            place["firstimage"]  = korea["firstimage"]
            place["firstimage2"] = korea["firstimage2"]
        if korea.get("usetime") and not place.get("usetime"):
            place["usetime"] = korea["usetime"]
    return places


def search_representative_from_db(
    area: str = "서울",
    preferences: list[str] | None = None,
    limit: int = 20,
) -> list[dict]:
    area_aliases = GENERAL_AREA_HINTS.get(area, (area,))
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    area_clauses, params = [], []
    for alias in area_aliases:
        area_clauses.extend(["area LIKE ?", "address LIKE ?", "road_address LIKE ?"])
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
        WHERE place_name IS NOT NULL AND place_name != ''
          AND x IS NOT NULL AND x != '' AND y IS NOT NULL AND y != ''
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
        if not row.get("place_name"):
            continue
        ranked.append((_representative_score(row), {**row, "distance_km": None}))

    ranked.sort(key=lambda item: item[0], reverse=True)
    deduped, seen = [], set()
    for _, row in ranked:
        canonical = _canonical_representative_name(row.get("place_name") or "")
        if canonical in seen:
            continue
        seen.add(canonical)
        deduped.append(row)
        if len(deduped) >= limit:
            break
    return deduped


def _representative_score(row: dict) -> int:
    name     = row.get("place_name") or ""
    category = row.get("category_name") or ""
    score, must_score = 0, 0
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


# ── Kakao API 헬퍼 ────────────────────────────────────────────────────────────

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
        "longitude":  float(doc.get("x", 0)),
        "latitude":   float(doc.get("y", 0)),
        "address":    doc.get("address_name", ""),
    }


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
                "phone":      doc.get("phone", ""),
                "address":    doc.get("address_name", ""),
                "road_address": doc.get("road_address_name", ""),
                "x": doc.get("x", ""), "y": doc.get("y", ""),
                "category_name":       doc.get("category_name", ""),
                "category_group_code": doc.get("category_group_code", ""),
                "category_group_name": doc.get("category_group_name", ""),
                "place_url": doc.get("place_url", ""),
                "overview": None, "firstimage": None, "firstimage2": None,
                "homepage": None, "usetime": None, "restdate": None, "parking": None,
                "distance_km": round(int(dist_m) / 1000, 2) if dist_m else 0.0,
            })

    results.sort(key=lambda r: r["distance_km"])
    return results[:limit]


# ── 유틸리티 ──────────────────────────────────────────────────────────────────

def _general_area_from_text(text: str) -> str:
    for area in GENERAL_AREA_HINTS:
        if area in text:
            return "서울" if area in ("한국", "대한민국", "서울특별시") else area
    return ""


def _is_general_tour_request(text: str) -> bool:
    return any(term in text for term in GENERAL_TOUR_TERMS)


def _float_or_none(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# ── LangGraph 노드 ────────────────────────────────────────────────────────────

def node_extract_intent(state: AgentState) -> AgentState:
    taste_context = state.get("taste_context") or {}
    user_message  = state["user_message"]

    # taste_context의 location_keywords 우선 사용
    location_keywords = taste_context.get("location_keywords") or []
    if location_keywords:
        user_message = location_keywords[0]

    intent            = extract_intent_llm(user_message)
    location_name     = intent.get("location", "").strip()
    preferences       = intent.get("preferences", [])
    category_keywords = intent.get("category_keywords", [])

    general_area = (
        _general_area_from_text(state["user_message"])
        or _general_area_from_text(location_name)
    )
    is_general_tour = (
        location_name in GENERAL_AREA_HINTS
        or (not location_name and (general_area or _is_general_tour_request(state["user_message"])))
    )

    return {
        **state,
        "location_name":     location_name,
        "preferences":       preferences,
        "category_keywords": category_keywords,
        "is_general_tour":   is_general_tour,
        "general_area":      general_area or location_name,
    }


def node_general_tour(state: AgentState) -> AgentState:
    area              = state.get("general_area") or "서울"
    preferences       = state.get("preferences", [])
    category_keywords = state.get("category_keywords", [])

    candidates = search_representative_from_db(
        area=area, preferences=category_keywords or None, limit=20,
    )
    if not candidates and category_keywords:
        candidates = search_representative_from_db(area=area, limit=20)

    ranked = candidates[:5]
    reason = (
        f"{area}을 처음 둘러볼 때 동선에 넣기 좋은 대표 명소를 우선으로 골랐어요."
        if ranked else "대표 명소 후보 없음"
    )
    result = {
        "current_location": area,
        "latitude": None, "longitude": None,
        "address":     area,
        "data_source": "db_general",
        "preferences": preferences,
        "llm_selection_reason": reason,
        "recommended_places":   ranked,
        "query_type":    "general_tour",
        "original_query": state["user_message"],
    }
    if not ranked:
        result["message"] = "해당 관광지를 조회할 수 없습니다."
    return {**state, "result": result}


def node_lookup_location(state: AgentState) -> AgentState:
    location_name = state["location_name"]
    coord = get_location_from_db(location_name)
    if not coord["found"]:
        coord = get_location_from_db(location_name.replace(" ", ""))
    if not coord["found"]:
        coord = get_location_from_kakao(location_name)
    if not coord.get("found"):
        return {
            **state,
            "coord": {"found": False},
            "error": f"'{location_name}'을(를) DB와 Kakao API 모두에서 찾지 못했습니다.",
        }
    return {**state, "coord": coord}


def node_search_nearby(state: AgentState) -> AgentState:
    coord     = state["coord"]
    radius_km = state["radius_km"]
    lat, lon  = coord["latitude"], coord["longitude"]

    if coord["source"] == "db":
        candidates = search_nearby_from_db(
            lat, lon, radius_km=radius_km,
            preferences=state.get("category_keywords") or None,
        )
    else:
        candidates = search_nearby_from_kakao(lat, lon, radius_km=radius_km)

    candidates = [p for p in candidates if p["place_name"] != coord["place_name"]]
    candidates = enrich_korea_images(candidates)
    return {**state, "candidates": candidates}


def node_rank_and_curate(state: AgentState) -> AgentState:
    candidates   = state["candidates"]
    user_message = state["user_message"]
    preferences  = state.get("preferences", [])
    sort_by      = state.get("sort_by", "preference")

    if not candidates:
        return {**state, "ranked": [], "reason": "후보 없음", "curation_map": {}}

    if sort_by == "distance":
        ranked = sorted(candidates, key=lambda p: p.get("distance_km") or float("inf"))[:5]
        reason = "거리 가까운 순 정렬"
    else:
        ranked, reason = rank_tour_places(candidates, user_message, preferences)

    curation_map: dict[str, dict] = {}
    if ranked:
        try:
            curation_map = curate_tour_items(ranked, preferences)
        except Exception:
            pass

    return {**state, "ranked": ranked, "reason": reason, "curation_map": curation_map}


def node_build_response(state: AgentState) -> AgentState:
    coord        = state["coord"]
    ranked       = state["ranked"]
    curation_map = state["curation_map"]
    user_lat     = state.get("user_lat")
    user_lng     = state.get("user_lng")

    for place in ranked:
        pid      = str(place.get("id", place.get("place_id", "")))
        curation = curation_map.get(pid, {
            "headline":    place["place_name"],
            "description": (place.get("overview") or "")[:150],
            "highlights":  [],
            "visit_tip":   "",
        })
        if place.get("usetime"):
            curation["operate_time"] = place["usetime"]
        if place.get("firstimage"):
            curation["image_url"]   = place["firstimage"]
        if place.get("firstimage2"):
            curation["image_url_2"] = place["firstimage2"]

        # 사용자 실제 좌표 기준 도보 시간 보정
        dist_km = place.get("distance_km")
        if user_lat is not None and user_lng is not None:
            try:
                dist_km = haversine_km(user_lat, user_lng, float(place["y"]), float(place["x"]))
                curation["walk_minutes"] = max(1, round(dist_km / 4.0 * 60))
            except (TypeError, ValueError):
                pass

        curation.update(check_visitability(place.get("usetime") or "", dist_km))
        curation["card_text"] = build_card_text(curation)
        place["curation"] = curation

    result = {
        "current_location": coord["place_name"],
        "latitude":  coord["latitude"],
        "longitude": coord["longitude"],
        "address":   coord["address"],
        "data_source": coord["source"],
        "preferences": state.get("preferences", []),
        "llm_selection_reason": state["reason"],
        "recommended_places":   ranked,
    }
    if not ranked:
        result["message"] = "해당 관광지를 조회할 수 없습니다."
    return {**state, "result": result}


# ── 라우팅 조건 ──────────────────────────────────────────────────────────────

def _route_after_intent(state: AgentState) -> str:
    if state.get("is_general_tour"):
        return "general_tour"
    if state.get("location_name"):
        return "lookup_location"
    return END


def _route_after_lookup(state: AgentState) -> str:
    if state.get("coord", {}).get("found"):
        return "search_nearby"
    return END


# ── 그래프 빌드 ──────────────────────────────────────────────────────────────

def _build_graph():
    g = StateGraph(AgentState)

    g.add_node("extract_intent",  node_extract_intent)
    g.add_node("general_tour",    node_general_tour)
    g.add_node("lookup_location", node_lookup_location)
    g.add_node("search_nearby",   node_search_nearby)
    g.add_node("rank_and_curate", node_rank_and_curate)
    g.add_node("build_response",  node_build_response)

    g.set_entry_point("extract_intent")
    g.add_conditional_edges(
        "extract_intent", _route_after_intent,
        {"general_tour": "general_tour", "lookup_location": "lookup_location", END: END},
    )
    g.add_conditional_edges(
        "lookup_location", _route_after_lookup,
        {"search_nearby": "search_nearby", END: END},
    )
    g.add_edge("general_tour",    END)
    g.add_edge("search_nearby",   "rank_and_curate")
    g.add_edge("rank_and_curate", "build_response")
    g.add_edge("build_response",  END)

    return g.compile()


_graph = _build_graph()


# ── 공개 진입점 ──────────────────────────────────────────────────────────────

@traceable(name="tourism_agent_run")
def run_agent(
    user_message: str,
    radius_km: float = 3.0,
    user_lat: float | None = None,
    user_lng: float | None = None,
    taste_context: dict | None = None,
    sort_by: str = "preference",
) -> str:
    initial: AgentState = {
        "user_message":      user_message,
        "radius_km":         radius_km,
        "user_lat":          user_lat,
        "user_lng":          user_lng,
        "taste_context":     taste_context,
        "sort_by":           sort_by,
        "location_name":     "",
        "preferences":       [],
        "category_keywords": [],
        "is_general_tour":   False,
        "general_area":      "",
        "coord":             {},
        "candidates":        [],
        "ranked":            [],
        "reason":            "",
        "curation_map":      {},
        "result":            {},
        "error":             None,
    }
    final = _graph.invoke(initial)
    if final.get("error"):
        return json.dumps({"error": final["error"]}, ensure_ascii=False)
    return json.dumps(final["result"], ensure_ascii=False, indent=2)


def run_tour_agent_for_state(state: KDiveState, radius_km: float = 3.0) -> KDiveState:
    """Supervisor가 KDiveState로 tour agent를 직접 실행하는 진입점."""
    if AGENT_TOURIST not in (state.get("target_agents") or []):
        return state

    travel_phase = state.get("travel_phase", "unknown")
    if travel_phase == "during_trip":
        radius_km = 1.5
    elif travel_phase == "pre_trip":
        radius_km = 5.0

    agent_contexts = state.get("agent_taste_contexts") or {}
    taste   = agent_contexts.get(AGENT_TOURIST) or state.get("taste_context") or {}
    sort_by = state.get("tour_sort_by", "preference")

    raw_json = run_agent(
        user_message=state["user_utterance"],
        radius_km=radius_km,
        user_lat=state.get("user_lat"),
        user_lng=state.get("user_lng"),
        taste_context=taste,
        sort_by=sort_by,
    )
    state["tourist_result"] = json.loads(raw_json)
    return state


# ── 온보딩: 음악 키워드 기반 관광지 추천 ────────────────────────────────────

def recommend_places_for_music_keywords(
    tracks: list[dict],
    per_keyword: int = 3,
    fixed_count: int = 2,
) -> dict:
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
        keyword    = _track_keyword(track)
        terms      = _terms_for_track(track)
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
        SELECT id, place_name, category_name, area, address, road_address,
               x, y, firstimage, firstimage2, place_url, source
        FROM tourists
        WHERE place_name IS NOT NULL AND place_name != ''
          AND x IS NOT NULL AND x != '' AND y IS NOT NULL AND y != ''
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


def _best_fixed_row(rows: list[dict], fixed_name: str, used_names: set[str]) -> dict | None:
    exact = [
        row for row in rows
        if row.get("place_name") == fixed_name and row.get("place_name") not in used_names
    ]
    if exact:
        exact.sort(key=lambda row: 1 if row.get("firstimage") else 0, reverse=True)
        return exact[0]
    return _rank_rows_for_terms(rows, [fixed_name], used_names)[0] if _rank_rows_for_terms(rows, [fixed_name], used_names) else None


def _rank_rows_for_terms(rows: list[dict], terms: list[str], used_names: set[str]) -> list[dict]:
    scored = []
    for row in rows:
        name = row.get("place_name") or ""
        if name in used_names:
            continue
        haystack = " ".join(
            str(row.get(key) or "")
            for key in ("place_name", "category_name", "address", "road_address", "area")
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
    name       = row.get("place_name") or "추천 장소"
    address    = row.get("road_address") or row.get("address") or ""
    photo_urls = [url for url in (row.get("firstimage"), row.get("firstimage2")) if url]
    if category == "must":
        curation = f"{topic_label(name)} {reason}"
    else:
        curation = f"{topic_label(name)} 선택한 노래의 {source_keyword} 무드와 이어지는 관광지 후보예요."
    return {
        "key":            f"tourist::{name}::{row.get('id') or name}",
        "id":             row.get("id") or name,
        "source_agent":   "tourist",
        "name":           name,
        "category":       category,
        "label":          label,
        "source_keyword": source_keyword,
        "address":        address,
        "area":           row.get("area") or "",
        "lat":            _float_or_none(row.get("y")),
        "lng":            _float_or_none(row.get("x")),
        "photo_url":      photo_urls[0] if photo_urls else None,
        "photo_urls":     photo_urls,
        "desc":           curation,
        "curation":       curation,
        "place_url":      row.get("place_url") or "",
    }
