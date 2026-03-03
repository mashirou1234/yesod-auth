#!/usr/bin/env sh
set -eu

log() {
  printf '%s\n' "[woodpecker-pr-automerge] $*"
}

if [ -z "${GH_TOKEN:-}" ] && [ -n "${GITHUB_TOKEN:-}" ]; then
  export GH_TOKEN="${GITHUB_TOKEN}"
fi

if [ -z "${GH_TOKEN:-}" ]; then
  log "GH_TOKEN/GITHUB_TOKEN が未設定のためスキップします。"
  exit 0
fi

repo="${CI_REPO:-}"
if [ -z "${repo}" ] && [ -n "${CI_REPO_OWNER:-}" ] && [ -n "${CI_REPO_NAME:-}" ]; then
  repo="${CI_REPO_OWNER}/${CI_REPO_NAME}"
fi

if [ -z "${repo}" ]; then
  log "CI_REPO を取得できないためスキップします。"
  exit 0
fi

pr_raw="${CI_COMMIT_PULL_REQUEST:-}"
case "${pr_raw}" in
  ""|false|0)
    log "CI_COMMIT_PULL_REQUEST が未設定のためスキップします。"
    exit 0
    ;;
esac

pr_number="$(printf '%s' "${pr_raw}" | sed -E 's#.*/##; s/[^0-9]//g')"
if [ -z "${pr_number}" ]; then
  log "PR番号を解釈できないためスキップします: ${pr_raw}"
  exit 0
fi

pr_api="repos/${repo}/pulls/${pr_number}"

if ! gh api "${pr_api}" >/dev/null 2>&1; then
  log "GitHub API からPR情報を取得できないためスキップします。"
  exit 0
fi

base_ref="$(gh api "${pr_api}" --jq '.base.ref' 2>/dev/null || true)"
draft="$(gh api "${pr_api}" --jq '.draft' 2>/dev/null || true)"
head_repo="$(gh api "${pr_api}" --jq '.head.repo.full_name' 2>/dev/null || true)"
author_assoc="$(gh api "${pr_api}" --jq '.author_association' 2>/dev/null || true)"
node_id="$(gh api "${pr_api}" --jq '.node_id' 2>/dev/null || true)"
automerge_off="$(gh api "repos/${repo}/issues/${pr_number}/labels" --jq 'map(.name=="automerge:off") | any' 2>/dev/null || printf 'false')"

if [ "${draft}" = "true" ]; then
  log "Draft PR のためスキップします。"
  exit 0
fi

if [ "${base_ref}" != "main" ] && [ "${base_ref}" != "master" ]; then
  log "base=${base_ref} は対象外のためスキップします。"
  exit 0
fi

if [ "${head_repo}" != "${repo}" ]; then
  log "fork 由来PRのためスキップします。"
  exit 0
fi

case "${author_assoc}" in
  OWNER|MEMBER|COLLABORATOR) ;;
  *)
    log "author_association=${author_assoc} は対象外のためスキップします。"
    exit 0
    ;;
esac

if [ "${automerge_off}" = "true" ]; then
  log "automerge:off ラベルがあるためスキップします。"
  exit 0
fi

set +e
approve_out="$(gh api --method POST "repos/${repo}/pulls/${pr_number}/reviews" \
  -f event=APPROVE \
  -f body='Automated approval by Woodpecker.' 2>&1)"
approve_rc=$?
set -e

if [ "${approve_rc}" -ne 0 ]; then
  if printf '%s' "${approve_out}" | grep -Eiq 'unprocessable|already|review cannot'; then
    log "Approve は既に実施済み、または不要です。"
  else
    log "Approve に失敗しましたが処理は継続します。"
    log "${approve_out}"
  fi
else
  log "PR #${pr_number} を自動承認しました。"
fi

if [ -z "${node_id}" ]; then
  log "node_id を取得できないため auto-merge はスキップします。"
  exit 0
fi

query='mutation($pullRequestId:ID!){enablePullRequestAutoMerge(input:{pullRequestId:$pullRequestId,mergeMethod:SQUASH}){pullRequest{number}}}'

set +e
merge_out="$(gh api graphql -f query="${query}" -F pullRequestId="${node_id}" 2>&1)"
merge_rc=$?
set -e

if [ "${merge_rc}" -ne 0 ]; then
  if printf '%s' "${merge_out}" | grep -Eiq 'already enabled|auto merge is disabled|not in the correct state|enablePullRequestAutoMerge'; then
    log "auto-merge の有効化は不要、または設定未整備です。"
  else
    log "auto-merge の有効化に失敗しましたが処理は継続します。"
    log "${merge_out}"
  fi
else
  log "PR #${pr_number} の auto-merge(squash) を有効化しました。"
fi

exit 0
