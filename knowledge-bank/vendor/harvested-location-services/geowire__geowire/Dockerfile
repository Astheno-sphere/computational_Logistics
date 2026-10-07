# syntax=docker/dockerfile:1

# ── builder: 전체 워크스페이스 설치·빌드 후 server만 배포 번들로 추출 ──
FROM node:22-slim AS builder
WORKDIR /repo

RUN corepack enable && corepack prepare pnpm@10.28.0 --activate

# 의존성 캐시 레이어: 매니페스트 먼저 복사
COPY pnpm-workspace.yaml pnpm-lock.yaml package.json turbo.json tsconfig.base.json ./
COPY packages ./packages
COPY apps ./apps

RUN --mount=type=cache,id=pnpm,target=/root/.local/share/pnpm/store \
    pnpm install --frozen-lockfile

RUN pnpm build

# server 패키지 + prod 의존성(workspace 포함)을 /app에 실복사 번들로 추출
# --legacy: pnpm v10에서 non-injected 워크스페이스를 배포하려면 필요
RUN pnpm --filter @geowirehq/server deploy --prod --legacy /app

# ── runner: distroless nodejs (shell 없음, 경량·비루트) ──
FROM gcr.io/distroless/nodejs22-debian12 AS runner
WORKDIR /app

ENV NODE_ENV=production \
    PORT=4980 \
    HOST=0.0.0.0

COPY --from=builder /app /app

EXPOSE 4980
USER nonroot

# distroless nodejs 이미지의 ENTRYPOINT는 node — 스크립트 경로만 넘긴다
CMD ["dist/server.js"]
