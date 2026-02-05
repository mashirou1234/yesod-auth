# YESOD Auth

**OAuth 2.0認証基盤** - シンプルで安全な認証をあなたのアプリケーションに

---

## 特徴

| | |
|---|---|
| :material-shield-check: **OAuth 2.0対応** | :material-refresh: **トークンローテーション** |
| Google、GitHub、Discord、X、LinkedIn、Facebook、Slack、Twitchに対応。PKCEによるセキュアな認証フロー | リフレッシュトークンの自動ローテーションでセキュリティを強化 |
| :material-webhook: **Webhook連携** | :material-docker: **Docker対応** |
| ユーザーイベントを外部サービスにリアルタイム通知 | Docker Composeで簡単にデプロイ |

## クイックスタート

```bash
# リポジトリをクローン
git clone https://github.com/mashirou1234/yesod-auth.git
cd yesod-auth

# シークレットファイルを作成
cp secrets/*.example secrets/
# 各ファイルを編集してOAuthクレデンシャルを設定

# 起動
docker compose --profile default up -d
```

APIドキュメントは http://localhost:8000/docs で確認できます。

## アーキテクチャ

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Client    │────▶│  YESOD Auth │────▶│   OAuth     │
│   (SPA)     │◀────│    API      │◀────│  Provider   │
└─────────────┘     └──────┬──────┘     └─────────────┘
                           │
                    ┌──────┴──────┐
                    ▼             ▼
              ┌──────────┐  ┌──────────┐
              │ PostgreSQL│  │  Valkey  │
              │   (DB)    │  │ (Cache)  │
              └──────────┘  └──────────┘
```

## 対応プロバイダー

<div class="provider-icons">
  <a href="guides/oauth/google.md" title="Google">
    <img src="assets/icons/google.svg" alt="Google" width="48" height="48">
  </a>
  <a href="guides/oauth/github.md" title="GitHub">
    <img src="assets/icons/github.svg" alt="GitHub" width="48" height="48">
  </a>
  <a href="guides/oauth/discord.md" title="Discord">
    <img src="assets/icons/discord.svg" alt="Discord" width="48" height="48">
  </a>
  <a href="guides/oauth/x.md" title="X">
    <img src="assets/icons/x.svg" alt="X" width="48" height="48">
  </a>
  <a href="guides/oauth/linkedin.md" title="LinkedIn">
    <img src="assets/icons/linkedin.svg" alt="LinkedIn" width="48" height="48">
  </a>
  <a href="guides/oauth/facebook.md" title="Facebook">
    <img src="assets/icons/facebook.svg" alt="Facebook" width="48" height="48">
  </a>
  <a href="guides/oauth/slack.md" title="Slack">
    <img src="assets/icons/slack.svg" alt="Slack" width="48" height="48">
  </a>
  <a href="guides/oauth/twitch.md" title="Twitch">
    <img src="assets/icons/twitch.svg" alt="Twitch" width="48" height="48">
  </a>
</div>

詳細は[OAuth設定ガイド](guides/oauth/index.md)を参照してください。

## ライセンス

MIT License
