#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SOURCE_DOCKER="$ROOT_DIR/docker"
mkdir -p "$ROOT_DIR/tmp"
TMP_ROOT="$(mktemp -d "$ROOT_DIR/tmp/docker-config-test.XXXXXX")"
FIXTURE="$TMP_ROOT/repo/docker"
FAKE_BIN="$TMP_ROOT/bin"
DOCKER_LOG="$TMP_ROOT/docker.log"
SECRET_EVAL_MARKER="$TMP_ROOT/secret-evaluated"

cleanup() { rm -rf "$TMP_ROOT"; }
trap cleanup EXIT

fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }
assert_contains() { grep -Fq -- "$2" "$1" || fail "$1 does not contain $2"; }
assert_not_contains() { ! grep -Fq -- "$2" "$1" || fail "$1 unexpectedly contains $2"; }
assert_mode_600() { [[ "$(stat -c '%a' "$1")" == "600" ]] || fail "$1 is not mode 0600"; }

mkdir -p "$FIXTURE/config/defaults" "$FIXTURE/config/overrides" "$FIXTURE/config/secrets" "$FIXTURE/tests" "$FAKE_BIN" "$TMP_ROOT/repo/.bin"
cp "$SOURCE_DOCKER/render-config.sh" "$SOURCE_DOCKER/run.sh" "$SOURCE_DOCKER/docker-compose.yml" "$SOURCE_DOCKER/docker-compose.prod.yml" "$FIXTURE/"
cp "$SOURCE_DOCKER/config/schema.yaml" "$FIXTURE/config/"
cp "$SOURCE_DOCKER/config/defaults/common.yaml" "$SOURCE_DOCKER/config/defaults/production.yaml" "$SOURCE_DOCKER/config/defaults/local.yaml" "$FIXTURE/config/defaults/"
cp "$SOURCE_DOCKER/config/overrides/production.example.yaml" "$SOURCE_DOCKER/config/overrides/local.example.yaml" "$FIXTURE/config/overrides/"
cp "$SOURCE_DOCKER/config/secrets/production.example.env" "$SOURCE_DOCKER/config/secrets/local.example.env" "$FIXTURE/config/secrets/"

# Shutdown must remain available before any live override, secrets, generated env, or yq exists.
EARLY_BIN="$TMP_ROOT/early-bin"
EARLY_DOCKER_LOG="$TMP_ROOT/early-docker.log"
EARLY_YQ_MARKER="$TMP_ROOT/early-yq-invoked"
mkdir -p "$EARLY_BIN"
cat > "$EARLY_BIN/docker" <<EOF
#!/usr/bin/env bash
printf '%s\n' "\$*" >> '$EARLY_DOCKER_LOG'
EOF
cat > "$EARLY_BIN/yq" <<EOF
#!/usr/bin/env bash
touch '$EARLY_YQ_MARKER'
exit 99
EOF
chmod +x "$EARLY_BIN/docker" "$EARLY_BIN/yq"
PATH="$EARLY_BIN:/usr/bin:/bin" bash -c "cd '$FIXTURE' && ./run.sh prod down" >/dev/null
PATH="$EARLY_BIN:/usr/bin:/bin" bash -c "cd '$FIXTURE' && ./run.sh prod down -v" >/dev/null
EXPECTED_EARLY_DOWN=$(cat <<'EOF'
compose -f docker-compose.prod.yml down
compose -f docker-compose.prod.yml down -v
EOF
)
[[ "$(cat "$EARLY_DOCKER_LOG")" == "$EXPECTED_EARLY_DOWN" ]] || fail "pre-configuration shutdown routed unexpected Compose arguments"
[[ ! -e "$EARLY_YQ_MARKER" ]] || fail "pre-configuration shutdown invoked yq"
[[ ! -e "$FIXTURE/config/overrides/production.yaml" ]] || fail "shutdown created a production override"
[[ ! -e "$FIXTURE/config/secrets/production.env" ]] || fail "shutdown created production secrets"
[[ ! -e "$FIXTURE/env/.env.prod" ]] || fail "shutdown generated a production env"

YQ_SOURCE="$(command -v yq || true)"
[[ -n "$YQ_SOURCE" ]] || fail "Mike Farah yq v4 is required for the focused config test"
if [[ "$(readlink -f "$YQ_SOURCE")" == "/usr/bin/snap" ]]; then
    YQ_SOURCE="$(snap run --shell yq -c 'command -v yq')"
fi
ln -s "$YQ_SOURCE" "$TMP_ROOT/repo/.bin/yq"
chmod +x "$FIXTURE/render-config.sh" "$FIXTURE/run.sh"
YQ="$TMP_ROOT/repo/.bin/yq"

write_secrets() {
    local profile="$1"
    cat > "$FIXTURE/config/secrets/$profile.env" <<'EOF'
NUXT_SESSION_PASSWORD=test-session-value
MASTER_OPEN_ROUTER_API_KEY=test-open-router=value#fragment
BACKEND_SECRET=test-backend-value
JWT_SECRET_KEY=test-jwt-value
LINK_EXTRACTION_BROWSER_SERVICE_TOKEN=test-browser-token-value
REDIS_PASSWORD=test-redis-value
POSTGRES_PASSWORD=test-postgres-value
NEO4J_PASSWORD=test-neo4j-value
USERPASS="test-admin:test-password"
LINK_EXTRACTION_BROWSER_PROXY_URL="http://test-user:test-pass@proxy.invalid:8080/path?x=1#fragment"
EOF
    printf 'GITHUB_CLIENT_SECRET=$(touch %s)\n' "$SECRET_EVAL_MARKER" >> "$FIXTURE/config/secrets/$profile.env"
    printf 'SMTP_PASSWORD=`touch %s`\n' "$SECRET_EVAL_MARKER" >> "$FIXTURE/config/secrets/$profile.env"
    printf 'AWS_ACCESS_KEY_ID="access=value#fragment"\n' >> "$FIXTURE/config/secrets/$profile.env"
    printf 'AWS_SECRET_ACCESS_KEY=$(touch %s)\n' "$SECRET_EVAL_MARKER" >> "$FIXTURE/config/secrets/$profile.env"
    printf 'AWS_SESSION_TOKEN=`touch %s`\n' "$SECRET_EVAL_MARKER" >> "$FIXTURE/config/secrets/$profile.env"
}

write_secrets local
write_secrets production

EXPECTED_KEYS="
ENV NAME ADMIN_USER_CREATION NITRO_PORT NUXT_PUBLIC_API_BASE_URL NUXT_API_INTERNAL_BASE_URL
NUXT_PUBLIC_IS_OAUTH_DISABLED NUXT_OAUTH_GITHUB_CLIENT_ID NUXT_OAUTH_GOOGLE_CLIENT_ID API_PORT
PYTHONUNBUFFERED ALLOW_CORS_ORIGINS DATABASE_ECHO PLAN_FREE_WEB_SEARCH_LIMIT
PLAN_FREE_LINK_EXTRACTION_LIMIT PLAN_FREE_STORAGE_LIMIT_MIB PLAN_PREMIUM_WEB_SEARCH_LIMIT
PLAN_PREMIUM_LINK_EXTRACTION_LIMIT PLAN_PREMIUM_STORAGE_LIMIT_MIB SEARXNG_URL GOOGLE_CSE_ID
LINK_EXTRACTION_BROWSER_SERVICE_PORT LINK_EXTRACTION_BROWSER_SERVICE_URL SANDBOX_MANAGER_PORT
SANDBOX_MANAGER_URL MAX_CONCURRENT_SANDBOXES SANDBOX_QUEUE_WAIT_SECONDS EXECUTION_TIMEOUT_SECONDS
SANDBOX_OUTPUT_LIMIT_BYTES SANDBOX_CODE_MAX_BYTES SANDBOX_ARTIFACT_MAX_FILES
SANDBOX_ARTIFACT_MAX_FILE_BYTES SANDBOX_ARTIFACT_MAX_TOTAL_BYTES SANDBOX_INPUT_MAX_FILES
SANDBOX_INPUT_MAX_FILE_BYTES SANDBOX_INPUT_MAX_TOTAL_BYTES SANDBOX_MEMORY_LIMIT
SANDBOX_CPU_NANO_CPUS SANDBOX_PIDS_LIMIT SANDBOX_TMPFS_SIZE SANDBOX_RUNTIME REDIS_HOST REDIS_PORT
POSTGRES_DB POSTGRES_USER POSTGRES_HOST POSTGRES_PORT DATABASE_POOL_SIZE DATABASE_MAX_OVERFLOW
POSTGRES_SHARED_BUFFERS POSTGRES_EFFECTIVE_CACHE_SIZE POSTGRES_WORK_MEM POSTGRES_MAINTENANCE_WORK_MEM
POSTGRES_RANDOM_PAGE_COST POSTGRES_MAX_WORKER_PROCESSES POSTGRES_MAX_PARALLEL_WORKERS_PER_GATHER
POSTGRES_MAX_PARALLEL_WORKERS POSTGRES_LOG_MIN_DURATION_STATEMENT POSTGRES_LOG_LOCK_WAITS NEO4J_USER
NEO4J_HOST NEO4J_BOLT_PORT NEO4J_BOLT_ADDRESS NEO4J_HTTP_PORT NEO4J_HTTP_ADDRESS GITHUB_CLIENT_ID
GITHUB_REDIRECT_URI SENTRY_DSN EMAIL_PROVIDER SMTP_SERVER SMTP_PORT SMTP_USERNAME SMTP_AUTH_PROTOCOL
SMTP_FROM_EMAIL SES_REGION SES_FROM_EMAIL SES_CONFIGURATION_SET_NAME
NUXT_SESSION_PASSWORD MASTER_OPEN_ROUTER_API_KEY BACKEND_SECRET JWT_SECRET_KEY
LINK_EXTRACTION_BROWSER_SERVICE_TOKEN REDIS_PASSWORD POSTGRES_PASSWORD NEO4J_PASSWORD USERPASS
NUXT_OAUTH_GITHUB_CLIENT_SECRET NUXT_OAUTH_GOOGLE_CLIENT_SECRET GOOGLE_SEARCH_API_KEY
LINK_EXTRACTION_BROWSER_PROXY_URL GITHUB_CLIENT_SECRET SMTP_PASSWORD AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN
"

EXPECTED_MAPPINGS=$(cat <<'EOF'
deployment.environment=ENV
deployment.name=NAME
deployment.admin_user_creation=ADMIN_USER_CREATION
ui.port=NITRO_PORT
ui.api.public_base_url=NUXT_PUBLIC_API_BASE_URL
ui.api.internal_base_url=NUXT_API_INTERNAL_BASE_URL
ui.oauth.disabled=NUXT_PUBLIC_IS_OAUTH_DISABLED
ui.oauth.github.client_id=NUXT_OAUTH_GITHUB_CLIENT_ID
ui.oauth.google.client_id=NUXT_OAUTH_GOOGLE_CLIENT_ID
api.port=API_PORT
api.logging.unbuffered=PYTHONUNBUFFERED
api.cors.allowed_origins=ALLOW_CORS_ORIGINS
api.database.echo_queries=DATABASE_ECHO
limits.free.web_search=PLAN_FREE_WEB_SEARCH_LIMIT
limits.free.link_extraction=PLAN_FREE_LINK_EXTRACTION_LIMIT
limits.free.storage_mib=PLAN_FREE_STORAGE_LIMIT_MIB
limits.premium.web_search=PLAN_PREMIUM_WEB_SEARCH_LIMIT
limits.premium.link_extraction=PLAN_PREMIUM_LINK_EXTRACTION_LIMIT
limits.premium.storage_mib=PLAN_PREMIUM_STORAGE_LIMIT_MIB
search.searxng.url=SEARXNG_URL
search.google.cse_id=GOOGLE_CSE_ID
browser.port=LINK_EXTRACTION_BROWSER_SERVICE_PORT
browser.service_url=LINK_EXTRACTION_BROWSER_SERVICE_URL
sandbox.manager.port=SANDBOX_MANAGER_PORT
sandbox.manager.url=SANDBOX_MANAGER_URL
sandbox.capacity.max_concurrent=MAX_CONCURRENT_SANDBOXES
sandbox.queue.wait_seconds=SANDBOX_QUEUE_WAIT_SECONDS
sandbox.execution.timeout_seconds=EXECUTION_TIMEOUT_SECONDS
sandbox.execution.output_limit_bytes=SANDBOX_OUTPUT_LIMIT_BYTES
sandbox.execution.code_max_bytes=SANDBOX_CODE_MAX_BYTES
sandbox.artifacts.max_files=SANDBOX_ARTIFACT_MAX_FILES
sandbox.artifacts.max_file_bytes=SANDBOX_ARTIFACT_MAX_FILE_BYTES
sandbox.artifacts.max_total_bytes=SANDBOX_ARTIFACT_MAX_TOTAL_BYTES
sandbox.inputs.max_files=SANDBOX_INPUT_MAX_FILES
sandbox.inputs.max_file_bytes=SANDBOX_INPUT_MAX_FILE_BYTES
sandbox.inputs.max_total_bytes=SANDBOX_INPUT_MAX_TOTAL_BYTES
sandbox.resources.memory_limit=SANDBOX_MEMORY_LIMIT
sandbox.resources.cpu_nano_cpus=SANDBOX_CPU_NANO_CPUS
sandbox.resources.pids_limit=SANDBOX_PIDS_LIMIT
sandbox.resources.tmpfs_size=SANDBOX_TMPFS_SIZE
sandbox.runtime=SANDBOX_RUNTIME
redis.host=REDIS_HOST
redis.port=REDIS_PORT
postgres.database=POSTGRES_DB
postgres.username=POSTGRES_USER
postgres.host=POSTGRES_HOST
postgres.port=POSTGRES_PORT
postgres.pool.size=DATABASE_POOL_SIZE
postgres.pool.max_overflow=DATABASE_MAX_OVERFLOW
postgres.tuning.shared_buffers=POSTGRES_SHARED_BUFFERS
postgres.tuning.effective_cache_size=POSTGRES_EFFECTIVE_CACHE_SIZE
postgres.tuning.work_mem=POSTGRES_WORK_MEM
postgres.tuning.maintenance_work_mem=POSTGRES_MAINTENANCE_WORK_MEM
postgres.tuning.random_page_cost=POSTGRES_RANDOM_PAGE_COST
postgres.tuning.max_worker_processes=POSTGRES_MAX_WORKER_PROCESSES
postgres.tuning.max_parallel_workers_per_gather=POSTGRES_MAX_PARALLEL_WORKERS_PER_GATHER
postgres.tuning.max_parallel_workers=POSTGRES_MAX_PARALLEL_WORKERS
postgres.logging.min_duration_statement=POSTGRES_LOG_MIN_DURATION_STATEMENT
postgres.logging.lock_waits=POSTGRES_LOG_LOCK_WAITS
neo4j.username=NEO4J_USER
neo4j.host=NEO4J_HOST
neo4j.bolt.port=NEO4J_BOLT_PORT
neo4j.bolt.address=NEO4J_BOLT_ADDRESS
neo4j.http.port=NEO4J_HTTP_PORT
neo4j.http.address=NEO4J_HTTP_ADDRESS
integrations.github.client_id=GITHUB_CLIENT_ID
integrations.github.redirect_uri=GITHUB_REDIRECT_URI
observability.sentry.dsn=SENTRY_DSN
email.provider=EMAIL_PROVIDER
email.smtp.server=SMTP_SERVER
email.smtp.port=SMTP_PORT
email.smtp.username=SMTP_USERNAME
email.smtp.auth_protocol=SMTP_AUTH_PROTOCOL
email.smtp.from_email=SMTP_FROM_EMAIL
email.ses.region=SES_REGION
email.ses.from_email=SES_FROM_EMAIL
email.ses.configuration_set_name=SES_CONFIGURATION_SET_NAME
EOF
)

ACTUAL_MAPPINGS="$("$YQ" -r '.settings[] | .path + "=" + .env' "$FIXTURE/config/schema.yaml")"
[[ "$(printf '%s\n' "$ACTUAL_MAPPINGS" | sort)" == "$(printf '%s\n' "$EXPECTED_MAPPINGS" | sort)" ]] || fail "friendly path to env mapping inventory differs"
[[ "$(printf '%s\n' "$ACTUAL_MAPPINGS" | cut -d= -f1 | sort | uniq -d)" == "" ]] || fail "duplicate friendly schema path"

for compose_file in "$FIXTURE/docker-compose.yml" "$FIXTURE/docker-compose.prod.yml"; do
    API_ENVIRONMENT="$("$YQ" -r '.services.api.environment[]' "$compose_file")"
    for key in EMAIL_PROVIDER SES_REGION SES_FROM_EMAIL SES_CONFIGURATION_SET_NAME AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN; do
        [[ "$API_ENVIRONMENT" == *"$key="* ]] || fail "$key is not forwarded to API in $compose_file"
        [[ "$(grep -Fc -- "- $key=\${$key}" "$compose_file")" == "1" ]] || fail "$key is forwarded outside API or duplicated in $compose_file"
    done
done

assert_key_inventory() {
    local file="$1" expected="$2" actual expected_sorted
    actual="$(grep -E '^[A-Z][A-Z0-9_]*=' "$file" | cut -d= -f1 | sort)"
    expected_sorted="$(printf '%s\n' $expected | sed '/^$/d' | sort)"
    [[ "$actual" == "$expected_sorted" ]] || fail "rendered env key inventory differs for $file"
    [[ "$(printf '%s\n' "$actual" | uniq -d)" == "" ]] || fail "duplicate rendered key in $file"
}

(cd "$FIXTURE" && ./render-config.sh production)
(cd "$FIXTURE" && ./render-config.sh local)

PROD_ENV="$FIXTURE/env/.env.prod"
LOCAL_COMPOSE_ENV="$FIXTURE/env/.env.compose.local"
LOCAL_ENV="$FIXTURE/env/.env.local"
assert_key_inventory "$PROD_ENV" "$EXPECTED_KEYS"
assert_key_inventory "$LOCAL_COMPOSE_ENV" "$EXPECTED_KEYS"
assert_key_inventory "$LOCAL_ENV" "${EXPECTED_KEYS/LINK_EXTRACTION_BROWSER_PROXY_URL/}"
assert_mode_600 "$PROD_ENV"
assert_mode_600 "$LOCAL_COMPOSE_ENV"
assert_mode_600 "$LOCAL_ENV"

assert_contains "$PROD_ENV" "ENV=prod"
assert_contains "$PROD_ENV" "NAME=meridian_prod"
assert_contains "$PROD_ENV" "NUXT_API_INTERNAL_BASE_URL=http://api:8000"
assert_contains "$PROD_ENV" "POSTGRES_HOST=db"
assert_contains "$LOCAL_ENV" "ENV=dev"
assert_contains "$LOCAL_ENV" "NAME=meridian"
assert_contains "$LOCAL_ENV" "POSTGRES_HOST=localhost"
assert_contains "$LOCAL_COMPOSE_ENV" 'LINK_EXTRACTION_BROWSER_PROXY_URL="http://test-user:test-pass@proxy.invalid:8080/path?x=1#fragment"'
assert_not_contains "$LOCAL_ENV" "LINK_EXTRACTION_BROWSER_PROXY_URL="
printf -v EXPECTED_COMMAND_SUBSTITUTION 'GITHUB_CLIENT_SECRET=$(touch %s)' "$SECRET_EVAL_MARKER"
printf -v EXPECTED_BACKTICK 'SMTP_PASSWORD=`touch %s`' "$SECRET_EVAL_MARKER"
printf -v EXPECTED_AWS_COMMAND_SUBSTITUTION 'AWS_SECRET_ACCESS_KEY=$(touch %s)' "$SECRET_EVAL_MARKER"
printf -v EXPECTED_AWS_BACKTICK 'AWS_SESSION_TOKEN=`touch %s`' "$SECRET_EVAL_MARKER"
assert_contains "$PROD_ENV" "$EXPECTED_COMMAND_SUBSTITUTION"
assert_contains "$PROD_ENV" "$EXPECTED_BACKTICK"
assert_contains "$PROD_ENV" 'AWS_ACCESS_KEY_ID="access=value#fragment"'
assert_contains "$PROD_ENV" "$EXPECTED_AWS_COMMAND_SUBSTITUTION"
assert_contains "$PROD_ENV" "$EXPECTED_AWS_BACKTICK"
assert_contains "$LOCAL_COMPOSE_ENV" "$EXPECTED_COMMAND_SUBSTITUTION"
assert_contains "$LOCAL_ENV" "$EXPECTED_BACKTICK"
assert_contains "$LOCAL_COMPOSE_ENV" 'AWS_ACCESS_KEY_ID="access=value#fragment"'
assert_contains "$LOCAL_COMPOSE_ENV" "$EXPECTED_AWS_COMMAND_SUBSTITUTION"
assert_contains "$LOCAL_ENV" "$EXPECTED_AWS_BACKTICK"
[[ ! -e "$SECRET_EVAL_MARKER" ]] || fail "secret parser executed a secret value"
for pair in \
    "PLAN_FREE_WEB_SEARCH_LIMIT=0" \
    "PLAN_FREE_LINK_EXTRACTION_LIMIT=0" \
    "PLAN_FREE_STORAGE_LIMIT_MIB=50" \
    "PLAN_PREMIUM_WEB_SEARCH_LIMIT=200" \
    "PLAN_PREMIUM_LINK_EXTRACTION_LIMIT=1000" \
    "PLAN_PREMIUM_STORAGE_LIMIT_MIB=5120"; do
    assert_contains "$PROD_ENV" "$pair"
done

FIRST_HASH="$(sha256sum "$PROD_ENV" | cut -d' ' -f1)"
(cd "$FIXTURE" && ./render-config.sh production >/dev/null)
[[ "$FIRST_HASH" == "$(sha256sum "$PROD_ENV" | cut -d' ' -f1)" ]] || fail "rendering is not deterministic"
LOCAL_COMPOSE_HASH="$(sha256sum "$LOCAL_COMPOSE_ENV" | cut -d' ' -f1)"
LOCAL_HOST_HASH="$(sha256sum "$LOCAL_ENV" | cut -d' ' -f1)"
(cd "$FIXTURE" && ./render-config.sh local >/dev/null)
[[ "$LOCAL_COMPOSE_HASH" == "$(sha256sum "$LOCAL_COMPOSE_ENV" | cut -d' ' -f1)" ]] || fail "local Compose rendering is not deterministic"
[[ "$LOCAL_HOST_HASH" == "$(sha256sum "$LOCAL_ENV" | cut -d' ' -f1)" ]] || fail "local host rendering is not deterministic"
[[ ! -e "$SECRET_EVAL_MARKER" ]] || fail "repeat rendering executed a secret value"

cat > "$FIXTURE/config/overrides/production.yaml" <<'EOF'
version: 1
settings:
  postgres:
    tuning:
      work_mem: "64MB"
  limits:
    free:
      web_search: 7
EOF
(cd "$FIXTURE" && ./render-config.sh production >/dev/null)
assert_contains "$PROD_ENV" "POSTGRES_WORK_MEM=64MB"
assert_contains "$PROD_ENV" "POSTGRES_SHARED_BUFFERS=4GB"
assert_contains "$PROD_ENV" "PLAN_FREE_WEB_SEARCH_LIMIT=7"
(cd "$FIXTURE" && ./render-config.sh local >/dev/null)
assert_contains "$LOCAL_ENV" "POSTGRES_WORK_MEM=32MB"
rm "$FIXTURE/config/overrides/production.yaml"

cp "$PROD_ENV" "$TMP_ROOT/valid-prod.env"
printf 'sentinel\n' > "$PROD_ENV"
cat > "$FIXTURE/config/overrides/production.yaml" <<'EOF'
version: 1
settings:
  unknown: {}
EOF
if (cd "$FIXTURE" && ./render-config.sh production >"$TMP_ROOT/failure.out" 2>"$TMP_ROOT/failure.err"); then
    fail "unknown empty mapping was accepted"
fi
[[ "$(cat "$PROD_ENV")" == "sentinel" ]] || fail "failed render replaced prior output"
assert_contains "$TMP_ROOT/failure.err" "unknown"
assert_not_contains "$TMP_ROOT/failure.err" "test-open-router=value#fragment"

printf 'local-compose-sentinel\n' > "$LOCAL_COMPOSE_ENV"
printf 'local-host-sentinel\n' > "$LOCAL_ENV"
cat > "$FIXTURE/config/overrides/local.yaml" <<'EOF'
version: 1
settings:
  unknown: {}
EOF
if (cd "$FIXTURE" && ./render-config.sh local >/dev/null 2>"$TMP_ROOT/local-failure.err"); then
    fail "invalid local override was accepted"
fi
[[ "$(cat "$LOCAL_COMPOSE_ENV")" == "local-compose-sentinel" ]] || fail "failed local render replaced Compose output"
[[ "$(cat "$LOCAL_ENV")" == "local-host-sentinel" ]] || fail "failed local render replaced host output"
assert_contains "$TMP_ROOT/local-failure.err" "unknown"
assert_not_contains "$TMP_ROOT/local-failure.err" "test-open-router=value#fragment"
[[ ! -e "$SECRET_EVAL_MARKER" ]] || fail "failed local validation executed a secret value"
rm "$FIXTURE/config/overrides/local.yaml"
(cd "$FIXTURE" && ./render-config.sh local >/dev/null)

expect_override_failure() {
    local name="$1" content="$2" expected="$3"
    printf '%s\n' "$content" > "$FIXTURE/config/overrides/production.yaml"
    if (cd "$FIXTURE" && ./render-config.sh production >/dev/null 2>"$TMP_ROOT/$name.err"); then
        fail "$name override was accepted"
    fi
    assert_contains "$TMP_ROOT/$name.err" "$expected"
    assert_not_contains "$TMP_ROOT/$name.err" "test-open-router=value#fragment"
}

expect_override_failure wrong-version $'version: 2\nsettings: {}' "version"
expect_override_failure unknown-top $'version: 1\nsettings: {}\nextra: true' "top-level"
expect_override_failure unknown-leaf $'version: 1\nsettings:\n  postgres:\n    unknown_leaf: 1' "postgres.unknown_leaf"
expect_override_failure uppercase-path $'version: 1\nsettings:\n  postgres:\n    HOST: localhost' "postgres.HOST"
expect_override_failure yaml-secret $'version: 1\nsettings:\n  postgres_password: unsafe' "postgres_password"
expect_override_failure wrong-type $'version: 1\nsettings:\n  postgres:\n    port: "5432"' "postgres.port"
expect_override_failure null-value $'version: 1\nsettings:\n  postgres:\n    port: null' "postgres.port"
expect_override_failure sequence-value $'version: 1\nsettings:\n  postgres:\n    port: [5432]' "postgres.port"
expect_override_failure multiline-value $'version: 1\nsettings:\n  postgres:\n    database: |\n      first\n      second' "postgres.database"

cat > "$FIXTURE/config/overrides/production.yaml" <<'EOF'
version: 1
settings:
  limits:
    premium:
      storage_mib: -1
EOF
if (cd "$FIXTURE" && ./render-config.sh production >/dev/null 2>"$TMP_ROOT/negative.err"); then
    fail "negative plan limit was accepted"
fi
assert_contains "$TMP_ROOT/negative.err" "limits.premium.storage_mib"
rm "$FIXTURE/config/overrides/production.yaml"

for limit_path in \
    limits.free.web_search \
    limits.free.link_extraction \
    limits.free.storage_mib \
    limits.premium.web_search \
    limits.premium.link_extraction \
    limits.premium.storage_mib; do
    section="${limit_path#limits.}"
    plan="${section%%.*}"
    field="${section#*.}"
    printf 'version: 1\nsettings:\n  limits:\n    %s:\n      %s: -1\n' "$plan" "$field" > "$FIXTURE/config/overrides/production.yaml"
    if (cd "$FIXTURE" && ./render-config.sh production >/dev/null 2>"$TMP_ROOT/limit.err"); then
        fail "negative $limit_path was accepted"
    fi
    assert_contains "$TMP_ROOT/limit.err" "$limit_path"
done
rm "$FIXTURE/config/overrides/production.yaml"

cp "$FIXTURE/config/secrets/production.env" "$TMP_ROOT/production.secrets"
printf 'POSTGRES_PASSWORD=duplicate-test-value\n' >> "$FIXTURE/config/secrets/production.env"
if (cd "$FIXTURE" && ./render-config.sh production >/dev/null 2>"$TMP_ROOT/secret.err"); then
    fail "duplicate secret was accepted"
fi
assert_contains "$TMP_ROOT/secret.err" "POSTGRES_PASSWORD"
assert_not_contains "$TMP_ROOT/secret.err" "duplicate-test-value"
cp "$TMP_ROOT/production.secrets" "$FIXTURE/config/secrets/production.env"

mv "$FIXTURE/config/secrets/production.env" "$FIXTURE/config/secrets/production.missing"
if (cd "$FIXTURE" && ./render-config.sh production >/dev/null 2>"$TMP_ROOT/missing-secret-file.err"); then
    fail "missing secrets file was accepted"
fi
assert_contains "$TMP_ROOT/missing-secret-file.err" "production.env"
mv "$FIXTURE/config/secrets/production.missing" "$FIXTURE/config/secrets/production.env"

printf 'MALFORMED SECRET LINE\n' >> "$FIXTURE/config/secrets/production.env"
if (cd "$FIXTURE" && ./render-config.sh production >/dev/null 2>"$TMP_ROOT/malformed-secret.err"); then
    fail "malformed secret line was accepted"
fi
assert_contains "$TMP_ROOT/malformed-secret.err" "malformed"
cp "$TMP_ROOT/production.secrets" "$FIXTURE/config/secrets/production.env"

printf 'UNKNOWN_SECRET=test-unknown-value\n' >> "$FIXTURE/config/secrets/production.env"
if (cd "$FIXTURE" && ./render-config.sh production >/dev/null 2>"$TMP_ROOT/unknown-secret.err"); then
    fail "unknown secret was accepted"
fi
assert_contains "$TMP_ROOT/unknown-secret.err" "UNKNOWN_SECRET"
assert_not_contains "$TMP_ROOT/unknown-secret.err" "test-unknown-value"
cp "$TMP_ROOT/production.secrets" "$FIXTURE/config/secrets/production.env"

sed 's/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=""/' "$TMP_ROOT/production.secrets" > "$FIXTURE/config/secrets/production.env"
if (cd "$FIXTURE" && ./render-config.sh production >/dev/null 2>"$TMP_ROOT/empty-secret.err"); then
    fail "empty required secret was accepted"
fi
assert_contains "$TMP_ROOT/empty-secret.err" "POSTGRES_PASSWORD"
grep -v '^POSTGRES_PASSWORD=' "$TMP_ROOT/production.secrets" > "$FIXTURE/config/secrets/production.env"
if (cd "$FIXTURE" && ./render-config.sh production >/dev/null 2>"$TMP_ROOT/absent-secret.err"); then
    fail "absent required secret was accepted"
fi
assert_contains "$TMP_ROOT/absent-secret.err" "POSTGRES_PASSWORD"
cp "$TMP_ROOT/production.secrets" "$FIXTURE/config/secrets/production.env"

(cd "$FIXTURE" && ./render-config.sh production >/dev/null)

# A compatible PATH yq is used when no repository-local executable exists.
rm "$TMP_ROOT/repo/.bin/yq"
mkdir -p "$TMP_ROOT/system-bin"
ln -s "$YQ_SOURCE" "$TMP_ROOT/system-bin/yq"
PATH="$TMP_ROOT/system-bin:/usr/bin:/bin" bash -c "cd '$FIXTURE' && ./render-config.sh production" >/dev/null
[[ ! -e "$TMP_ROOT/repo/.bin/yq" ]] || fail "compatible PATH yq unexpectedly triggered installation"

# Incompatible yq plus a failed downloader is actionable and leaves output untouched.
mkdir -p "$TMP_ROOT/download-bin"
cat > "$TMP_ROOT/download-bin/yq" <<'EOF'
#!/usr/bin/env bash
exit 1
EOF
cat > "$TMP_ROOT/download-bin/curl" <<'EOF'
#!/usr/bin/env bash
exit 1
EOF
chmod +x "$TMP_ROOT/download-bin/yq" "$TMP_ROOT/download-bin/curl"
DOWNLOAD_SENTINEL="$(sha256sum "$PROD_ENV" | cut -d' ' -f1)"
if PATH="$TMP_ROOT/download-bin:/usr/bin:/bin" bash -c "cd '$FIXTURE' && ./render-config.sh production" >/dev/null 2>"$TMP_ROOT/download.err"; then
    fail "failed yq download unexpectedly succeeded"
fi
assert_contains "$TMP_ROOT/download.err" "Failed to download yq"
[[ "$DOWNLOAD_SENTINEL" == "$(sha256sum "$PROD_ENV" | cut -d' ' -f1)" ]] || fail "yq bootstrap failure replaced prior output"
ln -s "$YQ_SOURCE" "$TMP_ROOT/repo/.bin/yq"

cat > "$FAKE_BIN/docker" <<EOF
#!/usr/bin/env bash
printf '%s\n' "\$*" >> '$DOCKER_LOG'
exit 0
EOF
chmod +x "$FAKE_BIN/docker"
cat > "$FAKE_BIN/curl" <<'EOF'
#!/usr/bin/env bash
exit 1
EOF
chmod +x "$FAKE_BIN/curl"
: > "$DOCKER_LOG"
PATH="$FAKE_BIN:$PATH" bash -c "cd '$FIXTURE' && ./run.sh dev --config-only"
PATH="$FAKE_BIN:$PATH" bash -c "cd '$FIXTURE' && ./run.sh dev --sandbox-manager --config-only"
PATH="$FAKE_BIN:$PATH" bash -c "cd '$FIXTURE' && ./run.sh prod v2.3.4 --config-only"
assert_contains "$PROD_ENV" "SANDBOX_WORKER_IMAGE=ghcr.io/mathisverstrepen/meridian/sandbox-python:2.3.4"
PATH="$FAKE_BIN:$PATH" bash -c "cd '$FIXTURE' && ./run.sh build --config-only"
assert_contains "$PROD_ENV" "SANDBOX_WORKER_IMAGE=meridian_prod_sandbox_python:local"
[[ ! -s "$DOCKER_LOG" ]] || fail "--config-only invoked Docker"

PATH="$FAKE_BIN:$PATH" bash -c "cd '$FIXTURE' && ./run.sh prod down" >/dev/null
PATH="$FAKE_BIN:$PATH" bash -c "cd '$FIXTURE' && ./run.sh prod down -v" >/dev/null
assert_contains "$DOCKER_LOG" "compose -f docker-compose.prod.yml --env-file env/.env.prod down"
assert_contains "$DOCKER_LOG" "compose -f docker-compose.prod.yml --env-file env/.env.prod down -v"

mv "$LOCAL_COMPOSE_ENV" "$TMP_ROOT/local-compose.env"
PATH="$FAKE_BIN:$PATH" bash -c "cd '$FIXTURE' && ./run.sh dev down" >/dev/null
assert_contains "$DOCKER_LOG" "compose -f docker-compose.yml --env-file env/.env.local down"
mv "$TMP_ROOT/local-compose.env" "$LOCAL_COMPOSE_ENV"

: > "$DOCKER_LOG"
PATH="$FAKE_BIN:$PATH" bash -c "cd '$FIXTURE' && ./run.sh dev -d" >/dev/null
assert_contains "$DOCKER_LOG" "compose -f docker-compose.yml --env-file env/.env.compose.local up --build -d db neo4j redis browser_service"

: > "$DOCKER_LOG"
PATH="$FAKE_BIN:$PATH" bash -c "cd '$FIXTURE' && ./run.sh dev --sandbox-manager -d" >/dev/null
assert_contains "$DOCKER_LOG" "build -f sandbox-python.Dockerfile -t meridian_sandbox_python:local .."
assert_contains "$DOCKER_LOG" "sandbox_manager"

: > "$DOCKER_LOG"
PATH="$FAKE_BIN:$PATH" bash -c "cd '$FIXTURE' && ./run.sh build --force-rebuild -d" >/dev/null
assert_contains "$DOCKER_LOG" "build -f sandbox-python.Dockerfile -t meridian_prod_sandbox_python:local --no-cache .."
assert_contains "$DOCKER_LOG" "compose -f docker-compose.yml --env-file env/.env.prod build --no-cache"
assert_contains "$DOCKER_LOG" "compose -f docker-compose.yml --env-file env/.env.prod up -d"

: > "$DOCKER_LOG"
PATH="$FAKE_BIN:$PATH" bash -c "cd '$FIXTURE' && ./run.sh build -d" >/dev/null
assert_contains "$DOCKER_LOG" "build -f sandbox-python.Dockerfile -t meridian_prod_sandbox_python:local .."
assert_contains "$DOCKER_LOG" "compose -f docker-compose.yml --env-file env/.env.prod up --build -d"
assert_not_contains "$DOCKER_LOG" "--no-cache"

: > "$DOCKER_LOG"
PATH="$FAKE_BIN:$PATH" bash -c "cd '$FIXTURE' && ./run.sh prod v1.2.3 -d" >/dev/null
assert_contains "$DOCKER_LOG" "compose -f docker-compose.prod.yml --env-file env/.env.prod pull"
assert_contains "$DOCKER_LOG" "pull ghcr.io/mathisverstrepen/meridian/sandbox-python:1.2.3"
assert_contains "$DOCKER_LOG" "compose -f docker-compose.prod.yml --env-file env/.env.prod up -d"

docker compose -f "$FIXTURE/docker-compose.yml" --env-file "$LOCAL_COMPOSE_ENV" config --quiet
IMAGE_TAG=latest docker compose -f "$FIXTURE/docker-compose.prod.yml" --env-file "$PROD_ENV" config --quiet

printf 'Deployment configuration tests passed.\n'
