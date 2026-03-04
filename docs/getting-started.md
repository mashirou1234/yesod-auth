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

## 2.5 コールバックURLの検証

OAuth導入時は、実装前に「登録したコールバックURL」と「実際にYESOD Authが受けるURL」が一致することを確認します。

### 基本ルール

- 形式は `https://<api-domain>/api/v1/auth/<provider>/callback`
- `http` はローカル開発以外で使わない
- 末尾スラッシュを付けない（`.../callback/` は不可）
- `provider` は実際に有効化したものだけ登録する

### 検証チェックリスト

1. API公開URLを決める（例: `https://api.example.com`）
2. プロバイダーごとに callback URL を作る（例: `https://api.example.com/api/v1/auth/google/callback`）
3. OAuthプロバイダー管理画面の設定値と、`docs/api/auth.md` のパス仕様が一致することを確認する
4. リバースプロキシ利用時は `X-Forwarded-Proto=https` が正しく渡る構成にする
5. ログイン実行後、`Invalid state` や `redirect_uri_mismatch` が出ないことを確認する

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

## 次のステップ

- [OAuth設定](guides/oauth/index.md) - 各プロバイダーの設定方法
- [トラブルシューティング](help/troubleshooting.md#state-mismatch-flow) - `Invalid or expired state` の診断手順
- [Webhook設定](guides/webhooks.md) - 外部サービス連携
- [デプロイ](guides/deployment.md) - 本番環境へのデプロイ
