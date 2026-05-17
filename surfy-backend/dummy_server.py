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
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

from dotenv import load_dotenv


HOST = "0.0.0.0"
PORT = 8000
BASE_DIR = os.path.dirname(__file__)

sys.path.insert(0, BASE_DIR)
load_dotenv(os.path.join(BASE_DIR, ".env"))

STATUS_MESSAGES = [
    "Supervisor가 사용자의 입력에서 취향과 의도를 분석하고 있어요.",
    "Foodie Agent를 불러올게요.",
    "Foodie Agent가 사용자 맞춤 장소를 선정하고 있어요.",
]


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
        if self.path.rstrip("/") == "/api/chat":
            length = int(self.headers.get("Content-Length", "0") or 0)
            try:
                raw = self.rfile.read(length).decode("utf-8") if length else "{}"
                data = json.loads(raw or "{}")
            except json.JSONDecodeError:
                self._send_json(400, {"error": "invalid_json"})
                return

            try:
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


def run_chat_pipeline(payload):
    from apps.agents.state import AGENT_FOODIE
    from apps.agents.supervisor import supervisor_intake
    from apps.agents.workers.foodie import run_foodie_agent_for_state

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

    state = {
        "user_utterance": user_message,
        "onboarding_data": _build_onboarding_data(user_context),
    }
    result_state = supervisor_intake(state)

    if result_state.get("needs_user_clarification"):
        question = result_state.get("clarification_question") or "조금 더 구체적으로 알려주실래요?"
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

    if AGENT_FOODIE in result_state.get("target_agents", []):
        result_state = run_foodie_agent_for_state(result_state, top_k=3)
        foodie_result = result_state.get("foodie_result") or {}
        recommendations = foodie_result.get("candidates") or []
        return {
            "response": _build_foodie_response(foodie_result),
            "route_decision": {
                "target_agents": result_state.get("target_agents", []),
                "taste_context": result_state.get("taste_context", {}),
            },
            "agent_results": {"foodie": foodie_result},
            "recommendations": recommendations[:3],
            "status_messages": STATUS_MESSAGES,
        }

    return {
        "response": "지금 prototype에서는 Foodie Agent 추천만 연결되어 있어요. 맛집이나 카페 요청으로 다시 물어봐 주세요.",
        "route_decision": {
            "target_agents": result_state.get("target_agents", []),
            "taste_context": result_state.get("taste_context", {}),
        },
        "agent_results": {},
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


def _name_from_key(key):
    parts = [part for part in str(key).split("::") if part]
    if len(parts) >= 2:
        return parts[1]
    return parts[0] if parts else ""


def _build_foodie_response(foodie_result):
    status = foodie_result.get("status")
    candidates = foodie_result.get("candidates") or []
    if status != "ok" or not candidates:
        return foodie_result.get("message") or "조건에 맞는 Foodie 추천을 찾지 못했어요."

    names = ", ".join(candidate["name"] for candidate in candidates[:3])
    return f"좋아요. 취향 태그가 잘 맞는 장소 3곳을 골랐어요: {names}"


if __name__ == "__main__":
    main()
