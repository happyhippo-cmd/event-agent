# syntax=docker/dockerfile:1.6
# ---------------------------------------------------------------------------
# kdive-init (Next.js) - Production multi-stage build
#   1) deps   : 의존성만 설치 (캐시 분리)
#   2) builder: next build (standalone 출력)
#   3) runner : 최소 런타임 이미지 (non-root, standalone 산출물만 포함)
#
# 보안 패치 정책:
#   - node:22-alpine (현재 LTS, 패치 주기가 빠름)
#   - 모든 stage 에서 apk upgrade --no-cache 로 베이스 CVE 끌어내림
# ---------------------------------------------------------------------------

# 1) deps -------------------------------------------------------------------
FROM node:22-alpine AS deps
WORKDIR /app

RUN apk upgrade --no-cache \
 && apk add --no-cache libc6-compat

COPY package.json package-lock.json* ./
RUN npm ci --no-audit --no-fund


# 2) builder ----------------------------------------------------------------
FROM node:22-alpine AS builder
WORKDIR /app

ENV NEXT_TELEMETRY_DISABLED=1 \
    NODE_ENV=production

RUN apk upgrade --no-cache

COPY --from=deps /app/node_modules ./node_modules
COPY . .

# next.config.js 의 output: 'standalone' 설정에 의해 .next/standalone 생성
RUN npm run build


# 3) runner -----------------------------------------------------------------
FROM node:22-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

# 베이스 보안 패치 + non-root 사용자
RUN apk upgrade --no-cache \
 && addgroup --system --gid 1001 nodejs \
 && adduser  --system --uid 1001 nextjs

# standalone 산출물 (서버 + 최소 node_modules)
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
# 정적 자산
COPY --from=builder --chown=nextjs:nodejs /app/.next/static     ./.next/static
# public (이미지/폰트 등)
COPY --from=builder --chown=nextjs:nodejs /app/public           ./public

USER nextjs

EXPOSE 3000

# standalone 빌드의 진입점
CMD ["node", "server.js"]
