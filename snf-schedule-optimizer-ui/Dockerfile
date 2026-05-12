FROM node:24-bookworm-slim AS deps

WORKDIR /app

RUN corepack enable

COPY snf-schedule-optimizer-ui/package.json ./package.json
COPY snf-schedule-optimizer-ui/pnpm-lock.yaml ./pnpm-lock.yaml
COPY snf-schedule-optimizer-ui/pnpm-workspace.yaml ./pnpm-workspace.yaml

RUN pnpm install --frozen-lockfile

FROM deps AS builder

WORKDIR /workspace

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY proto ./proto
COPY snf-schedule-optimizer-ui ./snf-schedule-optimizer-ui

WORKDIR /workspace/proto
RUN npm install
RUN npx buf generate

WORKDIR /workspace/snf-schedule-optimizer-ui
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8080
RUN pnpm build

FROM node:24-bookworm-slim AS runner

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1

WORKDIR /app

RUN corepack enable

COPY --from=builder /workspace/snf-schedule-optimizer-ui/.next/standalone ./
COPY --from=builder /workspace/snf-schedule-optimizer-ui/.next/static ./.next/static
COPY --from=builder /workspace/snf-schedule-optimizer-ui/public ./public

EXPOSE 3000

CMD ["node", "server.js"]
