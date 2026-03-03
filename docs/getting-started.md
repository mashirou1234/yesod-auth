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

## 5. Webhook導入の最短導線

Webhookは、getting-started から以下の2クリック以内で設定手順へ到達できます。

1. このページの「次のステップ」から [Webhook設定](guides/webhooks.md) を開く
2. ガイド内の [ローカルテスト](guides/webhooks.md#ローカルテスト) に沿って設定する

### Webhook導入の前提条件

- API が起動していること（`docker compose --profile default up -d`）
- `config/webhooks.yaml` を作成済みであること
- Webhook受信先URLを用意できること（例: [webhook.site](https://webhook.site)）

### 送信確認の最小手順

1. [Webhook設定](guides/webhooks.md) の例を使って `config/webhooks.yaml` を作成する
2. Mock OAuth ログインを実行する
3. 配信履歴 API で Webhook 送信結果を確認する

```bash
curl "http://localhost:8000/api/v1/auth/mock/login?user=alice&provider=google"
curl http://localhost:8000/api/v1/admin/webhooks/deliveries
```

## 次のステップ

- [OAuth設定](guides/oauth/index.md) - 各プロバイダーの設定方法
- [トラブルシューティング](help/troubleshooting.md#state-mismatch-flow) - `Invalid or expired state` の診断手順
- [Webhook設定](guides/webhooks.md) - 外部サービス連携
- [デプロイ](guides/deployment.md) - 本番環境へのデプロイ
