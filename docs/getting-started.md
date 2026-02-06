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

## 3. 起動

```bash
docker compose --profile default up -d
```

### HTTPS必須プロバイダー（X等）を使用する場合

X (Twitter)などHTTPSが必須のプロバイダーを使用する場合は、ngrokプロファイルも起動します：

```bash
# ngrok authtokenを設定
echo "your-ngrok-authtoken" > secrets/ngrok_authtoken.txt

# ngrokプロファイルを含めて起動
docker compose --profile default --profile ngrok up -d
```

ngrokが発行するHTTPS URLは自動的にValkeyに保存され、OAuth認証時に使用されます。
管理画面（`http://localhost:8501`）のAPIテストページでngrok URLを確認できます。

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
