# Codex Project Agent Notes (GitHub)

- 日本語で簡潔に報告する
- まず `artifacts/` を確認して前回結果を把握する
- `scripts/orch.sh` を使う自動レーンでは必ず 1 run 1 issue を守る
- 手動レーン（Power User の直接対応）は一括処理可。ただし `codex:queue` 系ラベル遷移の整合は維持する
- Project 併用 repo では、queue 着手前に linked Project の status / priority を確認する
- 失敗時は issue コメントと `codex:blocked` を付与する
- `codex:pr-opened` の Issue は merge 確認後の reconcile で close する
