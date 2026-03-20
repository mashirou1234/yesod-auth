# Codex Project Agent Notes (GitHub)

- 日本語で簡潔に報告する
- まず `artifacts/` を確認して前回結果を把握する
- `scripts/orch.sh` を使う自動レーンでは必ず 1 run 1 issue を守る
- 手動レーン（Power User の直接対応）は一括処理可。ただし `codex:queue` 系ラベル遷移の整合は維持する
- 失敗時は issue コメントと `codex:blocked` を付与する
- マルチオーケストレーションでは `codex:pr-opened` の滞留を成功扱いで放置しない。required check 未到着、auto-merge 未成立、競合を切り分け、必要なら `codex:blocked`・再キュー・手動介入へ進める
