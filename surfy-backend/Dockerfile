# syntax=docker/dockerfile:1.6
# ---------------------------------------------------------------------------
# Surfy Django Backend (placeholder)
#   - 실제 Django 프로젝트가 들어오면 그대로 사용 가능
#   - manage.py 가 없는 동안에는 컨테이너가 더미 HTTP 서버를 띄움
#
# 보안/재현성 정책:
#   - Debian bookworm 슬림 베이스 + apt 보안 패치
#   - non-root 사용자 (django) 로 실행
# ---------------------------------------------------------------------------
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 1) 시스템 패키지 보안 패치 + 빌드/런타임 의존
RUN apt-get update \
 && apt-get upgrade -y \
 && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
 && rm -rf /var/lib/apt/lists/*

# 2) non-root 사용자
RUN groupadd --system --gid 1001 django \
 && useradd  --system --uid 1001 --gid django --create-home django

WORKDIR /app

# 3) 의존성 (캐시 레이어 분리)
COPY requirements.txt ./
RUN pip install -r requirements.txt

# 4) 앱 소스 (현재는 dummy_server.py 만 있음)
COPY --chown=django:django . .

USER django

EXPOSE 8000

# manage.py 가 있으면 Django, 없으면 dummy_server 로 부팅
CMD ["sh", "-c", "if [ -f manage.py ]; then \
        python manage.py migrate --noinput && \
        python manage.py runserver 0.0.0.0:8000; \
     else \
        echo '[surfy-backend] manage.py 가 아직 없습니다. dummy_server.py 로 부팅합니다.' && \
        python dummy_server.py; \
     fi"]
