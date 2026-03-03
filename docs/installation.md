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

### 必須（未設定時に運用影響が出る）

| 変数/シークレット | 用途 | 未設定時の症状 | 既定値/補足 |
|------------------|------|----------------|------------|
| `DATABASE_URL` | PostgreSQL接続先 | API/管理画面がDB接続エラーで起動失敗、または意図しないDBへ接続 | 開発向け既定値あり。セルフホストでは明示設定推奨 |
| `VALKEY_URL` | Valkey接続先（state/レート制御） | OAuthの`state mismatch`やセッション関連エラーが発生しやすくなる | 開発向け既定値あり。セルフホストでは明示設定推奨 |
| `FRONTEND_URL` | OAuth完了後のリダイレクト先 | ログイン後の遷移先が不正になり、認証完了後のUXが壊れる | 既定値 `http://localhost:3000` |
| `CORS_ORIGINS` | API許可オリジン | ブラウザから`CORS`エラーでAPI呼び出し失敗 | 既定値 `http://localhost:3000,http://localhost:5173` |
| `jwt_secret` | JWT署名鍵 | トークン検証不整合や`401`が発生。既定値運用はセキュリティ上非推奨 | Docker Secret推奨（`secrets/jwt_secret.txt`） |
| `<provider>_client_id` / `<provider>_client_secret` | OAuth provider資格情報 | 該当providerで`invalid_client`や認証失敗が発生 | 有効化して使うprovider分のみ必須 |

### 推奨（運用品質・セキュリティ向上）

| 変数名 | 説明 | デフォルト |
|--------|------|-----------|
| `ACCESS_TOKEN_LIFETIME_SECONDS` | アクセストークン有効期限 | `900` |
| `REFRESH_TOKEN_LIFETIME_DAYS` | リフレッシュトークン有効期限 | `7` |
| `SESSION_EXPIRY_HOURS` | 管理画面セッション有効期限（時間） | `24` |

### 任意（要件に応じて設定）

| 変数名 | 説明 | デフォルト |
|--------|------|-----------|
| `MOCK_OAUTH_ENABLED` | Mock OAuth有効化（アプリ既定値は`0`。`docker compose --profile default`/`ci`ではCompose側で`1`に上書き） | `0` |
| `ADMIN_USER` | 管理者ユーザー名 | `admin` |
| `DEFAULT_LANGUAGE` | 管理画面デフォルト言語（en, ja, fr, ko, de） | `en` |

関連ヘルプ:
- [トラブルシューティング（認証エラー）](./help/troubleshooting.md#認証エラー)

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

## ポート

| サービス | ポート |
|---------|-------|
| API | 8000 |
| PostgreSQL | 5432 |
| Valkey | 6379 |
| Admin | 8501 |
