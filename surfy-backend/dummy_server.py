"""
Surfy backend 가 아직 들어오지 않은 동안 컨테이너가 죽지 않게 띄우는 더미 HTTP 서버.
실제 Django 프로젝트를 surfy-backend/ 에 옮겨 manage.py 가 생기면
Dockerfile CMD 가 자동으로 runserver 로 전환됩니다.

엔드포인트:
  GET  /            : 상태 메시지
  POST /api/chat/   : Supervisor + Foodie Agent prototype 응답
"""

import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

from dotenv import load_dotenv

# 공유 유틸 — 에이전트 모듈과 동일 함수를 사용한다
from apps.agents.utils import (
    join_modifiers as _join_intro_modifiers,
    object_phrase as _object_phrase,
    preference_modifier as _intro_modifier,
    taste_terms as _list_taste_terms,
    to_connective as _intro_connective,
    topic_label,
)


HOST = "0.0.0.0"
PORT = 8000
BASE_DIR = os.path.dirname(__file__)

sys.path.insert(0, BASE_DIR)
load_dotenv(os.path.join(BASE_DIR, ".env"))

# 세션별 pending clarification state 저장 (인메모리, 재시작 시 초기화)
_pending_clarifications: dict = {}

STATUS_MESSAGES = [
    "Supervisor가 사용자의 입력에서 취향과 의도를 분석하고 있어요.",
    "필요한 전문 Agent를 불러올게요.",
    "Agent가 사용자 맞춤 장소를 선정하고 있어요.",
]

LOCATION_HINTS = (
    "강남", "서초", "홍대", "연남", "합정", "망원", "성수", "압구정", "신사",
    "이태원", "한남", "을지로", "종로", "명동", "성북", "잠실", "여의도",
    "북촌", "서촌", "인사동", "혜화", "대학로", "경복궁", "광화문", "남산",
)
FOOD_CATEGORY_HINTS = {
    "카페": ("카페", "커피", "브런치", "디저트", "찻집", "베이커리"),
    "한식": ("한식", "백반", "국밥", "찌개"),
    "일식": ("일식", "라멘", "우동", "돈까스", "초밥", "스시"),
    "중식": ("중식", "짜장", "짬뽕", "마라"),
    "양식": ("양식", "파스타", "피자", "스테이크"),
    "분식": ("분식", "떡볶이", "김밥"),
}
FOOD_INTENT_HINTS = tuple(
    dict.fromkeys(["맛집", "식당", "밥", "먹", *[item for hints in FOOD_CATEGORY_HINTS.values() for item in hints]])
)
TOUR_INTENT_HINTS = (
    "관광", "관광지", "여행지", "명소", "가볼만", "구경", "산책", "박물관",
    "미술관", "공원", "야경", "볼거리",
)
EVENT_INTENT_HINTS = (
    "전시", "전시회", "팝업", "이벤트", "공연", "콘서트", "페스티벌", "행사", "아트페어",
)
MOOD_HINTS = {
    "조용한": ("조용", "차분"),
    "로컬 느낌": ("로컬", "동네", "개인", "독립", "숨은"),
    "감성적인": ("감성", "분위기"),
    "혼자": ("혼자", "혼밥", "혼카페"),
}
CHAIN_EXCLUDE_HINTS = (
    "체인", "프랜차이즈", "스타벅스", "커피빈", "투썸", "이디야", "메가커피",
    "컴포즈", "빽다방", "할리스", "폴바셋", "파스쿠찌",
)
LOCATION_PATTERN = re.compile(r"([가-힣A-Za-z0-9]+)\s*(?:에서|근처|주변|쪽|역)")
NEARBY_LOCATION_PATTERN = re.compile(r"([가-힣A-Za-z0-9]+)\s*(?:근처|주변|쪽)")


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):  # noqa: N802
        self._send_json(204, {})

    def do_GET(self):  # noqa: N802
        self._send_json(
            200,
            {
                "status": "ok",
                "service": "surfy-backend (placeholder)",
                "message": "manage.py 를 추가하면 Django runserver 로 전환됩니다.",
            },
        )

    def do_POST(self):  # noqa: N802
        route = self.path.rstrip("/")
        if route in ("/api/chat", "/api/onboarding/places", "/api/onboarding/foods"):
            length = int(self.headers.get("Content-Length", "0") or 0)
            try:
                raw = self.rfile.read(length).decode("utf-8") if length else "{}"
                data = json.loads(raw or "{}")
            except json.JSONDecodeError:
                self._send_json(400, {"error": "invalid_json"})
                return

            try:
                if route == "/api/onboarding/places":
                    payload = run_onboarding_places(data)
                elif route == "/api/onboarding/foods":
                    payload = run_onboarding_foods(data)
                else:
                    payload = run_chat_pipeline(data)
            except Exception as exc:
                self._send_json(
                    500,
                    {
                        "error": "agent_pipeline_failed",
                        "detail": str(exc),
                        "status_messages": STATUS_MESSAGES,
                    },
                )
                return

            self._send_json(200, payload)
            return
        self._send_json(404, {"error": "not found", "path": self.path})

    def log_message(self, format, *args):  # noqa: A002
        # 컨테이너 로그를 너무 시끄럽지 않게
        print("[surfy-backend]", format % args, flush=True)


def main():
    print(f"[surfy-backend] dummy server listening on http://{HOST}:{PORT}", flush=True)
    HTTPServer((HOST, PORT), Handler).serve_forever()


def run_onboarding_places(payload):
    from apps.agents.workers.tour.agent import recommend_places_for_music_keywords

    tracks = payload.get("tracks") or []
    result = recommend_places_for_music_keywords(
        tracks=tracks,
        per_keyword=int(payload.get("per_keyword") or 3),
        fixed_count=int(payload.get("fixed_count") or 2),
    )
    return result


def run_onboarding_foods(payload):
    from apps.agents.workers.restaurant.agent import recommend_nearby_foods_for_places

    places = payload.get("places") or []
    return recommend_nearby_foods_for_places(
        places=places,
        limit=int(payload.get("limit") or 5),
        radius_km=float(payload.get("radius_km") or 2.0),
    )


def run_chat_pipeline(payload):
    from apps.agents.state import AGENT_EVENT, AGENT_FOODIE, AGENT_TOURIST
    from apps.agents.supervisor import supervisor_intake, continue_after_clarification

    history = payload.get("history") or []
    user_message = str(payload.get("message") or "").strip()
    user_context = payload.get("user_context") or {}

    if not user_message:
        return {
            "response": "메시지를 입력해 주세요.",
            "route_decision": None,
            "agent_results": {},
            "recommendations": [],
            "status_messages": [],
        }

    # 이전 턴에 저장된 pending clarification state 확인
    session_key = _make_session_key(history)
    pending_state = _pending_clarifications.pop(session_key, None)

    if pending_state is not None:
        # pending state가 있으면 continue_after_clarification()으로 이어서 처리
        effective_message = user_message  # 세션 복원 시: 사용자 답변을 그대로 사용
        result_state = continue_after_clarification(pending_state, user_message)
    else:
        effective_message = user_message
        state = {
            "user_utterance": effective_message,
            "onboarding_data": _build_onboarding_data(user_context),
            "messages": history,
            "accumulated_keywords": _build_accumulated_keywords_from_history(history),
        }
        result_state = supervisor_intake(state)

    result_state = _apply_deterministic_taste_hints(
        result_state=result_state,
        user_message=user_message,
        event_agent=AGENT_EVENT,
        foodie_agent=AGENT_FOODIE,
        tourist_agent=AGENT_TOURIST,
    )
    result_state = _apply_user_context_to_taste(result_state, user_context)

    if result_state.get("needs_user_clarification"):
        question = result_state.get("clarification_question") or "조금 더 구체적으로 알려주실래요?"
        # 다음 턴을 위해 현재 state를 세션에 저장
        next_session_key = _make_session_key(
            history + [{"role": "user", "content": user_message}]
        )
        _pending_clarifications[next_session_key] = dict(result_state)
        return {
            "response": question,
            "route_decision": {
                "target_agents": result_state.get("target_agents", []),
                "needs_user_clarification": True,
                "clarification_type": result_state.get("clarification_type"),
            },
            "agent_results": {},
            "recommendations": [],
            "status_messages": STATUS_MESSAGES[:1],
        }

    target_agents = result_state.get("target_agents", [])
    agent_results = {}
    recommendations = []

    if AGENT_FOODIE in target_agents:
        result_state = _run_foodie_agent(result_state, top_k=3)
        foodie_result = result_state.get("foodie_result") or {}
        agent_results["foodie"] = foodie_result
        recommendations.extend(_format_foodie_recommendations(foodie_result))

    if AGENT_EVENT in target_agents:
        event_taste = _agent_taste_context(result_state, AGENT_EVENT)
        event_result = _run_event_agent(
            effective_message,
            taste_context=event_taste,
            history=payload.get("history") or [],
        )
        result_state["event_result"] = event_result
        agent_results["event"] = event_result
        recommendations.extend(_format_event_recommendations(event_result))

    if AGENT_TOURIST in target_agents:
        tour_result = _run_tour_agent(effective_message)
        result_state["tourist_result"] = tour_result
        agent_results["tourist"] = tour_result
        recommendations.extend(_format_tour_recommendations(tour_result))

    if recommendations:
<<<<<<< Updated upstream
<<<<<<< Updated upstream
        recommendations = recommendations[:3]
        base_response = _build_recommendation_response(
            recommendations,
            target_agents,
            result_state.get("taste_context", {}),
        )
        event_result = agent_results.get("event") or {}
        if (
            AGENT_EVENT in target_agents
            and AGENT_FOODIE not in target_agents
            and AGENT_TOURIST not in target_agents
            and event_result.get("message")
        ):
            base_response = event_result["message"]
        # event agent가 제약을 완화한 경우(예: 성수에 트로트 없어서 다른 지역도 봤음)
        # 사용자에게 그 사실을 먼저 알린다.
        event_relax = event_result.get("relaxation_note") or ""
        if base_response.startswith(event_relax):
            event_relax = ""
        final_response = f"{event_relax} {base_response}".strip() if event_relax else base_response
=======
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
        return {
            "response": final_response,
            "route_decision": {
                "target_agents": target_agents,
                "taste_context": result_state.get("taste_context", {}),
            },
            "agent_results": agent_results,
            "recommendations": recommendations,
            "status_messages": STATUS_MESSAGES,
        }

    return {
        "response": _build_no_result_response(target_agents, agent_results),
        "route_decision": {
            "target_agents": target_agents,
            "taste_context": result_state.get("taste_context", {}),
        },
        "agent_results": agent_results,
        "recommendations": [],
        "status_messages": STATUS_MESSAGES[:1],
    }


def _build_onboarding_data(user_context):
    music_keywords = list(user_context.get("music_keywords") or [])
    extras = user_context.get("extras") or {}
    active_track = extras.get("active_track") or {}
    if not music_keywords and active_track.get("vibe"):
        music_keywords = [
            item.strip()
            for item in str(active_track["vibe"]).split("·")
            if item.strip()
        ]

    liked_places = _extract_names(user_context.get("liked_places") or [])
    liked_foods = _extract_names(user_context.get("liked_foods") or [])
    foodie_spots = liked_foods or liked_places

    return {
        "music": music_keywords,
        "tourist_spots": liked_places,
        "foodie_spots": foodie_spots,
        "preferred_mood": music_keywords,
        "companion_type": extras.get("companion_type") or "혼자",
        "active_time": extras.get("active_time") or "저녁",
    }


def _apply_deterministic_taste_hints(result_state, user_message, event_agent, foodie_agent, tourist_agent):
    state = dict(result_state)
    taste_context = dict(state.get("taste_context") or {})
    target_agents = list(state.get("target_agents") or [])

    food_categories = _detect_food_categories(user_message)
    locations = _detect_locations(user_message)
    nearby_locations = _detect_nearby_locations(user_message)
    moods = _detect_moods(user_message)
    suppressed = _detect_suppressed_keywords(user_message)
    is_food_request = bool(food_categories) or any(hint in user_message for hint in FOOD_INTENT_HINTS)
    is_event_request = any(hint in user_message for hint in EVENT_INTENT_HINTS)
    is_tour_request = any(hint in user_message for hint in TOUR_INTENT_HINTS)
    if is_food_request and not _has_explicit_tour_intent(user_message):
        is_tour_request = False
    if is_event_request and not _has_explicit_tour_intent(user_message):
        is_tour_request = False
    if not is_tour_request and (is_food_request or is_event_request):
        target_agents = [agent for agent in target_agents if agent != tourist_agent]

    if is_food_request:
        _append_unique(target_agents, foodie_agent)
    if is_event_request:
        _append_unique(target_agents, event_agent)
    if is_tour_request:
        _append_unique(target_agents, tourist_agent)

    _extend_taste_context(taste_context, "location_keywords", locations)
    _extend_taste_context(taste_context, "nearby_place_keywords", nearby_locations)
    _extend_taste_context(taste_context, "event_type_keywords", _detect_event_types(user_message))
    _extend_taste_context(taste_context, "food_type_keywords", food_categories)
    _extend_taste_context(taste_context, "place_type_keywords", food_categories)
    _extend_taste_context(taste_context, "mood_keywords", moods)
    _extend_taste_context(taste_context, "current_mood_keywords", moods)
    _extend_taste_context(taste_context, "suppressed_keywords", suppressed)
    _extend_taste_context(
        taste_context,
        "current_keywords",
        [*locations, *nearby_locations, *food_categories, *moods, *suppressed],
    )

    if target_agents:
        state["target_agents"] = target_agents
    if taste_context:
        state["taste_context"] = taste_context

    if (
        state.get("needs_user_clarification")
        and state.get("clarification_type") != "out_of_scope"
        and (is_food_request or is_event_request or is_tour_request)
        and target_agents
    ):
        state["needs_user_clarification"] = False
        state.pop("clarification_question", None)
        state.pop("clarification_type", None)

    return state


def _apply_user_context_to_taste(result_state, user_context):
    state = dict(result_state)
    taste_context = dict(state.get("taste_context") or {})
    extras = user_context.get("extras") or {}
    nickname = (
        user_context.get("nickname")
        or user_context.get("user_nickname")
        or user_context.get("display_name")
        or extras.get("nickname")
        or extras.get("user_nickname")
        or extras.get("display_name")
    )
    if nickname:
        taste_context["nickname"] = nickname
    # supervisor가 허용한 경우에만 온보딩 liked_places 좌표를 자동 anchor로 사용한다.
    # 발화에 명시 location이 있으면 supervisor가 False로 내려보내므로 anchor 자동 설정을 건너뛴다.
    if taste_context.get("allow_onboarding_anchors", True):
        liked_place_anchors = _extract_place_anchors(user_context.get("liked_places") or [])
        if liked_place_anchors and not taste_context.get("nearby_place_keywords"):
            taste_context["nearby_place_anchors"] = liked_place_anchors
            taste_context["nearby_place_keywords"] = [anchor["name"] for anchor in liked_place_anchors]
    if taste_context:
        state["taste_context"] = taste_context
    return state


def _detect_locations(user_message):
    locations = []
    for match in LOCATION_PATTERN.finditer(user_message):
        location = match.group(1).strip()
        if 1 < len(location) <= 8:
            locations.append(location)
    locations.extend(location for location in LOCATION_HINTS if location in user_message)
    return list(dict.fromkeys(locations))


def _detect_nearby_locations(user_message):
    locations = []
    for match in NEARBY_LOCATION_PATTERN.finditer(user_message):
        location = match.group(1).strip()
        if 1 < len(location) <= 12:
            locations.append(location)
    return list(dict.fromkeys(locations))


def _detect_event_types(user_message):
    return [hint for hint in EVENT_INTENT_HINTS if hint in user_message]


def _has_explicit_tour_intent(user_message):
    explicit_terms = (
        "관광", "관광지", "여행지", "명소", "가볼만", "구경", "산책",
        "박물관", "미술관", "공원", "야경",
    )
    return any(term in user_message for term in explicit_terms)


def _detect_food_categories(user_message):
    categories = []
    for category, hints in FOOD_CATEGORY_HINTS.items():
        if any(hint in user_message for hint in hints):
            categories.append(category)
    if any(brand in user_message for brand in ("스타벅스", "커피빈", "투썸", "이디야", "메가커피", "컴포즈", "빽다방", "할리스")):
        categories.append("카페")
    return list(dict.fromkeys(categories))


def _detect_moods(user_message):
    moods = []
    for mood, hints in MOOD_HINTS.items():
        if any(hint in user_message for hint in hints):
            moods.append(mood)
    return list(dict.fromkeys(moods))


def _detect_suppressed_keywords(user_message):
    suppressed = [hint for hint in CHAIN_EXCLUDE_HINTS if hint in user_message]
    if any(hint in user_message for hint in ("로컬", "동네", "개인", "독립", "숨은")):
        suppressed.append("체인")
    return list(dict.fromkeys(suppressed))


def _extend_taste_context(taste_context, key, values):
    if not values:
        return
    current = taste_context.get(key)
    if not isinstance(current, list):
        current = [current] if current else []
    for value in values:
        _append_unique(current, value)
    taste_context[key] = current


def _append_unique(items, value):
    if value and value not in items:
        items.append(value)


def _make_session_key(history: list) -> str:
    """대화 히스토리의 user 메시지만 기반으로 세션 키를 생성한다.
    assistant 메시지는 저장/조회 시 포함 여부가 달라지므로 제외한다."""
    user_messages = tuple(
        m.get("content", "")
        for m in history
        if m.get("role") == "user"
    )
    return str(hash(user_messages))


def _build_accumulated_keywords_from_history(history):
    """프론트가 보낸 raw history를 추천용 키워드 요약으로 압축한다.

    이전 발화를 현재 발화에 그대로 붙이면 오래된 날짜나 장소가 현재 의도로
    되살아나므로, 다음 턴 해석에 필요한 범주만 남긴다.
    """
    accumulated = {
        "location": [],
        "mood": [],
        "place_type": [],
        "food_type": [],
        "suppressed": [],
    }
    for item in history:
        if item.get("role") != "user":
            continue
        text = str(item.get("content") or "")
        locations = _detect_locations(text)
        if locations:
            accumulated["location"] = locations
        food_categories = _detect_food_categories(text)
        if food_categories:
            accumulated["food_type"] = food_categories
            accumulated["place_type"] = food_categories
        moods = _detect_moods(text)
        accumulated["mood"] = list(dict.fromkeys(accumulated["mood"] + moods))
        suppressed = _detect_suppressed_keywords(text)
        accumulated["suppressed"] = list(
            dict.fromkeys(accumulated["suppressed"] + suppressed)
        )
    return {key: value for key, value in accumulated.items() if value}


def _extract_names(items):
    names = []
    for item in items:
        if isinstance(item, str):
            name = _name_from_key(item)
        else:
            name = item.get("name") or item.get("title") or _name_from_key(item.get("key", ""))
        if name:
            names.append(name)
    return list(dict.fromkeys(names))


def _extract_place_anchors(items):
    anchors = []
    seen = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or item.get("title") or _name_from_key(item.get("key", ""))
        lat = item.get("lat")
        lng = item.get("lng")
        if not name or lat is None or lng is None or name in seen:
            continue
        anchors.append({"name": name, "lat": lat, "lng": lng})
        seen.add(name)
    return anchors


def _name_from_key(key):
    parts = [part for part in str(key).split("::") if part]
    if len(parts) >= 2:
        return parts[1]
    return parts[0] if parts else ""


def _run_foodie_agent(result_state, top_k):
    from apps.agents.workers.restaurant import run_restaurant_agent_for_state
    from apps.agents.workers.restaurant.agent import run_nearby_restaurant_agent

    taste_context = _agent_taste_context(result_state, "foodie")
    anchors = _resolve_nearby_anchors(taste_context)
    if anchors:
        result_state = dict(result_state)
        result = run_nearby_restaurant_agent(
            anchors=anchors,
            taste_context=taste_context,
            top_k=top_k,
            radius_km=2.0,
        )
        result_state["foodie_result"] = result
        result_state["restaurant_result"] = result
        return result_state
    return run_restaurant_agent_for_state(result_state, top_k=top_k)


def _agent_taste_context(result_state, agent):
    contexts = result_state.get("agent_taste_contexts") or {}
    return contexts.get(agent) or result_state.get("taste_context", {})


def _resolve_nearby_anchors(taste_context):
    explicit_anchors = [
        anchor
        for anchor in taste_context.get("nearby_place_anchors", [])
        if anchor.get("name") and anchor.get("lat") is not None and anchor.get("lng") is not None
    ]
    if explicit_anchors:
        return explicit_anchors

    anchor_names = list(taste_context.get("nearby_place_keywords") or [])
    if not anchor_names:
        return []

    from apps.agents.workers.tour.agent import get_location_from_db, get_location_from_kakao

    anchors = []
    for name in anchor_names:
        coord = get_location_from_db(name)
        if not coord.get("found"):
            coord = get_location_from_db(str(name).replace(" ", ""))
        if not coord.get("found"):
            coord = get_location_from_kakao(name)
        if coord.get("found"):
            anchors.append(
                {
                    "name": name,
                    "lat": coord.get("latitude"),
                    "lng": coord.get("longitude"),
                }
            )
    return anchors


def _run_event_agent(user_message, taste_context=None, history=None):
    try:
        from apps.agents.workers.event import run_event_agent

        return run_event_agent(
            query=user_message,
            taste_context=taste_context or {},
            history=history or [],
            top_k=3,
        )
    except Exception as exc:
        return {
            "status": "error",
            "message": f"Event Agent 실행 중 오류가 발생했어요: {exc}",
            "recommended_events": [],
        }


def _run_tour_agent(user_message):
    try:
        from apps.agents.workers.tour.agent import run as run_tour_agent

        result = run_tour_agent(user_message, radius_km=3.0)
    except Exception as exc:
        return {
            "status": "error",
            "message": f"Tour Agent 실행 중 오류가 발생했어요: {exc}",
            "recommended_places": [],
        }

    if result.get("error"):
        return {
            "status": "error",
            "message": result["error"],
            "recommended_places": [],
            "raw": result,
        }
    return {
        "status": "ok",
        "message": "",
        **result,
    }


def _format_foodie_recommendations(foodie_result):
    status = foodie_result.get("status")
    candidates = foodie_result.get("candidates") or []
    if status != "ok" or not candidates:
        return []

    return [
        {
            "source_agent": "restaurant",
            "id": candidate.get("kakao_place_id"),
            "name": candidate.get("name"),
            "category": candidate.get("category"),
            "area": candidate.get("gu"),
            "address": candidate.get("address"),
            "photo_url": _first_present(candidate, ("photo_url", "image_url", "firstimage", "firstimage2")),
            "photo_urls": _photo_urls(candidate),
            "rating": candidate.get("rating"),
            "review_count": candidate.get("review_count"),
            "matched_preferences": candidate.get("matched_preferences", []),
            "ranking_basis": candidate.get("ranking_basis", ""),
            "curation": candidate.get("curation") or candidate.get("ranking_basis", ""),
        }
        for candidate in candidates[:3]
    ]


def _format_tour_recommendations(tour_result):
    if tour_result.get("status") != "ok":
        return []

    reason = tour_result.get("llm_selection_reason") or ""
    recommendations = []
    for place in (tour_result.get("recommended_places") or [])[:3]:
        name = place.get("place_name") or place.get("name")
        category = place.get("category_name") or "관광지"
        address = place.get("road_address_name") or place.get("address_name") or place.get("address")
        distance = place.get("distance_km")
        photo_url = _first_present(place, ("firstimage", "firstimage2", "photo_url", "image_url"))
        curation = _build_tour_curation(name, category, distance, reason, place.get("overview"))
        recommendations.append(
            {
                "source_agent": "tourist",
                "id": place.get("id") or name,
                "name": name,
                "category": category,
                "area": tour_result.get("current_location"),
                "address": address,
                "photo_url": photo_url,
                "photo_urls": _photo_urls(place),
                "distance_km": distance,
                "matched_preferences": tour_result.get("preferences", []),
                "ranking_basis": reason,
                "curation": curation,
            }
        )
    return recommendations


def _format_event_recommendations(event_result):
    if event_result.get("status") != "ok":
        return []

    recommendations = []
    for event in (event_result.get("recommended_events") or [])[:3]:
        title = event.get("title") or event.get("name")
        recommendations.append(
            {
                "source_agent": "event",
                "id": event.get("id") or event.get("detail_url") or title,
                "name": title,
                "category": event.get("category") or "이벤트",
                "area": event.get("region") or event.get("location"),
                "address": event.get("location") or event.get("address"),
                "photo_url": _first_present(event, ("photo_url", "thumbnail_url", "image_url")),
                "photo_urls": _photo_urls(event),
                "event_date": event.get("date"),
                "detail_url": event.get("detail_url"),
                "matched_preferences": event.get("hashtags", [])[:2],
                "ranking_basis": event.get("reason", ""),
                "curation": event.get("curation") or event.get("reason") or event.get("description", ""),
            }
        )
    return recommendations


def _first_present(data, keys):
    for key in keys:
        value = data.get(key)
        if value:
            return value
    return None


def _photo_urls(data):
    urls = []
    for key in ("photo_url", "thumbnail_url", "image_url", "firstimage", "firstimage2"):
        value = data.get(key)
        if value and value not in urls:
            urls.append(value)
    return urls


def _build_tour_curation(name, category, distance, reason, overview):
    if not name:
        name = "이 장소"
    subject = _subject_phrase(name)
    category_label = _tour_category_label(category)
    distance_text = f" 기준 위치에서 약 {distance}km 거리라" if distance is not None else ""
    overview_text = (overview or "").strip()
    if overview_text:
        overview_text = overview_text[:80]
    if reason:
        return f"{subject} {category_label}로,{distance_text} 요청한 동선에 넣기 좋아요. {reason}"
    if overview_text:
        return f"{subject} {category_label}로,{distance_text} {overview_text}"
    return f"{subject} {category_label}로,{distance_text} Surfy가 고른 관광지 추천이에요."


def _subject_phrase(text):
    return topic_label(text)


def _tour_category_label(category):
    text = str(category or "").strip()
    if not text or text == "관광지":
        return "관광지"
    if "고궁" in text:
        return "고궁 명소"
    if "문화유적" in text:
        return "역사 명소"
    if "테마거리" in text:
        return "거리 명소"
    if "전망대" in text:
        return "전망 명소"
    if "공원" in text:
        return "공원"
    return text.split(">")[-1].strip() or "관광지"


def _build_recommendation_response(recommendations, target_agents, taste_context=None):
    names = ", ".join(item["name"] for item in recommendations if item.get("name"))
    count = len(recommendations)
<<<<<<< Updated upstream
<<<<<<< Updated upstream
=======
    if "event" in target_agents and "tourist" in target_agents and "foodie" not in target_agents:
        return f"좋아요. 관광지와 전시·이벤트를 함께 골랐어요: {names}"
>>>>>>> Stashed changes
=======
    if "event" in target_agents and "tourist" in target_agents and "foodie" not in target_agents:
        return f"좋아요. 관광지와 전시·이벤트를 함께 골랐어요: {names}"
>>>>>>> Stashed changes
    if "event" in target_agents and "foodie" not in target_agents and "tourist" not in target_agents:
        return f"좋아요. 지금 요청에 맞는 이벤트 {count}곳을 골랐어요: {names}"
    if "foodie" in target_agents and "tourist" in target_agents:
        return f"좋아요. 맛집과 관광지를 함께 보고 어울리는 장소 {count}곳을 골랐어요: {names}"
    if "tourist" in target_agents:
        return f"좋아요. 지금 요청에 맞는 관광지 {count}곳을 골랐어요: {names}"
    return f"좋아요. {_foodie_taste_intro(taste_context or {})} {count}군데를 가져왔어요: {names}"


def _foodie_taste_intro(taste_context):
    food_types = _list_taste_terms(taste_context, ("food_type_keywords", "place_type_keywords"))
    current_moods = _list_taste_terms(taste_context, ("mood_keywords", "current_mood_keywords"))
    history_moods = _list_taste_terms(taste_context, ("onboarding_mood_keywords", "preferred_mood", "preferred_music"))
    if "카페" in food_types:
        food_types = [term for term in food_types if term not in ("커피", "커피전문점")]

    condition_phrase = _restaurant_condition_phrase(current_moods, food_types)
    history_phrase = _history_preference_phrase(history_moods)
    food_phrase = food_types[0] if food_types else "장소"

    if history_phrase and condition_phrase:
        return f"히스토리의 {history_phrase} 취향을 참고해서 요청하신 {condition_phrase}"
    if history_phrase:
        return f"히스토리의 {history_phrase} 취향을 참고해서 어울리는 {food_phrase}"
    if condition_phrase:
        return f"요청하신 {condition_phrase}"
    if food_types:
        return f"{_object_phrase(food_phrase)} 찾고 계신 것 같아서"
    return "취향에 맞는 장소를 찾고 계신 것 같아서"


def _restaurant_condition_phrase(moods, food_types):
    food_phrase = food_types[0] if food_types else "장소"
    mood_phrase = _join_intro_modifiers([_intro_modifier(term) for term in moods[:2]])
    if mood_phrase:
        return f"{mood_phrase} {food_phrase}"
    if food_types:
        return food_phrase
    return ""


def _history_preference_phrase(moods):
    meaningful = [
        term
        for term in moods
        if term and term not in ("카페", "커피", "커피전문점", "맛집", "식당", "장소")
    ]
    return _join_intro_modifiers([_intro_modifier(term) for term in meaningful[:2]])



# _object_phrase, _list_taste_terms, _intro_modifier, _join_intro_modifiers, _intro_connective
# → apps.agents.utils 에서 import 완료 (파일 상단)


def _build_no_result_response(target_agents, agent_results):
    if "event" in target_agents:
        event_result = agent_results.get("event") or {}
        return event_result.get("message") or "조건에 맞는 이벤트 추천을 찾지 못했어요."
    if "tourist" in target_agents:
        tour_result = agent_results.get("tourist") or {}
        return tour_result.get("message") or "조건에 맞는 관광지 추천을 찾지 못했어요."
    if "foodie" in target_agents:
        foodie_result = agent_results.get("foodie") or {}
        return foodie_result.get("message") or "조건에 맞는 Foodie 추천을 찾지 못했어요."
    return "지금 prototype에서는 Foodie/Tour Agent 추천만 실행되고 있어요. 맛집이나 관광지 요청으로 다시 물어봐 주세요."


if __name__ == "__main__":
    main()
