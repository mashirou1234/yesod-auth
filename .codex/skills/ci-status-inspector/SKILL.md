---
name: ci-status-inspector
description: 失敗した PR check や commit pipeline の CI provider を特定し、GitHub Actions / Woodpecker / GitLab CI のどれが失敗しているかを正確に切り分ける。外部 status URL、pipeline URL、commit SHA から exact target を調べたいときに使う。
---

# ci-status-inspector

`$ci-status-inspector` は、失敗した check の provider を判定し、repo 全体の最新状況ではなく「その check が指している実体」を優先して調査する。

## provider 判定

repo 構成よりも、check 自体のメタデータを優先する。

1. まず failing target を確認する。
   - GitHub PR: `gh pr view <pr> --json statusCheckRollup,headRefOid,url`
   - commit status: `gh api repos/<owner>/<repo>/commits/<sha>/status`
2. 次に provider を分類する。
   - **GitHub Actions**: `detailsUrl` が `github.com/.../actions/runs/...`
   - **Woodpecker**: context が `ci/woodpecker/` で始まる、または URL が `/repos/<repo-id>/pipeline/<n>/...` に一致する
   - **GitLab CI**: URL が GitLab pipelines/jobs を指す、またはタスクが明示的に GitLab CI を対象としている
3. repo ファイルは fallback signal としてだけ使う。
   - `.woodpecker.yml`
   - `.github/workflows/`
   - `.gitlab-ci.yml`
4. 複数 provider が混在する場合は、failing check の `detailsUrl` を最優先する。まだ曖昧なら、曖昧さと根拠を明示して止める。

## exact target の優先順位

次の順で selector を選ぶ。

1. pipeline URL
2. pipeline ID / number
3. commit SHA
4. latest pipeline

障害調査で `latest` に頼るのは、他に selector がない場合だけにする。

## GitHub Actions の流れ

失敗 check が GitHub Actions なら、この流れを使う。

- GitHub PR check の失敗調査が主目的なら、`$gh-fix-ci` が使える場合はそちらを優先する
- それ以外は `gh pr checks <pr>` と `gh run view <run-id> --log` を使う
- failing job 名、failing step、最小の再現ヒントだけを要約する
- 外部 check を GitHub 上に見えているという理由だけで GitHub Actions 扱いしない

## Woodpecker の流れ

失敗 check が Woodpecker を指している場合は、bundled script を使う。

前提:
- `WOODPECKER_TOKEN`
- 任意: `WOODPECKER_HOST`（既定 `https://mashirou.stream`）

bundled script:
- `scripts/get-woodpecker-pipeline-status.sh`

推奨コマンド:

```bash
# 最優先: GitHub status の target_url をそのまま渡す
scripts/get-woodpecker-pipeline-status.sh --pipeline-url <target_url>

# repo id / pipeline number が分かっている場合
scripts/get-woodpecker-pipeline-status.sh --repo-id <repo_id> --pipeline-id <pipeline_number>

# commit しか分からない場合
scripts/get-woodpecker-pipeline-status.sh --repo <owner/repo> --commit <sha>
```

解釈ルール:
- `workflow_failures` を最優先で読み、具体的な failed workflow / plugin / command step を特定する
- `errors` は config validation や lint 段階の reject を示すことが多い
- `--strict` は selected pipeline が `success` でない限り exit code `3` を返すので、自動ガードに使える
- PR 調査では、同じ commit に複数 pipeline がある場合 `push` より `pull_request` を優先する

## GitLab CI の流れ

失敗 URL またはタスクが明確に GitLab CI を指している場合は、この流れを使う。

- 既存の GitLab 向けツール（`glab` や内部 script）があればそれを優先する
- API が使えるなら、latest pipeline ではなく exact pipeline/job URL を直接見る
- token や tooling が無ければ推測せず、足りない前提を明示して止める

この skill は現在 Woodpecker helper script を同梱している。GitLab については workflow guidance を定義し、bundled implementation はまだ持たない。

## 出力形式

返答は provider を意識した短い要約に揃える。

- Provider
- 使った exact target（`pipeline-url` / `pipeline-id` / `commit` / `latest`）
- Pipeline status
- Failing workflow / job / plugin / step
- Key error text
- 今回の diff 起因か、既存 CI / infrastructure 起因かの見立て

## resources

### scripts/get-woodpecker-pipeline-status.sh

Woodpecker API を exact selector で問い合わせる helper script。

次の場面で使う。
- GitHub status が Woodpecker URL を返している
- Woodpecker の PR pipeline を正確に調べたい
- latest pipeline に依存せず commit から exact pipeline を引きたい
