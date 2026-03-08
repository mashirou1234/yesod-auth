# YESOD Auth

**OAuth 2.0認証基盤** - シンプルで安全な認証をあなたのアプリケーションに

---

## 特徴

| | |
|---|---|
| :material-shield-check: **OAuth 2.0対応** | :material-refresh: **トークンローテーション** |
| OAuthガイドで扱う8プロバイダー（Google、GitHub、Discord、X (Twitter)、LinkedIn、Facebook、Slack、Twitch）の設定手順を提供。PKCEによるセキュアな認証フロー | リフレッシュトークンの自動ローテーションでセキュリティを強化 |
| :material-webhook: **Webhook連携** | :material-docker: **Docker対応** |
| ユーザーイベントを外部サービスにリアルタイム通知 | Docker Composeで簡単にデプロイ |

> 対応プロバイダー表記の参照元（正）は `docs/guides/oauth/index.md` です。

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
セルフホスト運用時の秘密情報配置は
[インストールガイドの配置例](installation.md#セルフホスト向け秘密情報配置例)を参照してください。

主要ドキュメント:

- [Quick Start](index.md#クイックスタート)
- [OAuth設定ガイド](guides/oauth/index.md)

起動直後の最小確認は [インストール手順の「docker compose利用時の最小確認手順」](installation.md#docker-compose利用時の最小確認手順) を参照してください。

## API認証トラブル時の参照順

1. [インストール](installation.md#oauth認証情報)で OAuth シークレットと profile 設定を確認
2. [クイックスタート](getting-started.md#4-動作確認)で `/health` と `/docs` を確認
3. [トラブルシューティング](help/troubleshooting.md#state-mismatch-flow)で原因を切り分け

## 導入者向けの読み進め方

初回導入時は、次の順序で確認すると最短で環境を立ち上げられます。

1. [インストール](installation.md): 必要要件と `default` / `full` / `ci` プロファイル差分を確認
2. [クイックスタート](getting-started.md): シークレット作成から起動・ヘルスチェックまで実施
3. [OAuth設定ガイド](guides/oauth/index.md): 使用するプロバイダーだけを有効化

リフレッシュトークン運用時の注意点は [インストールガイド](installation.md#リフレッシュトークン運用時の注意) を参照してください。

OAuth provider を追加する場合は、先に[事前チェックリスト](installation.md#oauth-provider追加時の事前チェック)を実施してください。

## 学習順ガイド（導入→API→運用）

「まず動かす」「API仕様を確認する」「運用手順を固める」の順に進めると、オンボーディングと本番準備を並行しやすくなります。

1. 導入
   - [インストール](installation.md)
   - [クイックスタート](getting-started.md)
   - [OAuth設定ガイド](guides/oauth/index.md)
2. API
   - [認証API](api/auth.md)
   - [ユーザーAPI](api/users.md)
   - [Webhook API](api/webhooks.md)
3. 運用
   - [デプロイガイド](guides/deployment.md)
   - [トラブルシューティング](help/troubleshooting.md)
   - [FAQ](help/faq.md)

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
  <a href="guides/oauth/x.md" title="X (Twitter)">
    <img src="assets/icons/x.svg" alt="X (Twitter)" width="48" height="48">
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

各プロバイダーの対応状況（公式PKCE/独自PKCE/OpenID Connect/備考）は、[OAuth設定ガイド](guides/oauth/index.md)の一覧表を正として参照してください。

## ライセンス

MIT License
