#!/usr/bin/env bash
set -eo pipefail
umask 077
REPO=/root/devops-students/241880546/draft
PERSONAL_ROOT=/root/devops-students/241880546
BASE=fb968b7e0d2b406905003d3956b3e177bea8e416
EXPECTED_IMAGE=sha256:c4a2b06bf18f03980a0535adb13b947de32bee713b8b3e9349e4f9746fb77776
RUNNER_DIR="$(cd "$(dirname "$0")" && pwd -P)"
ARCHIVE_OUTPUT="${1:-}"
META=
E8_OUT=
E9_OUT=
PHASE=preflight
stop() { printf 'STOP: %s\n' "$*" >&2; exit 1; }

[ "$(readlink -m "$PERSONAL_ROOT")" = "$PERSONAL_ROOT" ] || stop 'Personal directory resolves elsewhere.'
[ "$(readlink -m "$REPO")" = "$REPO" ] || stop 'Repository resolves elsewhere.'
[ -d "$REPO/.git" ] && [ ! -L "$REPO/.git" ] || stop 'Expected a standalone personal checkout.'
case "$ARCHIVE_OUTPUT" in
  /root/devops-students/241880546/evidence/e8-e9-supplement-*.tar.gz) ;;
  *) stop 'Unexpected evidence archive path.' ;;
esac
[ "$(readlink -m "$ARCHIVE_OUTPUT")" = "$ARCHIVE_OUTPUT" ] || stop 'Evidence path resolves elsewhere.'
for path in "$ARCHIVE_OUTPUT" "$ARCHIVE_OUTPUT.sha256"; do
  [ ! -e "$path" ] && [ ! -L "$path" ] || stop 'Evidence already exists. Use -DownloadOnly instead of repeating the experiment.'
done
cd "$REPO"
[ "$(git rev-parse --show-toplevel)" = "$REPO" ] || stop 'Wrong repository root.'
[ "$(git rev-parse HEAD)" = "$BASE" ] || stop 'Source HEAD changed. Preserve the checkout and report the new SHA.'
[ "$(git branch --show-current)" = student/241880546/e8-e10 ] || stop 'Wrong personal branch.'
[ "$(git config --local user.name)" = 241880546 ] || stop 'Wrong student identity.'
case "$(git remote get-url origin)" in
  https://github.com/tynacity/devops-e8-e10-b08|https://github.com/tynacity/devops-e8-e10-b08.git) ;;
  *) stop 'Unexpected origin.' ;;
esac
source "$RUNNER_DIR/course/classroom_helpers.sh"
lab_ready
[ "$(docker image inspect "$LAB_IMAGE" --format '{{.Id}}')" = "$EXPECTED_IMAGE" ] || stop 'Environment image changed; do not silently mix evidence.'
python3 "$RUNNER_DIR/protect_existing.py" check "$REPO"

META="$(mktemp -d work/e8-e9-supplement.XXXXXX)"
archive_evidence() {
  e89_exit=$?
  trap - EXIT
  set +e
  printf 'EXIT_CODE=%s\nPHASE=%s\nE8_OUT=%s\nE9_OUT=%s\n' "$e89_exit" "$PHASE" "$E8_OUT" "$E9_OUT" | tee "$META/run-status.txt"
  evidence_paths=("$META")
  [ -z "$E8_OUT" ] || evidence_paths+=("$E8_OUT")
  [ -z "$E9_OUT" ] || evidence_paths+=("$E9_OUT")
  mkdir -p "$PERSONAL_ROOT/evidence"
  if tar --exclude='.git' --exclude='__pycache__' --exclude='.pytest_cache' \
      --exclude='.env' --exclude='.env.*' --exclude='*.pem' --exclude='*.key' \
      -czf "$ARCHIVE_OUTPUT" -C "$REPO" "${evidence_paths[@]}"; then
    if sha256sum "$ARCHIVE_OUTPUT" | tee "$ARCHIVE_OUTPUT.sha256"; then
      printf 'EVIDENCE_ARCHIVE=%s\n' "$ARCHIVE_OUTPUT"
    else
      e89_exit=1
    fi
  else
    e89_exit=1
  fi
  exit "$e89_exit"
}
trap archive_evidence EXIT
cp "$RUNNER_DIR/e8_e9_steps.py" "$META/e8_e9_steps.py"
cp "$RUNNER_DIR/protect_existing.py" "$META/protect_existing.py"
cp "$RUNNER_DIR/run_supplement.sh" "$META/run_supplement.sh"
cp "$RUNNER_DIR/course/classroom_helpers.sh" "$META/classroom_helpers.sh"
git rev-parse HEAD > "$META/source-base-commit.txt"
git status --porcelain > "$META/source-status.txt"
git diff --binary --full-index --output="$META/worktree.patch" -- labs/e8e10/test_profile.py
sha256sum labs/e8e10/lab.py labs/e8e10/test_profile.py > "$META/source-files.sha256"
docker image inspect "$LAB_IMAGE" --format '{{.Id}}' > "$META/environment-image-id.txt"
for stage in e8 e9; do
  marker="work/last-$stage-B.path"
  if [ -f "$marker" ]; then cp "$marker" "$META/previous-last-$stage-B.path"; fi
done
PHASE=protect-before
python3 "$RUNNER_DIR/protect_existing.py" before "$REPO" "$META"

PHASE=e8
lab_new_run e8 B
E8_OUT="$OUT"
printf 'E8_OUT=%s\n' "$E8_OUT" | tee "$META/e8-out.txt"
for action in create inspect scan identity patch apply-check stale conclude; do
  printf 'E8_ACTION=%s\n' "$action"
  lab_python "$OUT" e8 "$action" < "$RUNNER_DIR/e8_e9_steps.py"
done

PHASE=e9
lab_new_run e9 B
E9_OUT="$OUT"
printf 'E9_OUT=%s\n' "$E9_OUT" | tee "$META/e9-out.txt"
for action in direct macro mixed compare apply-demo conclude; do
  printf 'E9_ACTION=%s\n' "$action"
  lab_python "$OUT" e9 "$action" < "$RUNNER_DIR/e8_e9_steps.py"
done

PHASE=protect-after
python3 "$RUNNER_DIR/protect_existing.py" after "$REPO" "$META" "$E8_OUT" "$E9_OUT"
PHASE=complete
printf 'E8_BASELINE_PASSED=true\nE9_BASELINE_PASSED=true\nE10_EVIDENCE_UNCHANGED=true\n'
printf 'SOURCE_SHA=%s\nE8_OUT=%s\nE9_OUT=%s\nSUMMARY=%s/%s/summary.json\n' "$BASE" "$E8_OUT" "$E9_OUT" "$REPO" "$META"
printf 'Only E8/E9 reference steps were run. Personal extensions and submission status are recorded separately.\n'
