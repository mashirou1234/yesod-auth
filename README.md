# YESOD Auth

🔐 Docker-ready OAuth authentication API template with Google & Discord support.

> **YESOD** (יסוד) - "Foundation" in Hebrew. The ninth sephira in the Kabbalistic Tree of Life, representing the foundation that connects the spiritual and physical realms.

## Features

- 🔑 OAuth 2.0 authentication (Google, Discord)
- 🐳 Docker Compose ready - just add secrets and run
- 🗄️ PostgreSQL with automatic migrations
- 🔒 JWT-based session management
- 📡 REST API - integrate with any frontend
- 👤 User profile with avatar support

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/mashirou1234/yesod-auth.git
cd yesod-auth
```

### 2. Set up OAuth credentials

#### Google OAuth
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable "Google+ API" or "Google Identity"
4. Go to "Credentials" → "Create Credentials" → "OAuth 2.0 Client ID"
5. Set authorized redirect URI: `http://localhost:8000/auth/google/callback`
6. Copy Client ID and Client Secret

#### Discord OAuth
1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application
3. Go to "OAuth2" section
4. Add redirect URI: `http://localhost:8000/auth/discord/callback`
5. Copy Client ID and Client Secret

### 3. Configure secrets

```bash
# Create secrets directory (already exists in repo)
mkdir -p secrets

# Add your credentials
echo "your-google-client-id" > secrets/google_client_id.txt
echo "your-google-client-secret" > secrets/google_client_secret.txt
echo "your-discord-client-id" > secrets/discord_client_id.txt
echo "your-discord-client-secret" > secrets/discord_client_secret.txt

# Generate JWT secret (or use your own)
openssl rand -hex 32 > secrets/jwt_secret.txt
```

### 4. Start the service

```bash
# API + DB + Valkey (開発用)
docker compose up -d

# Admin画面も含めて起動
docker compose --profile full up -d

# CI用（軽量構成）
docker compose --profile ci up -d
```

### 5. Access the API

- API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000/health

## API Endpoints

Base URL: `http://localhost:8000/api/v1`

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/auth/google` | Start Google OAuth flow |
| GET | `/auth/google/callback` | Google OAuth callback |
| GET | `/auth/discord` | Start Discord OAuth flow |
| GET | `/auth/discord/callback` | Discord OAuth callback |
| POST | `/auth/refresh` | Refresh access token |
| POST | `/auth/logout` | Logout (invalidate token) |

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

#### Current User (`/auth/me`)
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "display_name": "User Name",
  "avatar_url": "https://...",
  "created_at": "2025-01-31T00:00:00Z"
}
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

  const login = (provider: 'google' | 'discord') => {
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
| `JWT_LIFETIME_SECONDS` | Token expiration time | `86400` (24 hours) |
| `CORS_ORIGINS` | Allowed CORS origins | `http://localhost:3000` |
| `FRONTEND_URL` | Frontend URL for redirects | `http://localhost:3000` |

### Docker Secrets

| File | Description |
|------|-------------|
| `secrets/google_client_id.txt` | Google OAuth Client ID |
| `secrets/google_client_secret.txt` | Google OAuth Client Secret |
| `secrets/discord_client_id.txt` | Discord OAuth Client ID |
| `secrets/discord_client_secret.txt` | Discord OAuth Client Secret |
| `secrets/jwt_secret.txt` | JWT signing secret |

## Admin Panel

管理画面は http://localhost:8501 でアクセスできます。

### Features
- **Users**: ユーザー一覧・検索
- **Sessions**: アクティブセッション管理
- **DB Schema**: ER図・テーブル詳細・統計
- **Audit Logs**: ログイン履歴・認証イベント
- **API Test**: APIエンドポイントのテスト

### Default Credentials
```
Username: admin
Password: (secrets/admin_password.txt の内容)
```

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

実際のOAuthプロバイダーなしでテストするには、`MOCK_OAUTH_ENABLED=1` を設定します。

```bash
# docker-compose.ymlに追加
environment:
  - MOCK_OAUTH_ENABLED=1
```

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
cd api
pip install -r requirements.txt
pytest
```

### Generate TypeScript Types

OpenAPIスキーマからTypeScript型定義を生成:

```bash
# 前提: npm install -g openapi-typescript
./scripts/generate-types.sh ./frontend/src/types
```

生成された型の使用例:

```typescript
import type { paths, components } from "./types/api";

type User = components["schemas"]["UserResponse"];
type TokenPair = components["schemas"]["TokenPairResponse"];
```

### Seed Test Data

監査ログのテストデータを投入する場合：

```bash
docker exec -i yesod-db psql -U yesod_user -d yesod < scripts/seed_audit_data.sql
```

これにより `login_history` と `auth_events` に各10万件のテストデータが投入されます。

### Database Migrations

```bash
# マイグレーション実行（コンテナ起動時に自動実行）
docker exec yesod-api alembic upgrade head

# マイグレーション状態確認
docker exec yesod-api alembic current
```

## License

MIT License - feel free to use this in your projects!
