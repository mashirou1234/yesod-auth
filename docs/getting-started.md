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

## 4. 最短検証フロー（3コマンド）

起動/health/mock login を3コマンドで確認します。

```bash
docker compose --profile default up -d
curl http://localhost:8000/health
curl "http://localhost:8000/api/v1/auth/mock/login?user=alice&provider=google"
```

期待値:
- `health` は `{"status":"healthy"}` を返す
- `mock login` はアクセストークンを含むJSONを返す

## 5. README Quick Startとの差分

- READMEは「最短検証3コマンド」のみを示します
- このページは前提（シークレット作成）と検証後の遷移先を含む完全版です
- `full` / `ci` など追加プロファイルはREADMEではなくこのページ基準で確認します

## 6. 次のステップ

検証後は [OAuth設定インデックス](guides/oauth/index.md) を先に確認してください。
