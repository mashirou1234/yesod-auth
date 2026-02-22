# YESOD Auth

🔐 Docker-ready OAuth authentication API template with multi-provider support.

> **YESOD** (יסוד) - "Foundation" in Hebrew. The ninth sephira in the Kabbalistic Tree of Life, representing the foundation that connects the spiritual and physical realms.

## Features

- 🔑 OAuth 2.0 authentication (Google, GitHub, Discord, X, LinkedIn, Facebook, Slack, Twitch)
- 🆔 OIDC互換ID Token発行（非OIDCプロバイダー含む全プロバイダー対応）
- 🐳 Docker Compose ready - just add secrets and run
- 🗄️ PostgreSQL with automatic migrations
- 🔒 JWT-based session management with PKCE
- 📡 REST API - integrate with any frontend
- 👤 User profile with avatar support
- 🔗 Multiple OAuth account linking
- 📣 Webhook連携（ユーザーイベント通知）
- 🌐 ngrok統合（HTTPS必須プロバイダーの開発用）
- 🛡️ 管理画面（ユーザー管理、セッション管理、監査ログ）

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/mashirou1234/yesod-auth.git
cd yesod-auth
```

### 2. Configure secrets

```bash
# Create secrets directory (already exists in repo)
mkdir -p secrets

# JWT secret（必須）
openssl rand -hex 32 > secrets/jwt_secret.txt

# 管理画面パスワード
echo "your-admin-password" > secrets/admin_password.txt

# 使用するプロバイダーのクレデンシャルを設定
echo "your-google-client-id" > secrets/google_client_id.txt
echo "your-google-client-secret" > secrets/google_client_secret.txt
echo "your-discord-client-id" > secrets/discord_client_id.txt
echo "your-discord-client-secret" > secrets/discord_client_secret.txt
# 他のプロバイダーも同様に設定
```

各プロバイダーの設定方法は[OAuth設定ガイド](https://mashirou1234.github.io/yesod-auth/guides/oauth/)を参照してください。

### 3. Start the service

```bash
# API + DB + Valkey + Docs（開発用）
docker compose --profile default up -d

# 管理画面も含めて起動
docker compose --profile full up -d

# ngrokトンネル付き（X等のHTTPS必須プロバイダー用）
docker compose --profile default --profile ngrok up -d
```

### 4. Access the API

- API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000/health
- Admin: http://localhost:8501（fullプロファイル時）
- Docs: http://localhost:8080（MkDocsプレビュー）

## 対応プロバイダー

| プロバイダー | PKCE | OIDC | ID Token |
|-------------|------|------|----------|
| Google | ✅ | ✅（ネイティブ） | ✅ |
| GitHub | ✅ | ❌ | ✅（自己発行） |
| Discord | ✅ | ❌ | ✅（自己発行） |
| X (Twitter) | ✅ | ❌ | ✅（自己発行） |
| LinkedIn | ✅ | ✅（ネイティブ） | ✅ |
| Facebook | ✅ | ❌ | ✅（自己発行） |
| Slack | ✅ | ✅（ネイティブ） | ✅ |
| Twitch | ✅ | ❌ | ✅（自己発行） |

## Docker Compose Profiles

| プロファイル | 用途 | サービス |
|-------------|------|---------|
| `default` | ローカル開発 | db, valkey, api, docs |
| `full` | 管理画面含む | db, valkey, api, admin, docs |
| `ci` | CI/CD用軽量構成 | db-ci, valkey, api-ci |
| `ngrok` | HTTPS必須プロバイダー用 | ngrok, ngrok-sync（apiに依存） |

## API Endpoints

Base URL: `http://localhost:8000/api/v1`

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/auth/google` | Start Google OAuth flow |
| GET | `/auth/google/callback` | Google OAuth callback |
| GET | `/auth/github` | Start GitHub OAuth flow |
| GET | `/auth/github/callback` | GitHub OAuth callback |
| GET | `/auth/discord` | Start Discord OAuth flow |
| GET | `/auth/discord/callback` | Discord OAuth callback |
| GET | `/auth/x` | Start X (Twitter) OAuth flow |
| GET | `/auth/x/callback` | X OAuth callback |
| GET | `/auth/linkedin` | Start LinkedIn OAuth flow |
| GET | `/auth/linkedin/callback` | LinkedIn OAuth callback |
| GET | `/auth/facebook` | Start Facebook OAuth flow |
| GET | `/auth/facebook/callback` | Facebook OAuth callback |
| GET | `/auth/slack` | Start Slack OAuth flow |
| GET | `/auth/slack/callback` | Slack OAuth callback |
| GET | `/auth/twitch` | Start Twitch OAuth flow |
| GET | `/auth/twitch/callback` | Twitch OAuth callback |
| POST | `/auth/refresh` | Refresh access token |
| POST | `/auth/logout` | Logout (invalidate token) |

### OIDC

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/.well-known/openid-configuration` | OpenID Connect設定 |
| GET | `/.well-known/jwks.json` | JSON Web Key Set |

### Users

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/users/me` | Get current user info |
| PUT | `/users/me` | Update profile |
| DELETE | `/users/me` | Delete account (soft delete) |
| POST | `/users/me/sync-from-provider` | Sync profile from OAuth provider |

### Accounts

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/accounts/me` | Get linked OAuth accounts |
| GET | `/accounts/me/link/{provider}` | Link additional OAuth provider |
| DELETE | `/accounts/me/{provider}` | Unlink OAuth provider |

### Sessions

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/sessions/me` | Get active sessions |
| DELETE | `/sessions/me/{session_id}` | Revoke specific session |
| DELETE | `/sessions/me` | Revoke all sessions |

### Webhooks

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/admin/webhooks/endpoints` | Get webhook endpoints |
| GET | `/admin/webhooks/deliveries` | Get delivery history |

### Response Format

#### Successful Login (Callback Response)
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "display_name": "User Name",
    "avatar_url": "https://...",
    "provider": "google"
  }
}
```

#### Current User (`/users/me`)
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "display_name": "User Name",
  "avatar_url": "https://...",
  "created_at": "2025-01-31T00:00:00Z"
}
```

## Docker Secrets

| ファイル | 説明 | 必須 |
|---------|------|------|
| `secrets/jwt_secret.txt` | JWT署名用シークレット | ✅ |
| `secrets/admin_password.txt` | 管理画面パスワード | fullプロファイル時 |
| `secrets/ngrok_authtoken.txt` | ngrok認証トークン | ngrokプロファイル時 |
| `secrets/google_client_id.txt` | Google OAuth Client ID | |
| `secrets/google_client_secret.txt` | Google OAuth Client Secret | |
| `secrets/github_client_id.txt` | GitHub OAuth Client ID | |
| `secrets/github_client_secret.txt` | GitHub OAuth Client Secret | |
| `secrets/discord_client_id.txt` | Discord OAuth Client ID | |
| `secrets/discord_client_secret.txt` | Discord OAuth Client Secret | |
| `secrets/x_client_id.txt` | X (Twitter) OAuth Client ID | |
| `secrets/x_client_secret.txt` | X (Twitter) OAuth Client Secret | |
| `secrets/linkedin_client_id.txt` | LinkedIn OAuth Client ID | |
| `secrets/linkedin_client_secret.txt` | LinkedIn OAuth Client Secret | |
| `secrets/facebook_client_id.txt` | Facebook OAuth Client ID | |
| `secrets/facebook_client_secret.txt` | Facebook OAuth Client Secret | |
| `secrets/slack_client_id.txt` | Slack OAuth Client ID | |
| `secrets/slack_client_secret.txt` | Slack OAuth Client Secret | |
| `secrets/twitch_client_id.txt` | Twitch OAuth Client ID | |
| `secrets/twitch_client_secret.txt` | Twitch OAuth Client Secret | |

## ポート一覧

| サービス | ポート | 備考 |
|---------|-------|------|
| API | 8000 | |
| PostgreSQL（開発） | 5434 | 他プロジェクトとの競合回避 |
| PostgreSQL（CI） | 5433 | CI専用 |
| Valkey | 6379 | |
| Admin | 8501 | fullプロファイル時 |
| Docs | 8080 | MkDocsプレビュー |
| ngrokダッシュボード | 4040 | ngrokプロファイル時 |
| API（CI） | 8001 | CI専用 |

## ngrok統合

X (Twitter)など、OAuthリダイレクトURIにHTTPSが必須のプロバイダーを開発環境で使用する場合、ngrokトンネルを利用できます。

### セットアップ

1. [ngrok](https://ngrok.com/)でアカウントを作成し、認証トークンを取得
2. シークレットファイルを作成：
   ```bash
   echo "your-ngrok-authtoken" > secrets/ngrok_authtoken.txt
   ```
3. ngrokプロファイル付きで起動：
   ```bash
   docker compose --profile default --profile ngrok up -d
   ```

### 動作の仕組み

1. `ngrok`コンテナがAPIサーバーへのHTTPSトンネルを作成
2. `ngrok-sync`コンテナがngrok APIからパブリックURLを取得し、Valkeyに保存
3. APIサーバーがOAuthコールバックURL生成時にValkeyからngrok URLを自動取得
4. 各プロバイダーのコールバックURLが動的にHTTPS URLに切り替わる

ngrokダッシュボード（http://localhost:4040）でトンネルの状態を確認できます。

## Admin Panel

管理画面は http://localhost:8501 でアクセスできます（fullプロファイル時）。

### Features
- **Users**: ユーザー一覧・検索
- **Sessions**: アクティブセッション管理
- **DB Schema**: ER図・テーブル詳細・統計
- **Audit Logs**: ログイン履歴・認証イベント
- **API Test**: APIエンドポイントのテスト
- **OIDC Test**: OpenID Connect設定・JWKSの確認

### Default Credentials
```
Username: admin
Password: (secrets/admin_password.txt の内容)
```

## Frontend Integration

### JavaScript Example

```javascript
// Redirect to OAuth login
window.location.href = 'http://localhost:8000/api/v1/auth/google';

// After callback, store the token
const token = new URLSearchParams(window.location.search).get('token');
localStorage.setItem('auth_token', token);

// Use token for API requests
fetch('http://localhost:8000/api/v1/users/me', {
  headers: {
    'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
  }
});
```

### React/Vue/Nuxt Example

```typescript
// composables/useAuth.ts
export function useAuth() {
  const token = ref(localStorage.getItem('auth_token'));
  const user = ref(null);

  const login = (provider: 'google' | 'github' | 'discord' | 'x' | 'linkedin' | 'facebook' | 'slack' | 'twitch') => {
    window.location.href = `http://localhost:8000/api/v1/auth/${provider}`;
  };

  const logout = () => {
    localStorage.removeItem('auth_token');
    token.value = null;
    user.value = null;
  };

  const fetchUser = async () => {
    if (!token.value) return;
    const res = await fetch('http://localhost:8000/api/v1/users/me', {
      headers: { 'Authorization': `Bearer ${token.value}` }
    });
    user.value = await res.json();
  };

  return { user, token, login, logout, fetchUser };
}
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://...` |
| `ACCESS_TOKEN_LIFETIME_SECONDS` | Access token expiration | `900` (15 min) |
| `REFRESH_TOKEN_LIFETIME_DAYS` | Refresh token expiration | `7` (7 days) |
| `CORS_ORIGINS` | Allowed CORS origins | `http://localhost:3000` |
| `FRONTEND_URL` | Frontend URL for redirects | `http://localhost:3000` |
| `RATE_LIMIT_PER_MINUTE` | Rate limit per minute | `20` |

## Monitoring

### Prometheus Metrics

`/api/v1/metrics` エンドポイントでPrometheus形式のメトリクスを取得できます。

```bash
curl http://localhost:8000/api/v1/metrics
```

### Audit Logs

監査ログは `audit` スキーマに保存されます（36ヶ月保持、月次パーティション）。

- `audit.login_history`: ログイン試行履歴
- `audit.auth_events`: 認証イベント（ログイン、ログアウト、プロフィール更新等）

## Development

### Mock OAuth (Development Mode)

実際のOAuthプロバイダーなしでテストするには、`MOCK_OAUTH_ENABLED=1` を設定します（デフォルトで有効）。

利用可能なモックユーザー:
- `alice` - alice@example.com
- `bob` - bob@example.com  
- `charlie` - charlie@example.com

```bash
# モックログイン
curl "http://localhost:8000/api/v1/auth/mock/login?user=alice&provider=google"

# 利用可能なモックユーザー一覧
curl "http://localhost:8000/api/v1/auth/mock/users"
```

### Running Tests

```bash
# Docker上でテスト実行（推奨）
docker compose --profile ci build api-ci
docker compose --profile ci run --rm api-ci pytest

# テスト完了後、必ずコンテナを停止
docker compose --profile ci down
```

### Generate TypeScript Types

OpenAPIスキーマからTypeScript型定義を生成:

```bash
# 前提: npm install -g openapi-typescript
./scripts/generate-types.sh ./frontend/src/types
```

### Database Migrations

```bash
# マイグレーション実行（コンテナ起動時に自動実行）
docker exec yesod-api alembic upgrade head

# マイグレーション状態確認
docker exec yesod-api alembic current
```

## License

MIT License - feel free to use this in your projects!
