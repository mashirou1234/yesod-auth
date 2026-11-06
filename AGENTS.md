# Codex Project Agent Notes (GitHub)

- 日本語で簡潔に報告する
- まず `artifacts/` を確認して前回結果を把握する
- クラウド開発のセットアップ・検証は `docs/guides/codex-cloud-development.md` を参照し、`bash scripts/cloud-setup.sh` / `bash scripts/cloud-test.sh` を使う。本番シークレット不要。実OAuthログインとSQLite・モックテストの検証範囲を区別する。
- テスト・lint・PR自動承認・マージはWoodpecker（`.woodpecker.yml`）に統一する。GitHub Actionsのワークフローは追加しない。PR自動化は保護されたmain/masterのcronのみで実行し、bot用secretはWoodpecker管理側でcronイベントだけに制限する。設定は `docs/guides/woodpecker-pr-automation.md` を参照。
- 自動レーンは `<ORCH_RUN_COMMAND>` を使い、必ず 1 run 1 issue を守る
- 自動レーンの commit/push は原則許可。Issue 指示やプロンプトで明示禁止がある場合のみ停止する
- 手動レーン（Power User の直接対応）は一括処理可。ただし `codex:queue` 系ラベル遷移の整合は維持する
- 手動レーンの push はローカル確認後に 1 回を標準とする
- issue 選定は `codex:blocked` を最優先し、次に `codex:priority` + `codex:queue`、最後に通常の `codex:queue` を処理する
- queue 着手前に linked Project の status / priority を確認する。Project 未連携 repo は `N/A` を記録する
- Issue 状態遷移は `queue -> claimed -> (blocked | pr-opened) -> merge確認 -> close` を標準とする
- 失敗時は issue コメントと `codex:blocked` を付与する
- `codex:pr-opened` の Issue は merge 確認後の reconcile で close する（自動レーン主体）
- docs-only CI 分岐の対象は `docs/**`, `README.md`, `AGENTS.md` に固定し、対象外または判定不能な変更があれば通常 CI を実行する
