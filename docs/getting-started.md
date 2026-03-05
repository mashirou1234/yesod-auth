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

`default`プロファイルでは、Compose設定により`MOCK_OAUTH_ENABLED=1`がAPIサービスへ適用されます（アプリ既定値は`0`）。

### Compose profile差分の確認

起動前に、利用するプロファイルで有効になるサービス差分を確認できます。

```bash
# default: 最小構成（api / admin / db / redis）
docker compose --profile default config --services

# full: default + caddy
docker compose --profile default --profile full config --services

# ci: テスト用の isolated 構成
docker compose --profile ci config --services
```

`MOCK_OAUTH_ENABLED` の適用差分は次で確認できます。

```bash
docker compose --profile default config | rg "MOCK_OAUTH_ENABLED|api:"
docker compose --profile ci config | rg "MOCK_OAUTH_ENABLED|api-ci:"
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
- [トラブルシューティング](help/troubleshooting.md#state-mismatch-flow) - `Invalid or expired state` の診断手順
- [Webhook設定](guides/webhooks.md) - 外部サービス連携
- [デプロイ](guides/deployment.md) - 本番環境へのデプロイ
