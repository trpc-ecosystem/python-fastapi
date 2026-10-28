#!/usr/bin/env bash
#
# Tencent is pleased to support the open source community by making tRPC-FastAPI-Python available.
#
# Copyright (C) 2026 Tencent.  All rights reserved.
#
# tRPC-FastAPI-Python is licensed under the Apache-2.0.
#
# Start the example server, hit the HTTP / RPC / SSE / WebSocket checks, then stop it.
#
# Usage:
#   ./run_examples.sh                  # same as "http" with trpc_python.yaml
#   ./run_examples.sh http [conf]      # start trpc_main.py, run checks, stop the server
#   ./run_examples.sh all              # http against each of the four configs
#   ./run_examples.sh list             # list example names and config files
#
# A conf path is a file name under this directory, or an absolute path.
# FastAPI listens on 8000 and the native tRPC service on 8001.
#
# Environment:
#   PYTHON   interpreter to use (default: ../venv/bin/python, then python3)
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
# Package root first. A sibling checkout of the SDK (../trpc_sdk) is inserted
# ahead of site-packages so this example uses that source.
PYTHONPATH="${PKG_DIR}${PYTHONPATH:+:${PYTHONPATH}}"
SDK_PARENT="$(cd "${PKG_DIR}/.." && pwd)"
if [[ -f "${SDK_PARENT}/trpc_sdk/http/__init__.py" ]]; then
  PYTHONPATH="${SDK_PARENT}:${PYTHONPATH}"
fi
export PYTHONPATH

if [[ -n "${PYTHON:-}" ]]; then
  PY="${PYTHON}"
elif [[ -x "${PKG_DIR}/venv/bin/python" ]]; then
  PY="${PKG_DIR}/venv/bin/python"
else
  PY="$(command -v python3)"
fi

SERVER_LOG="${SCRIPT_DIR}/.server_run.log"
SERVER_PID=""
HOST="127.0.0.1"
HTTP_PORT=8000
TRPC_PORT=8001
BASE="http://${HOST}:${HTTP_PORT}"

CONFIGS=(
  trpc_python.yaml
  trpc_python_merge_threads.yaml
  trpc_python_separate_thread.yaml
  trpc_python_separate.yaml
)

log() { printf '\n\033[1;34m==> %s\033[0m\n' "$*" >&2; }
ok()  { printf '\033[1;32m[PASS]\033[0m %s\n' "$*" >&2; }
bad() { printf '\033[1;31m[FAIL]\033[0m %s\n' "$*" >&2; }

port_open() {
  local port="$1"
  "${PY}" -c "import socket; s=socket.create_connection(('${HOST}', ${port}), 0.2); s.close()" >/dev/null 2>&1
}

wait_ready() {
  local tries=60
  while (( tries-- > 0 )); do
    port_open "${HTTP_PORT}" && return 0
    if [[ -n "${SERVER_PID}" ]] && ! kill -0 "${SERVER_PID}" 2>/dev/null; then
      return 1
    fi
    sleep 0.5
  done
  return 1
}

wait_ports_free() {
  local tries=20
  while (( tries-- > 0 )); do
    if ! port_open "${HTTP_PORT}" && ! port_open "${TRPC_PORT}"; then
      return 0
    fi
    sleep 0.5
  done
  return 1
}

resolve_conf() {
  local conf="${1:-${SCRIPT_DIR}/trpc_python.yaml}"
  if [[ "${conf}" != /* ]]; then
    if [[ -f "${SCRIPT_DIR}/${conf}" ]]; then
      conf="${SCRIPT_DIR}/${conf}"
    fi
  fi
  if [[ ! -f "${conf}" ]]; then
    bad "config not found: ${conf}"
    return 1
  fi
  printf '%s\n' "${conf}"
}

start_server() {
  local conf="$1"
  if port_open "${HTTP_PORT}" || port_open "${TRPC_PORT}"; then
    bad "port ${HTTP_PORT} or ${TRPC_PORT} is already in use; stop that process first"
    return 1
  fi
  log "starting server: ${conf}"
  : > "${SERVER_LOG}"
  # `exec` makes the subshell become the python process, so $! is its pid.
  ( cd "${SCRIPT_DIR}" && exec "${PY}" trpc_main.py --conf "${conf}" ) >>"${SERVER_LOG}" 2>&1 &
  SERVER_PID=$!
  if ! wait_ready; then
    bad "server did not start listening on ${HTTP_PORT}; last log lines:"
    tail -n 40 "${SERVER_LOG}" || true
    stop_server
    return 1
  fi
}

stop_server() {
  # EXIT also calls this when no server was started (for example `list`).
  [[ -z "${SERVER_PID}" ]] && return 0
  pkill -TERM -P "${SERVER_PID}" 2>/dev/null || true
  kill -TERM "${SERVER_PID}" 2>/dev/null || true
  local _
  for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
    kill -0 "${SERVER_PID}" 2>/dev/null || break
    sleep 0.5
  done
  pkill -KILL -P "${SERVER_PID}" 2>/dev/null || true
  kill -KILL "${SERVER_PID}" 2>/dev/null || true
  wait "${SERVER_PID}" 2>/dev/null || true
  SERVER_PID=""
  if ! wait_ports_free; then
    bad "ports ${HTTP_PORT}/${TRPC_PORT} still in use after stopping the server"
    return 1
  fi
}

check_get() {
  local path="$1"
  local needle="$2"
  local body rc=0
  body="$(curl -fsS --max-time 10 "${BASE}${path}")" || rc=$?
  if [[ ${rc} -ne 0 ]]; then
    bad "GET ${path} (curl ${rc})"
    return 1
  fi
  if [[ "${body}" != *"${needle}"* ]]; then
    bad "GET ${path} missing '${needle}'"
    printf '%s\n' "${body}" >&2
    return 1
  fi
  ok "GET ${path}"
}

check_status() {
  local path="$1"
  local code rc=0
  code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 10 "${BASE}${path}")" || rc=$?
  if [[ ${rc} -ne 0 ]]; then
    bad "GET ${path} (curl ${rc})"
    return 1
  fi
  if [[ "${code}" != "200" ]]; then
    bad "GET ${path} status ${code}"
    return 1
  fi
  ok "GET ${path}"
}

check_sayhello() {
  local body rc=0
  body="$(curl -fsS --max-time 10 -X POST \
    "${BASE}/trpc.trpc_python_group.helloworld.Greeter/SayHello" \
    -H 'Content-Type: application/json' \
    -d '{"msg":"data"}')" || rc=$?
  if [[ ${rc} -ne 0 ]]; then
    bad "POST SayHello (curl ${rc})"
    return 1
  fi
  if [[ "${body}" != *"hello:"* ]]; then
    bad "POST SayHello missing 'hello:'"
    printf '%s\n' "${body}" >&2
    return 1
  fi
  ok "POST SayHello"
}

check_download() {
  local headers rc=0 lower
  headers="$(curl -fsS -D - -o /dev/null --max-time 10 "${BASE}/download_file")" || rc=$?
  if [[ ${rc} -ne 0 ]]; then
    bad "GET /download_file (curl ${rc})"
    return 1
  fi
  lower="$(printf '%s' "${headers}" | tr '[:upper:]' '[:lower:]')"
  if [[ "${lower}" != *"content-disposition:"* ]]; then
    bad "GET /download_file missing content-disposition"
    printf '%s\n' "${headers}" >&2
    return 1
  fi
  ok "GET /download_file"
}

check_sse() {
  local out rc=0
  # The handler streams until the client stops. curl exits 28 when --max-time fires.
  out="$(curl -sS -N --max-time 3 "${BASE}/sse" 2>&1)" || rc=$?
  if [[ ${rc} -ne 0 && ${rc} -ne 28 ]]; then
    bad "GET /sse (curl ${rc})"
    printf '%s\n' "${out}" >&2
    return 1
  fi
  if [[ "${out}" != *"data:"* ]]; then
    bad "GET /sse missing event data"
    printf '%s\n' "${out}" >&2
    return 1
  fi
  ok "GET /sse"
}

run_python_client() {
  local label="$1"
  local script="$2"
  local rc=0
  log "running ${label}"
  ( cd "${SCRIPT_DIR}" && "${PY}" "${script}" ) || rc=$?
  if [[ ${rc} -eq 0 ]]; then
    ok "${label}"
  else
    bad "${label} (exit ${rc})"
  fi
  return ${rc}
}

run_checks() {
  local rc=0
  check_get /health healthy || rc=1
  check_get /fastapi_http "This fastapi_http" || rc=1
  check_get /fastapi_users "John Doe" || rc=1
  check_get /trpc_http "This normal_http" || rc=1
  check_sayhello || rc=1
  check_status / || rc=1
  check_status /static/html/page1.html || rc=1
  check_status /static/css/style.css || rc=1
  check_download || rc=1
  check_sse || rc=1
  run_python_client "websocket" "client/test_websocket_client.py" || rc=1
  run_python_client "rpc" "client/test_service_rpc.py" || rc=1
  return ${rc}
}

run_http() {
  local conf
  conf="$(resolve_conf "${1:-}")" || return 1
  start_server "${conf}" || return 1
  log "running checks against ${BASE}"
  local rc=0
  run_checks || rc=$?
  stop_server || rc=1
  if [[ ${rc} -eq 0 ]]; then
    ok "http $(basename "${conf}")"
  else
    bad "http $(basename "${conf}") (see ${SERVER_LOG})"
  fi
  return ${rc}
}

run_all() {
  local rc=0 conf
  for conf in "${CONFIGS[@]}"; do
    run_http "${conf}" || rc=1
  done
  return ${rc}
}

trap 'stop_server' EXIT INT TERM

main() {
  case "${1:-http}" in
    list)
      echo "Available examples: http all"
      echo "Configs:"
      printf '  %s\n' "${CONFIGS[@]}"
      ;;
    http)
      run_http "${2:-}"
      ;;
    all)
      run_all
      ;;
    *)
      bad "unknown example: $1 (try: ./run_examples.sh list)"
      return 2
      ;;
  esac
}

main "$@"
