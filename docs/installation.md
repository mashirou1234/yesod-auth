# インストール

## システム要件

| 要件 | バージョン |
|------|-----------|
| Docker | 20.10+ |
| Docker Compose | 2.0+ |

## Docker Composeプロファイル

YESOD Authは3つのプロファイルを提供しています：

| プロファイル | 用途 | サービス |
|-------------|------|---------|
| `default` | ローカル開発 | db, api, docs (`valkey` は常時有効) |
| `full` | 管理画面含む | db, api, admin, docs (`valkey` は常時有効) |
| `ci` | CI/CD | db-ci, api-ci (`valkey` は常時有効) |

### 開発環境

```bash
docker compose --profile default up -d
```

### 管理画面付き

```bash
docker compose --profile full up -d
```

管理画面は http://localhost:8501 でアクセスできます。

### CI相当

```bash
docker compose --profile ci up -d
```

## profile整合確認手順

`docker-compose.yml` と本ドキュメントの profile 記載が一致していることを、変更時に必ず確認してください。

1. Compose定義上の profile 一覧を確認する

```bash
docker compose config --profiles
```

期待値:

```text
ci
default
full
```

2. profile ごとのサービス対応を確認する（`docker-compose.yml` を根拠に照合）

```bash
docker compose --profile default config --services
docker compose --profile full config --services
docker compose --profile ci config --services
```

3. 起動コマンド例が `default` / `full` / `ci` の3つをすべて網羅していることを確認する

```bash
rg -n "docker compose --profile (default|full|ci) up -d" docs/installation.md
```

## 環境変数

| 変数名 | 説明 | デフォルト |
|--------|------|-----------|
| `DATABASE_URL` | PostgreSQL接続URL | - |
| `VALKEY_URL` | Valkey接続URL | - |
| `CORS_ORIGINS` | 許可するオリジン | - |
| `FRONTEND_URL` | フロントエンドURL | - |
| `MOCK_OAUTH_ENABLED` | Mock OAuth有効化（アプリ既定値は`0`。`docker compose --profile default`/`ci`ではCompose側で`1`に上書き） | `0` |
| `ACCESS_TOKEN_LIFETIME_SECONDS` | アクセストークン有効期限 | `900` |
| `REFRESH_TOKEN_LIFETIME_DAYS` | リフレッシュトークン有効期限 | `7` |

### 管理画面用環境変数

| 変数名 | 説明 | デフォルト |
|--------|------|-----------|
| `ADMIN_USER` | 管理者ユーザー名 | `admin` |
| `SESSION_EXPIRY_HOURS` | セッション有効期限（時間） | `24` |
| `DEFAULT_LANGUAGE` | デフォルト言語（en, ja, fr, ko, de） | `en` |

## OAuth認証情報

Docker Secretsまたは環境変数で設定：

| シークレット名 | 説明 |
|---------------|------|
| `google_client_id` | Google OAuth Client ID |
| `google_client_secret` | Google OAuth Client Secret |
| `github_client_id` | GitHub OAuth Client ID |
| `github_client_secret` | GitHub OAuth Client Secret |
| `discord_client_id` | Discord OAuth Client ID |
| `discord_client_secret` | Discord OAuth Client Secret |
| `x_client_id` | X (Twitter) OAuth Client ID |
| `x_client_secret` | X (Twitter) OAuth Client Secret |
| `linkedin_client_id` | LinkedIn OAuth Client ID |
| `linkedin_client_secret` | LinkedIn OAuth Client Secret |
| `facebook_client_id` | Facebook OAuth Client ID (App ID) |
| `facebook_client_secret` | Facebook OAuth Client Secret (App Secret) |
| `slack_client_id` | Slack OAuth Client ID |
| `slack_client_secret` | Slack OAuth Client Secret |
| `twitch_client_id` | Twitch OAuth Client ID |
| `twitch_client_secret` | Twitch OAuth Client Secret |
| `jwt_secret` | JWT署名用シークレット |

## セルフホスト向け秘密情報配置例

`docker-compose.yml` は `./secrets/*.txt` を参照します。セルフホスト環境では
「アプリ配置」と「秘密情報配置」を分離し、`./secrets` をシンボリックリンクで
接続するとローテーションしやすくなります。

```text
/opt/yesod-auth/
  app/        # このリポジトリを配置
  secrets/
    current/
      google_client_id.txt
      google_client_secret.txt
      discord_client_id.txt
      discord_client_secret.txt
      jwt_secret.txt
      admin_password.txt   # --profile full を使う場合のみ
```

作成例:

```bash
mkdir -p /opt/yesod-auth/secrets/current
cp secrets/*.example /opt/yesod-auth/secrets/current/
openssl rand -hex 32 > /opt/yesod-auth/secrets/current/jwt_secret.txt
openssl rand -base64 24 > /opt/yesod-auth/secrets/current/admin_password.txt
chmod 600 /opt/yesod-auth/secrets/current/*.txt

cd /opt/yesod-auth/app
ln -sfn ../secrets/current secrets
```

検証:

```bash
docker compose --profile default config >/dev/null
docker compose --profile full config >/dev/null
```

## ポート

| サービス | ポート |
|---------|-------|
| API | 8000 |
| PostgreSQL | 5432 |
| Valkey | 6379 |
| Admin | 8501 |
