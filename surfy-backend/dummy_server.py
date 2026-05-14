"""
Surfy backend 가 아직 들어오지 않은 동안 컨테이너가 죽지 않게 띄우는 더미 HTTP 서버.
실제 Django 프로젝트를 surfy-backend/ 에 옮겨 manage.py 가 생기면
Dockerfile CMD 가 자동으로 runserver 로 전환됩니다.

엔드포인트:
  GET  /            : 상태 메시지
  POST /api/chat/   : { "reply": "..."} 형태의 mock 응답
"""

from http.server import BaseHTTPRequestHandler, HTTPServer
import json


HOST = "0.0.0.0"
PORT = 8000


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
                data = {}
            user_msg = data.get("message", "")
            self._send_json(
                200,
                {
                    "reply": f"[placeholder] '{user_msg}' 잘 받았어요. 실제 Django 백엔드를 연결해 주세요.",
                },
            )
            return
        self._send_json(404, {"error": "not found", "path": self.path})

    def log_message(self, format, *args):  # noqa: A002
        # 컨테이너 로그를 너무 시끄럽지 않게
        print("[surfy-backend]", format % args, flush=True)


def main():
    print(f"[surfy-backend] dummy server listening on http://{HOST}:{PORT}", flush=True)
    HTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
