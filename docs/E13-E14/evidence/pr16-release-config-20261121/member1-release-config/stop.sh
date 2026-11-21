#!/usr/bin/env bash
set -euo pipefail
repo="$(cd "${1:?Usage: stop.sh SOURCE_REPO}" && pwd)"
config_dir="$(cd "$(dirname "$0")" && pwd)"
export E14_ROOT="$repo" E14_IMAGE=sha256:1fa773b9ed7fdf35281eda86ec53ebf61048f271a70a43f9ccfd0e2d7a759829
pidfile="$repo/work/member1-release-control/api.pid"
if [ -f "$pidfile" ]; then
 pid="$(cat "$pidfile")"
 case "$pid" in ''|*[!0-9]*) echo 'Invalid saved PID'; exit 1;; esac
 if kill -0 "$pid" 2>/dev/null; then
  [ "$(readlink "/proc/$pid/cwd")" = "$repo" ] || { echo "PID working directory differs"; exit 1; }
  command_text="$(ps -p "$pid" -o args=)"
  case "$command_text" in *labs/e13e14/jobs_api.py*--root*work/member1-release-api*) kill "$pid";; *) echo 'PID identity differs; refusing to stop it'; exit 1;; esac
 fi
fi
docker compose -p b08-e14-member1-release -f "$config_dir/compose.yaml" down
