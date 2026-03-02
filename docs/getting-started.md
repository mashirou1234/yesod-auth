# クイックスタート

このガイドでは、YESOD Authを5分でセットアップする方法を説明します。

## 前提条件

- Docker & Docker Compose
- Google Cloud ConsoleまたはDiscord Developer Portalのアカウント

## 1. リポジトリのクローン

```bash
git clone https://github.com/mashirou1234/yesod-auth.git
cd yesod-auth
```

## 2. シークレットファイルの作成

```bash
# サンプルファイルをコピー
cp secrets/google_client_id.txt.example secrets/google_client_id.txt
cp secrets/google_client_secret.txt.example secrets/google_client_secret.txt
cp secrets/discord_client_id.txt.example secrets/discord_client_id.txt
cp secrets/discord_client_secret.txt.example secrets/discord_client_secret.txt
cp secrets/jwt_secret.txt.example secrets/jwt_secret.txt
```

各ファイルを編集して、OAuthプロバイダーから取得したクレデンシャルを設定します。

!!! tip "JWTシークレットの生成"
    ```bash
    openssl rand -base64 32 > secrets/jwt_secret.txt
    ```

### OAuthガイドへの導線

クイックスタートで起動確認した後、利用するプロバイダーの設定を進めてください。

- [OAuth設定ハブ](guides/oauth/index.md)
- [Google OAuth ガイド](guides/oauth/google.md)
- [Discord OAuth ガイド](guides/oauth/discord.md)
- [GitHub OAuth ガイド](guides/oauth/github.md)

## 3. 起動

```bash
docker compose --profile default up -d
```

## 4. 動作確認

### ヘルスチェック

```bash
curl http://localhost:8000/health
# {"status":"healthy"}
```

### APIドキュメント

ブラウザで http://localhost:8000/docs を開きます。

### Mock OAuthでテスト

開発環境では、実際のOAuthプロバイダーなしでテストできます：

```bash
curl "http://localhost:8000/api/v1/auth/mock/login?user=alice&provider=google"
```

## 次のステップ

- [OAuth設定](guides/oauth/index.md) - 各プロバイダーの設定方法
- [Webhook設定](guides/webhooks.md) - 外部サービス連携
- [デプロイ](guides/deployment.md) - 本番環境へのデプロイ
