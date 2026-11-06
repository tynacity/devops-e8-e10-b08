#!/usr/bin/env bash
# Source from the student's course repository. Uses the existing lab environment.
lab_ready() {
  LAB_REPO_ROOT=$(git rev-parse --show-toplevel) || return 1
  if [[ "$PWD" != "$LAB_REPO_ROOT" || ! -f labs/e8e10/lab.py ]]; then
    echo '请进入包含run_lab.py和labs/e8e10/lab.py的个人仓库根目录。' >&2
    return 1
  fi
  SID=$(git config --local user.name) || return 1
  [[ "$SID" =~ ^[0-9]{6,16}$ ]] || { echo '本仓库git user.name须为本人数字学号。' >&2; return 1; }
  LAB_IMAGE="course-e8e10:$SID"
  docker image inspect "$LAB_IMAGE" >/dev/null || { echo '先执行 python3 run_lab.py build。' >&2; return 1; }
  export LAB_REPO_ROOT LAB_IMAGE SID
  printf '仓库=%s\n学号=%s\n镜像=%s\n' "$LAB_REPO_ROOT" "$SID" "$LAB_IMAGE"
}
lab_new_run() {
  [[ "$1" =~ ^e(8|9|10)$ && "$2" =~ ^[AB]$ ]] || { echo '用法：lab_new_run e8 A'; return 1; }
  [[ "$PWD" == "$LAB_REPO_ROOT" ]] || { echo '请回到个人仓库根目录。'; return 1; }
  mkdir -p work
  OUT=$(mktemp -d "work/$1-$2-manual.XXXXXX") || return 1
  LAB_STEP_SEQ=0
  printf '%s\n' "$OUT" > "work/last-$1-$2.path"
  git rev-parse HEAD > "$OUT/student-source-commit.txt" || return 1
  docker image inspect "$LAB_IMAGE" --format '{{.Id}}' > "$OUT/environment-image-id.txt" || return 1
  export OUT
  printf '本次证据目录=%s\n' "$OUT"
}
lab_python() {
  [[ "$PWD" == "$LAB_REPO_ROOT" && "$OUT" == work/* && -d "$OUT" ]] || { echo '先在仓库根目录执行lab_ready和lab_new_run。'; return 1; }
  LAB_STEP_SEQ=$(( ${LAB_STEP_SEQ:-0} + 1 ))
  mkdir -p "$OUT/steps"
  local log="$OUT/steps/$(date +%Y%m%d-%H%M%S)-$LAB_STEP_SEQ.log"
  docker run --rm -i --network none --cap-add SYS_PTRACE \
    --user "$(id -u):$(id -g)" -e HOME=/tmp \
    -e PYTHONPATH=/course/labs/e8e10:/app \
    -v "$LAB_REPO_ROOT:/course" -w /course "$LAB_IMAGE" \
    python3 - "$@" 2>&1 | tee "$log"
  local result=${PIPESTATUS[0]}
  printf 'STEP_EXIT_CODE=%s\n' "$result" | tee -a "$log"
  return "$result"
}
