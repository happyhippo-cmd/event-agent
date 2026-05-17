# surfy-backend (placeholder)

Next.js 프론트엔드(`kdive-init`)의 Surfy 챗 컴포넌트가 호출하는
Django API 자리입니다. 현재 폴더에는 **Foodie Agent prototype 서버**가 있고,
실제 Django 프로젝트는 아직 들어와 있지 않습니다.

## 동작 방식
- `Dockerfile` CMD 가 `manage.py` 존재 여부를 검사합니다.
  - 있으면: `python manage.py migrate` → `runserver 0.0.0.0:8000`
  - 없으면: `python dummy_server.py` (8000 포트, `/api/chat/` prototype 응답)

## 환경 변수
루트 `.env` 파일 또는 compose `environment:` 에서 주입.
대표 키: `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DATABASE_URL`, `OPENAI_API_KEY` 등.

## Foodie Agent
- `data/foodie_enriched.db`의 `enriched_places` 테이블을 사용합니다.
- `mood_tags_naver`가 있으면 우선 사용하고, 없으면 `mood_tags`를 사용합니다.
- 기본 벡터화 방식은 외부 API를 쓰지 않는 `FOODIE_EMBED_PROVIDER=local_hash`입니다.
  OpenAI embedding을 쓰려면 `.env`에서 `FOODIE_EMBED_PROVIDER=openai`로 바꾸세요.
- 벡터 DB 생성:

```bash
cd surfy-backend
python -m apps.agents.workers.foodie.build_vector_db --reset
```

- Supervisor 검증 스크립트에서 `foodie`로 라우팅되면 Foodie Agent가
  `taste_context`를 받아 Chroma 검색 결과를 `foodie_result`에 채웁니다.
- `dummy_server.py`의 `/api/chat/`도 같은 흐름을 사용합니다. 현재 prototype은
  `foodie` 라우팅만 실제 실행하고, 추천 후보 3개와 각 후보의 큐레이션을 반환합니다.
