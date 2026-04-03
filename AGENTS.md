# Codex Project Agent Notes (GitHub)

- 日本語で簡潔に報告する
- `artifacts/` は必要なときだけ参照し、開始時に全体確認しない
- まずは `artifacts/orch_result.json` を確認し、失敗調査時のみ `artifacts/runs/<work_category>/<system_category>/run_*.log` と `artifacts/test.log` を見る
- `scripts/blackrain.sh` を使う自動レーンでは必ず 1 run 1 issue を守る
- 手動レーン（Power User の直接対応）は一括処理可。ただし `codex:queue` 系ラベル遷移の整合は維持する
- Project 併用 repo では、queue 着手前に linked Project の status / priority を確認する
- 失敗時は issue コメントと `codex:blocked` を付与する
- `codex:pr-opened` の Issue は merge を観測した run で close し、残件は reconcile で回収する
