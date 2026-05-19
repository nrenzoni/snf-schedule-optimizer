set shell := ["bash", "-cu"]

default:
  @just --list

db_url := "postgresql+asyncpg://snf_user:snf_password@localhost:35435/snf_optimizer_demo"
api_url := "http://localhost:8000"
demo_api_url := "http://localhost:8080"
ui_url := "http://localhost:3000"
e2e_runs := "uv run --project snf-schedule-optimizer-service python tools/e2e/runs.py"
demo_state_env := "tools/.demo-smoke.env"
demo_ports := "uv run --project snf-schedule-optimizer-service python -m tools.demo_ports"

install: install-ui install-be

check:
  just check-ui
  just check-be

ci: check

install-ui:
  cd snf-schedule-optimizer-ui && just install

install-be:
  cd snf-schedule-optimizer-service && just install

lint-ui:
  cd snf-schedule-optimizer-ui && just lint

typecheck-ui:
  cd snf-schedule-optimizer-ui && just typecheck

test-ui:
  cd snf-schedule-optimizer-ui && just test

build-ui:
  cd snf-schedule-optimizer-ui && just build

lint-be:
  cd snf-schedule-optimizer-service && just lint

auto-fix-format-be:
  cd snf-schedule-optimizer-service && just auto-fix-format

typecheck-be:
  cd snf-schedule-optimizer-service && just typecheck

test-be:
  cd snf-schedule-optimizer-service && just test

proto:
  cd proto && just generate

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
  cd snf-schedule-optimizer-ui && NEXT_PUBLIC_API_BASE_URL="${NEXT_PUBLIC_API_BASE_URL:-{{api_url}}}" NEXT_ALLOWED_DEV_ORIGINS="${NEXT_ALLOWED_DEV_ORIGINS:-}" just dev

dev-be:
  extra_origins="${EXTRA_DEV_ORIGINS:-}"; cors_origins="http://localhost:3000,http://127.0.0.1:3000"; if [[ -n "$extra_origins" ]]; then cors_origins="$cors_origins,$extra_origins"; fi; cd snf-schedule-optimizer-service && DATABASE_URL={{db_url}} CORS_ALLOW_ORIGINS="$cors_origins" just dev

dev-worker:
  cd snf-schedule-optimizer-service && DATABASE_URL={{db_url}} just dev-worker

dev:
  @printf 'Run in separate terminals:\n'
  @printf '  just infra-up\n'
  @printf '  just infra-seed\n'
  @printf '  just dev-be\n'
  @printf '  just dev-worker\n'
  @printf '  just dev-ui\n'

check-ui:
  cd snf-schedule-optimizer-ui && just check

check-be:
  cd snf-schedule-optimizer-service && just check

check-proto:
  just proto && git diff --exit-code -- proto snf-schedule-optimizer-ui/gen snf-schedule-optimizer-service/src/snf_schedule_optimizer/generated

test-e2e:
  uv run --project snf-schedule-optimizer-service python -m tools.e2e.run_playwright

e2e-scenarios scenario="dashboard_smoke" mode="dev":
  selected_mode="{{mode}}"; if [[ "$selected_mode" == mode=* ]]; then selected_mode="${selected_mode#mode=}"; fi; {{e2e_runs}} run --mode "$selected_mode" --scenario {{scenario}}

e2e-scenarios-all mode="dev":
  selected_mode="{{mode}}"; if [[ "$selected_mode" == mode=* ]]; then selected_mode="${selected_mode#mode=}"; fi; {{e2e_runs}} run-all --mode "$selected_mode"

e2e-scenarios-list:
  {{e2e_runs}} list-scenarios

e2e-scenarios-latest-failed:
  {{e2e_runs}} latest-unresolved-failed

e2e-scenarios-unresolved:
  {{e2e_runs}} unresolved-failed

e2e-scenarios-resolve target mode="dev":
  selected_mode="{{mode}}"; if [[ "$selected_mode" == mode=* ]]; then selected_mode="${selected_mode#mode=}"; fi; {{e2e_runs}} resolve {{target}} --mode "$selected_mode"

e2e-scenarios-mark-resolved failed resolved:
  {{e2e_runs}} mark-resolved --failed-run {{failed}} --resolved-by {{resolved}}

smoke-demo:
  {{demo_ports}} write-env --path {{demo_state_env}}
  docker compose --env-file {{demo_state_env}} -f compose.demo.yml up --build -d
  source {{demo_state_env}} && printf 'Demo API: http://localhost:%s\nDemo UI: http://localhost:%s\n' "$DEMO_API_PORT" "$DEMO_UI_PORT"

demo-down:
  if [[ -f {{demo_state_env}} ]]; then docker compose --env-file {{demo_state_env}} -f compose.demo.yml down -v; else docker compose -f compose.demo.yml down -v; fi
  rm -f {{demo_state_env}}

demo-ps:
  if [[ -f {{demo_state_env}} ]]; then docker compose --env-file {{demo_state_env}} -f compose.demo.yml ps -a; else docker compose -f compose.demo.yml ps -a; fi

demo-logs:
  if [[ -f {{demo_state_env}} ]]; then docker compose --env-file {{demo_state_env}} -f compose.demo.yml logs app ui db; else docker compose -f compose.demo.yml logs app ui db; fi

smoke-demo-check:
  if [[ ! -f {{demo_state_env}} ]]; then printf 'Missing %s. Run just smoke-demo first.\n' {{demo_state_env}}; exit 1; fi
  source {{demo_state_env}} && curl --fail --retry 20 --retry-delay 2 "http://localhost:$DEMO_API_PORT/health"
  source {{demo_state_env}} && sleep 5 && for i in $(seq 1 20); do curl --fail "http://localhost:$DEMO_UI_PORT" && exit 0; sleep 2; done; exit 1
