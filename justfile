set shell := ["bash", "-cu"]

default:
  @just --list

db_url := "postgresql+asyncpg://snf_user:snf_password@localhost:35435/snf_optimizer_demo"
api_url := "http://localhost:8000"
demo_api_url := "http://localhost:8080"
ui_url := "http://localhost:3000"
e2e_runs := "uv run --project snf-schedule-optimizer-service python tools/e2e/runs.py"

install: install-ui install-be

check: ci

install-ui:
  cd snf-schedule-optimizer-ui && pnpm install

install-be:
  cd snf-schedule-optimizer-service && uv sync

lint-ui:
  cd snf-schedule-optimizer-ui && pnpm lint

typecheck-ui:
  cd snf-schedule-optimizer-ui && pnpm typecheck

test-ui:
  cd snf-schedule-optimizer-ui && pnpm test:unit

build-ui:
  cd snf-schedule-optimizer-ui && pnpm build

lint-be:
  cd snf-schedule-optimizer-service && PYTHONPATH=src uv run ruff check .

typecheck-be:
  cd snf-schedule-optimizer-service && PYTHONPATH=src uv run mypy

test-be:
  cd snf-schedule-optimizer-service && PYTHONPATH=src uv run pytest

proto:
  cd proto && npm install --no-package-lock && npx buf generate && python3 post_generate_fix_imports.py

infra-up:
  docker compose -f compose.dev.yml up -d --remove-orphans db

infra-seed:
  docker compose -f compose.dev.yml up -d --remove-orphans db
  docker compose -f compose.dev.yml --profile tools run --rm seeder

infra-down:
  docker compose -f compose.dev.yml down --remove-orphans

infra-reset:
  docker compose -f compose.dev.yml down -v

infra-ps:
  docker compose -f compose.dev.yml ps -a

infra-logs:
  docker compose -f compose.dev.yml logs db seeder

infra-check:
  PGPASSWORD=snf_password psql -h localhost -p 35435 -U snf_user -d snf_optimizer_demo -c 'select 1'

dev-ui:
  cd snf-schedule-optimizer-ui && NEXT_PUBLIC_API_BASE_URL="${NEXT_PUBLIC_API_BASE_URL:-{{api_url}}}" NEXT_ALLOWED_DEV_ORIGINS="${NEXT_ALLOWED_DEV_ORIGINS:-}" pnpm dev

dev-be:
  extra_origins="${EXTRA_DEV_ORIGINS:-}"; cors_origins="http://localhost:3000,http://127.0.0.1:3000"; if [[ -n "$extra_origins" ]]; then cors_origins="$cors_origins,$extra_origins"; fi; cd snf-schedule-optimizer-service && PYTHONPATH=src DATABASE_URL={{db_url}} CORS_ALLOW_ORIGINS="$cors_origins" uv run uvicorn snf_schedule_optimizer.api.main:app --host 0.0.0.0 --port 8000 --reload

dev:
  @printf 'Run in separate terminals:\n'
  @printf '  just infra-up\n'
  @printf '  just infra-seed\n'
  @printf '  just dev-be\n'
  @printf '  just dev-ui\n'

check-ui:
  cd snf-schedule-optimizer-ui && pnpm lint && pnpm typecheck && pnpm test:unit && pnpm build

check-be:
  cd snf-schedule-optimizer-service && PYTHONPATH=src uv run ruff check . && PYTHONPATH=src uv run mypy && PYTHONPATH=src uv run pytest

check-proto:
  just proto && git diff --exit-code -- proto snf-schedule-optimizer-ui/gen snf-schedule-optimizer-service/src/snf_schedule_optimizer/generated

test-e2e:
  cd snf-schedule-optimizer-ui && NEXT_PUBLIC_API_BASE_URL={{api_url}} node node_modules/@playwright/test/cli.js test

e2e-scenarios scenario="dashboard_smoke" mode="dev":
  {{e2e_runs}} run --mode {{mode}} --scenario {{scenario}}

e2e-scenarios-all mode="dev":
  {{e2e_runs}} run-all --mode {{mode}}

e2e-scenarios-list:
  {{e2e_runs}} list-scenarios

e2e-scenarios-latest-failed:
  {{e2e_runs}} latest-unresolved-failed

e2e-scenarios-unresolved:
  {{e2e_runs}} unresolved-failed

e2e-scenarios-resolve target mode="dev":
  {{e2e_runs}} resolve {{target}} --mode {{mode}}

e2e-scenarios-mark-resolved failed resolved:
  {{e2e_runs}} mark-resolved --failed-run {{failed}} --resolved-by {{resolved}}

smoke-demo:
  docker compose -f compose.demo.yml up --build -d

demo-down:
  docker compose -f compose.demo.yml down -v

demo-ps:
  docker compose -f compose.demo.yml ps -a

demo-logs:
  docker compose -f compose.demo.yml logs app ui db

smoke-demo-check:
  curl --fail --retry 20 --retry-delay 2 {{demo_api_url}}/health
  sleep 5
  for i in $(seq 1 20); do curl --fail {{ui_url}} && exit 0; sleep 2; done; exit 1

ci:
  just check-ui
  just check-be
