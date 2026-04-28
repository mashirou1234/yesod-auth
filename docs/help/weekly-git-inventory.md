# 週次Git棚卸し Runbook

この手順は、`yesod-auth` の Git 状態を週次で確認し、重複コメントを避けながら記録するための運用手順です。

## 目的

- 未整理ブランチ、未コミット変更、不要な差分の早期発見
- Issue `#560`（週次Git棚卸し）への定期記録の標準化
- OSS 運用時の再現性確保

## 実行コマンド

```bash
bash scripts/weekly_git_inventory.sh
```

## 出力に含まれる内容

- JST 日付付きの棚卸しヘッダー
- working tree の clean/dirty 状態
- 直近ローカルブランチ一覧（最大20件）
- `origin/main` 比較の ahead/behind
- `origin/main` にマージ済みの `origin/codex/issue-*` 候補

## Issue 追記ルール

1. 同一 JST 日付のコメントが既にある場合は重複投稿しない
2. 未確認項目は推測で埋めず `未確認` として残す
3. コメント先は `mashirou1234/yesod-auth` の `#560` のみ

## 参考

- [週次Git棚卸し Issue #560](https://github.com/mashirou1234/yesod-auth/issues/560)
