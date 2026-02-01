# ドキュメント管理

## 基本方針

実装とドキュメントは常に同期させる。機能追加・変更時は、関連するドキュメントも同時に更新すること。

## ドキュメント構成

```
docs/
├── index.md              # プロジェクト紹介
├── getting-started.md    # クイックスタート
├── installation.md       # インストール
├── guides/               # 設定ガイド
│   ├── oauth.md
│   ├── webhooks.md
│   └── deployment.md
├── api/                  # APIリファレンス
│   ├── auth.md
│   ├── users.md
│   └── webhooks.md
└── help/                 # ヘルプ
    ├── faq.md
    └── troubleshooting.md
```

## 更新ルール

### APIエンドポイント追加・変更時
- `docs/api/` 配下の該当ファイルを更新
- リクエスト/レスポンス例を含める

### 新機能追加時
- `docs/guides/` に設定ガイドを追加
- `docs/index.md` の機能一覧を更新
- 必要に応じてFAQを追加

### 環境変数追加時
- `docs/installation.md` の環境変数一覧を更新

### トラブルシューティング
- 既知の問題は `docs/help/troubleshooting.md` に追加

## MkDocs

- 設定ファイル: `mkdocs.yml`
- ビルド: `mkdocs build`
- ローカルプレビュー: `mkdocs serve`
- デプロイ: GitHub Actionsで自動（mainブランチへのpush時）

## 公開URL

https://mashirou1234.github.io/yesod-auth/
