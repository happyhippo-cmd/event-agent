# surfy-backend (placeholder)

Next.js 프론트엔드(`kdive-init`)의 Surfy 챗 컴포넌트가 호출하는
Django API 자리입니다. 현재 폴더에는 **임시 더미 서버**만 있고,
실제 Django 프로젝트는 아직 들어와 있지 않습니다.

## 동작 방식
- `Dockerfile` CMD 가 `manage.py` 존재 여부를 검사합니다.
  - 있으면: `python manage.py migrate` → `runserver 0.0.0.0:8000`
  - 없으면: `python dummy_server.py` (8000 포트, `/api/chat/` mock 응답)

## 환경 변수
루트 `.env` 파일 또는 compose `environment:` 에서 주입.
대표 키: `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DATABASE_URL`, `OPENAI_API_KEY` 등.
