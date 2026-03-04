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

### OAuth callback失敗時の確認順

`/api/v1/auth/{provider}/callback` が失敗した場合は、次の順で確認すると切り分けが早くなります。

1. APIログで callback エラー種別を確認
   ```bash
   docker compose logs api --since=30m | rg -n "callback|Invalid state|invalid_client|401"
   ```
2. `Invalid or expired state` の場合は、`state mismatch` 診断フローを実施
   - [トラブルシューティング: state mismatch 診断フロー](help/troubleshooting.md#state-mismatch-flow)
3. `OAuth callback failed: invalid_client` / `401` の場合は、シークレット値と provider 設定を確認
   - [トラブルシューティング: 401 Unauthorized / invalid_client](help/troubleshooting.md#401-unauthorized--invalid_client)
4. 修正後は認証を最初から再実行し、同じエラーが再現しないことを確認
   ```bash
   curl -I "http://localhost:8000/api/v1/auth/google"
   ```

## 次のステップ

- [OAuth設定](guides/oauth/index.md) - 各プロバイダーの設定方法
- [トラブルシューティング](help/troubleshooting.md#state-mismatch-flow) - `Invalid or expired state` の診断手順
- [Webhook設定](guides/webhooks.md) - 外部サービス連携
- [デプロイ](guides/deployment.md) - 本番環境へのデプロイ
