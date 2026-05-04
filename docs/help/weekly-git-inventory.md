# 週次Git棚卸し Runbook

この手順は、`yesod-auth` の Git 状態を週次で確認し、重複コメントを避けながら記録するための運用手順です。2026-05-04 以降の棚卸し issue は、その時点で open な棚卸し issue へ記録し、完了後に `completed` として close します。

## 目的

- 未整理ブランチ、未コミット変更、不要な差分の早期発見
- open な週次Git棚卸し issue への定期記録の標準化
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
3. コメント先は `mashirou1234/yesod-auth` の open な週次Git棚卸し issue を優先する
4. 棚卸し結果を投稿し、不要ブランチや未コミット変更がなければ `completed` で close する

## 参考

- [週次Git棚卸し Issue 検索](https://github.com/mashirou1234/yesod-auth/issues?q=is%3Aissue+%E9%80%B1%E6%AC%A1Git%E6%A3%9A%E5%8D%B8%E3%81%97)
