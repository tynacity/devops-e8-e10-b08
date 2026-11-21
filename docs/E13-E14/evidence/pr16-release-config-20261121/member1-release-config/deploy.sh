#!/usr/bin/env bash
set -euo pipefail
repo="$(cd "${1:?Usage: deploy.sh SOURCE_REPO}" && pwd)"
config_dir="$(cd "$(dirname "$0")" && pwd)"
expected=7b7e67b6c005bdf27ca7645790d75623230c00fe
image=sha256:1fa773b9ed7fdf35281eda86ec53ebf61048f271a70a43f9ccfd0e2d7a759829
project=b08-e14-member1-release
[ "$(git -C "$repo" rev-parse HEAD)" = "$expected" ]
[ -z "$(git -C "$repo" status --porcelain --untracked-files=no)" ]
[ "$(docker image inspect --format '{{.Os}}/{{.Architecture}}' "$image")" = linux/amd64 ]
[ -z "$(docker ps -aq --filter label=com.docker.compose.project="$project")" ]
python3 - <<'CHECK'
import socket,sys
assert sys.version_info >= (3,10)
sockets=[]
for port in (18181,18182,18183,18184,18594):
 s=socket.socket();s.bind(('127.0.0.1',port));sockets.append(s)
CHECK
export E14_ROOT="$repo" E14_IMAGE="$image"
mkdir -p "$repo/work/member1-release-control"
control="$repo/work/member1-release-control"
docker compose -p "$project" -f "$config_dir/compose.yaml" config > "$control/compose-resolved.yaml"
docker compose -p "$project" -f "$config_dir/compose.yaml" up -d --wait
cd "$repo"
nohup python3 -u labs/e13e14/jobs_api.py --port 18594 --root work/member1-release-api > "$control/api.log" 2>&1 &
printf '%s\n' "$!" > "$control/api.pid"
python3 - <<'HEALTH'
import time,json,urllib.request
for attempt in range(30):
 try:
  with urllib.request.urlopen('http://127.0.0.1:18594/health',timeout=2) as r:
   data=json.load(r);assert data['service_id']=='course-e14-four-role';break
 except Exception:
  if attempt==29:raise
  time.sleep(1)
HEALTH
printf '%s\n' 'Started only b08-e14-member1-release; record real image IDs and run fresh task/download checks.'
