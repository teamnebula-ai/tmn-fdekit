#!/usr/bin/env bash
# otel_env.sh — print the environment that sends Claude Code's own telemetry to a backend.
#
#   otel_env.sh langfuse  [BASE_URL]    traces -> Langfuse (OTLP/HTTP). Default https://cloud.langfuse.com
#   otel_env.sh collector [ENDPOINT]    everything -> an OpenTelemetry Collector. Default http://127.0.0.1:4317
#   otel_env.sh phoenix   [BASE_URL]    traces -> Arize Phoenix. Default http://127.0.0.1:6006
#   otel_env.sh off                     unset it all
#
# Prints shell lines to put in your shell profile or a direnv .envrc. It never prints a
# secret: Langfuse auth is computed at shell start from LANGFUSE_PUBLIC_KEY and
# LANGFUSE_SECRET_KEY, which you keep in your secret manager, not in this output.
#
# Privacy defaults: tool names, commands and file paths are sent (that is the audit
# trail); prompt text, response text and file contents are not. Change the LOG_* lines
# only on purpose.
set -euo pipefail
common='export CLAUDE_CODE_ENABLE_TELEMETRY=1
export CLAUDE_CODE_ENHANCED_TELEMETRY_BETA=1          # spans (beta): interaction -> llm_request / tool
export OTEL_LOG_TOOL_DETAILS=1                        # commands + file paths: the audit trail
export OTEL_LOG_USER_PROMPTS=0                        # prompt text stays local
export OTEL_LOG_TOOL_CONTENT=0                        # file contents and command output stay local
export OTEL_RESOURCE_ATTRIBUTES="service.namespace=agents,repo=$(basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")"'

case "${1:-}" in
  langfuse)
    base="${2:-https://cloud.langfuse.com}"
    cat <<EOF
# --- tmn-fdekit: Claude Code traces -> Langfuse ($base) ---
$common
export OTEL_TRACES_EXPORTER=otlp
export OTEL_METRICS_EXPORTER=none                     # Langfuse ingests traces only
export OTEL_LOGS_EXPORTER=none
export OTEL_EXPORTER_OTLP_TRACES_PROTOCOL=http/protobuf
export OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=$base/api/public/otel/v1/traces
: "\${LANGFUSE_PUBLIC_KEY:?set it from your secret manager}" "\${LANGFUSE_SECRET_KEY:?set it from your secret manager}"
export OTEL_EXPORTER_OTLP_TRACES_HEADERS="Authorization=Basic \$(printf '%s:%s' "\$LANGFUSE_PUBLIC_KEY" "\$LANGFUSE_SECRET_KEY" | base64 | tr -d '\n'),x-langfuse-ingestion-version=4"
EOF
    ;;
  collector)
    ep="${2:-http://127.0.0.1:4317}"
    cat <<EOF
# --- tmn-fdekit: Claude Code metrics, events and traces -> OTel Collector ($ep) ---
$common
export OTEL_METRICS_EXPORTER=otlp
export OTEL_LOGS_EXPORTER=otlp
export OTEL_TRACES_EXPORTER=otlp
export OTEL_EXPORTER_OTLP_PROTOCOL=grpc
export OTEL_EXPORTER_OTLP_ENDPOINT=$ep
EOF
    ;;
  phoenix)
    base="${2:-http://127.0.0.1:6006}"
    cat <<EOF
# --- tmn-fdekit: Claude Code traces -> Phoenix ($base) ---
$common
export OTEL_TRACES_EXPORTER=otlp
export OTEL_METRICS_EXPORTER=none
export OTEL_LOGS_EXPORTER=none
export OTEL_EXPORTER_OTLP_TRACES_PROTOCOL=http/protobuf
export OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=$base/v1/traces
EOF
    ;;
  off)
    echo 'unset CLAUDE_CODE_ENABLE_TELEMETRY CLAUDE_CODE_ENHANCED_TELEMETRY_BETA OTEL_TRACES_EXPORTER OTEL_METRICS_EXPORTER OTEL_LOGS_EXPORTER OTEL_EXPORTER_OTLP_ENDPOINT OTEL_EXPORTER_OTLP_PROTOCOL OTEL_EXPORTER_OTLP_TRACES_ENDPOINT OTEL_EXPORTER_OTLP_TRACES_PROTOCOL OTEL_EXPORTER_OTLP_TRACES_HEADERS OTEL_LOG_TOOL_DETAILS OTEL_LOG_USER_PROMPTS OTEL_LOG_TOOL_CONTENT OTEL_RESOURCE_ATTRIBUTES'
    ;;
  *) sed -n '2,14p' "$0"; exit 2 ;;
esac
