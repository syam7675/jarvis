#!/usr/bin/env bash
# Prepare a tested upstream-update PR; never push or modify main here.
set -euo pipefail

mode=${1:---check}
if [[ "$mode" != --check && "$mode" != --prepare ]]; then
  echo 'Usage: bash personal/update.sh [--check|--prepare]' >&2
  exit 2
fi
root=$(git rev-parse --show-toplevel)
cd "$root"
if [[ -n $(git status --porcelain) ]]; then
  echo 'Refusing to update a checkout with local changes.' >&2
  exit 1
fi
original_branch=$(git symbolic-ref --quiet --short HEAD) || {
  echo 'Check out a named branch before updating.' >&2
  exit 1
}
original_head=$(git rev-parse HEAD)
upstream=${JARVIS_UPSTREAM_REMOTE:-https://github.com/open-jarvis/OpenJarvis.git}
branch=${JARVIS_UPDATE_BRANCH:-automation/upstream}
git check-ref-format --branch "$branch" >/dev/null
if [[ "$branch" == "$original_branch" ]]; then
  echo 'The update branch must differ from the current branch.' >&2
  exit 1
fi
git fetch --no-tags "$upstream" main
upstream_head=$(git rev-parse --verify 'FETCH_HEAD^{commit}')
if git merge-base --is-ancestor "$upstream_head" HEAD; then
  echo 'Already up to date with upstream main.'
  exit 0
fi
if ! git merge-base HEAD "$upstream_head" >/dev/null; then
  echo 'Upstream history is unrelated or shallow; fetch full history first.' >&2
  exit 1
fi
if [[ "$mode" == --check ]]; then
  echo "Upstream update available: $upstream_head"
  exit 0
fi
if git show-ref --verify --quiet "refs/heads/$branch"; then
  echo "Refusing to overwrite existing local branch: $branch" >&2
  exit 1
fi
for file in jarvis-ci.yml jarvis-update.yml; do
  git cat-file -e "$original_head:.github/workflows/$file" || {
    echo "Missing protected workflow: $file" >&2
    exit 1
  }
done

created=false
rollback() {
  result=$?
  if [[ "$result" != 0 && "$created" == true ]]; then
    git merge --abort >/dev/null 2>&1 || true
    # This branch was created by this script from a verified clean checkout.
    git reset --hard "$original_head" >/dev/null
    git switch "$original_branch" >/dev/null
    git branch -D "$branch" >/dev/null
    echo 'Update failed; restored the original clean branch.' >&2
  fi
  exit "$result"
}
trap rollback EXIT
git switch -c "$branch"
created=true
merge_status=0
git merge --no-ff --no-commit "$upstream_head" || merge_status=$?
if [[ "$merge_status" != 0 ]]; then
  if ! git rev-parse --verify MERGE_HEAD >/dev/null 2>&1; then
    echo 'Upstream merge failed before creating merge state.' >&2
    exit 1
  fi
  # Upstream commonly modifies publisher workflows deleted by this fork.
  # Resolve only that explicitly excluded directory; source conflicts still
  # require human review and trigger a complete rollback below.
  mapfile -d '' -t conflicts < <(git diff --name-only --diff-filter=U -z)
  for conflict in "${conflicts[@]}"; do
    case "$conflict" in
      .github/workflows/*)
        git rm --force -- "$conflict"
        ;;
      *)
        echo 'Upstream merge conflicts require review; no update was applied.' >&2
        exit 1
        ;;
    esac
  done
fi
# Upstream release/publishing workflows do not belong to this personal fork.
# Retain exactly our own reviewed CI and updater from the pre-merge commit.
mkdir -p .github/workflows
find .github/workflows -type f ! -name jarvis-ci.yml ! -name jarvis-update.yml -delete
git restore --source="$original_head" --staged --worktree -- \
  .github/workflows/jarvis-ci.yml .github/workflows/jarvis-update.yml
git add -A .github/workflows
git commit -m "chore: merge OpenJarvis upstream ${upstream_head:0:12}"
echo "Prepared $branch at $(git rev-parse HEAD); test before opening a PR."
