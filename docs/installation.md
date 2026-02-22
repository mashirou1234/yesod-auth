# インストール

## システム要件

| 要件 | バージョン |
|------|-----------|
| Docker | 20.10+ |
| Docker Compose | 2.0+ |

## Docker Composeプロファイル

YESOD Authは4つのプロファイルを提供しています：

| プロファイル | 用途 | サービス |
|-------------|------|---------|
| `default` | ローカル開発 | db, valkey, api, docs |
| `full` | 管理画面含む | db, valkey, api, admin, docs |
| `ci` | CI/CD | db-ci, valkey, api-ci |
| `ngrok` | HTTPS必須プロバイダー用 | ngrok, ngrok-sync（apiに依存） |

### 開発環境

```bash
docker compose --profile default up -d
```

### 管理画面付き

```bash
docker compose --profile full up -d
```

管理画面は http://localhost:8501 でアクセスできます。

### ngrokトンネル付き（HTTPS必須プロバイダー用）

X (Twitter)など、リダイレクトURIにHTTPSが必須のプロバイダーを使用する場合：

```bash
docker compose --profile default --profile ngrok up -d
```

ngrokダッシュボードは http://localhost:4040 でアクセスできます。
ngrok URLは自動的にValkeyに保存され、APIが動的にコールバックURLを生成します。

## 環境変数

| 変数名 | 説明 | デフォルト |
|--------|------|-----------|
| `DATABASE_URL` | PostgreSQL接続URL | - |
| `VALKEY_URL` | Valkey接続URL | - |
| `CORS_ORIGINS` | 許可するオリジン | - |
| `FRONTEND_URL` | フロントエンドURL | - |
| `MOCK_OAUTH_ENABLED` | Mock OAuth有効化 | `0` |
| `ACCESS_TOKEN_LIFETIME_SECONDS` | アクセストークン有効期限 | `900` |
| `REFRESH_TOKEN_LIFETIME_DAYS` | リフレッシュトークン有効期限 | `7` |
| `RATE_LIMIT_PER_MINUTE` | レートリミット（分あたり） | `20` |

### 管理画面用環境変数

| 変数名 | 説明 | デフォルト |
|--------|------|-----------|
| `ADMIN_USER` | 管理者ユーザー名 | `admin` |
| `SESSION_EXPIRY_HOURS` | セッション有効期限（時間） | `24` |
| `DEFAULT_LANGUAGE` | デフォルト言語（en, ja, fr, ko, de） | `en` |

## Docker Secrets

認証情報はDocker Secretsで管理します。`secrets/`ディレクトリにテキストファイルとして配置してください。

### OAuth認証情報

| シークレット名 | ファイル | 説明 |
|---------------|---------|------|
| `google_client_id` | `secrets/google_client_id.txt` | Google OAuth Client ID |
| `google_client_secret` | `secrets/google_client_secret.txt` | Google OAuth Client Secret |
| `github_client_id` | `secrets/github_client_id.txt` | GitHub OAuth Client ID |
| `github_client_secret` | `secrets/github_client_secret.txt` | GitHub OAuth Client Secret |
| `discord_client_id` | `secrets/discord_client_id.txt` | Discord OAuth Client ID |
| `discord_client_secret` | `secrets/discord_client_secret.txt` | Discord OAuth Client Secret |
| `x_client_id` | `secrets/x_client_id.txt` | X (Twitter) OAuth Client ID |
| `x_client_secret` | `secrets/x_client_secret.txt` | X (Twitter) OAuth Client Secret |
| `linkedin_client_id` | `secrets/linkedin_client_id.txt` | LinkedIn OAuth Client ID |
| `linkedin_client_secret` | `secrets/linkedin_client_secret.txt` | LinkedIn OAuth Client Secret |
| `facebook_client_id` | `secrets/facebook_client_id.txt` | Facebook OAuth Client ID (App ID) |
| `facebook_client_secret` | `secrets/facebook_client_secret.txt` | Facebook OAuth Client Secret (App Secret) |
| `slack_client_id` | `secrets/slack_client_id.txt` | Slack OAuth Client ID |
| `slack_client_secret` | `secrets/slack_client_secret.txt` | Slack OAuth Client Secret |
| `twitch_client_id` | `secrets/twitch_client_id.txt` | Twitch OAuth Client ID |
| `twitch_client_secret` | `secrets/twitch_client_secret.txt` | Twitch OAuth Client Secret |

### その他のシークレット

| シークレット名 | ファイル | 説明 |
|---------------|---------|------|
| `jwt_secret` | `secrets/jwt_secret.txt` | JWT署名用シークレット |
| `admin_password` | `secrets/admin_password.txt` | 管理画面のパスワード |
| `ngrok_authtoken` | `secrets/ngrok_authtoken.txt` | ngrok認証トークン（ngrokプロファイル使用時のみ） |

## ポート

| サービス | ホスト側ポート | コンテナ内ポート | 備考 |
|---------|--------------|----------------|------|
| API | 8000 | 8000 | |
| PostgreSQL（開発） | 5434 | 5432 | 他プロジェクトとの競合回避のため5434 |
| PostgreSQL（CI） | 5433 | 5432 | CI専用 |
| Valkey | 6379 | 6379 | |
| Admin | 8501 | 8501 | fullプロファイル時のみ |
| Docs | 8080 | 8000 | MkDocsプレビュー |
| ngrokダッシュボード | 4040 | 4040 | ngrokプロファイル時のみ |
| API（CI） | 8001 | 8000 | CI専用 |
