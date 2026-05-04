# Codex Automation Ops テンプレート（他repo展開用）

このドキュメントは、codex-orch 運用を他リポジトリへ展開するときの共通テンプレートです。  
README / AGENTS / CI 設定を同時に揃える前提で利用してください。

## 1. プレースホルダ置換表

| Placeholder | 説明 | 例（yesod-auth） |
| --- | --- | --- |
| `<ORCH_RUN_COMMAND>` | 自動レーン実行コマンド | 実行環境ごとの orch 実コマンド |
| `<REPO_SLUG>` | `owner/repo` 形式 | `mashirou1234/yesod-auth` |
| `<BASE_BRANCH>` | 既定マージ先ブランチ | `main` |
| `<REQUIRED_CHECKS>` | branch protection 必須チェック | `ci/woodpecker/push/woodpecker`, `auto-approve`, `enable-auto-merge` など |
| `<LABEL_SET>` | codex 系ラベルセット | `codex`, `codex-automation`, `codex:priority`, `codex:queue`, `codex:claimed`, `codex:blocked`, `codex:pr-opened` |

## 2. 標準運用ルール（テンプレ文面）

### 2.1 レーン別 commit/push

- 自動レーン: commit/push は原則許可。Issue 指示やプロンプトで明示禁止がある場合のみ停止
- 手動レーン: ローカル確認後に 1 回 push を標準化
- issue 選定: `codex:blocked` を最優先し、次に `codex:priority` + `codex:queue`、最後に通常の `codex:queue` を処理
- queue 着手前: linked Project の status / priority を確認し、Project 未連携 repo は `N/A` を記録

### 2.2 Issue 状態遷移

標準遷移は以下で固定:

`queue -> claimed -> (blocked | pr-opened) -> merge確認 -> close`

- `blocked`: issue コメントと `codex:blocked` を付与
- `pr-opened`: merge 確認後に reconcile で close（自動レーン主体）

## 3. Run 記録導線

自動レーンの記録は、実行前の状態、処理した issue、PR/merge 結果、後続メモを 1 本の流れで残します。記録先が分散しても、同じ run を後から追えるように `run_id`、issue 番号、branch、PR URL を同じ値でそろえてください。

| 段階 | 記録する内容 | yesod-auth での確認コマンド |
| --- | --- | --- |
| preflight | 認証、remote、working tree、必須ラベル、Project 連携状態 | `git status --short --branch` / `gh issue list -R <REPO_SLUG> --label codex:queue --state open` |
| queue snapshot | 着手前の `codex:queue` 件数と候補 issue | `python3 scripts/queue_seed_snapshot.py --repo <REPO_SLUG> --format markdown` |
| run log | 対象 issue、実行コマンド、検証結果、失敗時の blocker | issue コメントまたは run artifact |
| PR reconcile | PR URL、merge commit、remote branch 削除、issue close | `gh pr view <pr> --json state,mergedAt,mergeCommit` |
| memory | 1 run 1 file の運用メモ。直接追記ではなく append helper を使う | 展開先の `append_memory.sh` / Codex 運用 helper |

`scripts/preflight_automation.sh` や `append_memory.sh` を配布している repo へ展開する場合は、上表の preflight と memory にそれぞれ接続します。yesod-auth では repo 内に同名 helper を置かないため、repo 内の再現確認は `scripts/queue_seed_snapshot.py` と `scripts/weekly_git_inventory.sh` を正本にします。

受け入れ時の同期チェック:

```bash
rg -n "Run 記録導線|queue_seed_snapshot|weekly_git_inventory|append_memory|preflight" docs/guides/codex-automation-ops.md README.md AGENTS.md
python3 scripts/queue_seed_snapshot.py --repo mashirou1234/yesod-auth --format markdown
bash scripts/weekly_git_inventory.sh
```

## 4. Woodpecker docs-only CI 分岐ルール

- 対象ファイル: `docs/**`, `README.md`, `AGENTS.md`
- 変更が対象のみ: 重い検証ステップをスキップ
- 対象外が 1 つでも含まれる: 通常 CI を実行
- 判定が不確実なとき: スキップせず通常 CI を実行（fail-open）

## 5. README / AGENTS 反映ポイント

### README に必ず書くこと

- レーン別 commit/push ルール
- Issue 状態遷移（6状態）
- docs-only CI 分岐の判定対象
- merge確認と close の責務（自動レーン主体）

### AGENTS に必ず書くこと

- `<ORCH_RUN_COMMAND>` の利用
- 1 run 1 issue
- `blocked` / `pr-opened` のラベル運用
- Project 未連携時の `N/A` 記録ルール

## 6. 適用チェックリスト

- [ ] `<ORCH_RUN_COMMAND>` を実在コマンドへ置換した
- [ ] `<REPO_SLUG>`, `<BASE_BRANCH>`, `<REQUIRED_CHECKS>`, `<LABEL_SET>` を置換した
- [ ] README と AGENTS の文言が矛盾していない
- [ ] CI 定義（Woodpecker）と README の docs-only 条件が一致している
- [ ] `queue -> claimed -> (blocked | pr-opened) -> merge確認 -> close` が運用文書で一致している
- [ ] `codex:priority` を含む issue 選定順が README / AGENTS / 実行プロンプトと矛盾していない
- [ ] run 記録が preflight / snapshot / run log / PR reconcile / memory の順で追跡できる
