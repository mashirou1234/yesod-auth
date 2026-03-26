# YESOD Auth

🔐 Docker-ready OAuth authentication API template with multi-provider OAuth support.

> **YESOD** (יסוד) - "Foundation" in Hebrew. The ninth sephira in the Kabbalistic Tree of Life, representing the foundation that connects the spiritual and physical realms.

## Features

- 🔑 OAuth 2.0 authentication for 8 providers (Google, GitHub, X (Twitter), LinkedIn, Facebook, Discord, Slack, Twitch)
- 🛡️ PKCE-enabled secure OAuth flow
- 🔄 Refresh token rotation support
- 📣 Webhook integration for user events
- 🐳 Docker Compose ready - just add secrets and run
- 🗄️ PostgreSQL with automatic migrations
- 🔒 JWT-based session management
- 📡 REST API - integrate with any frontend
- 👤 User profile with avatar support

> Source of truth for provider support notation: `docs/guides/oauth/index.md`.
> Source of truth for top-level feature descriptions: `docs/index.md`.

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/mashirou1234/yesod-auth.git
cd yesod-auth
```

### 2. Set up OAuth credentials (Client ID / Client Secret)

Choose one or more providers and create OAuth apps:

- Self-hosted production callback format: `https://<your-domain>/api/v1/auth/{provider}/callback`

- Google: <http://localhost:8000/api/v1/auth/google/callback>
- GitHub: <http://localhost:8000/api/v1/auth/github/callback>
- Discord: <http://localhost:8000/api/v1/auth/discord/callback>
- X: <http://localhost:8000/api/v1/auth/x/callback>
- LinkedIn: <http://localhost:8000/api/v1/auth/linkedin/callback>
- Facebook: <http://localhost:8000/api/v1/auth/facebook/callback>
- Slack: <http://localhost:8000/api/v1/auth/slack/callback>
- Twitch: <http://localhost:8000/api/v1/auth/twitch/callback>

Provider-specific setup steps are documented in [`docs/guides/oauth/`](docs/guides/oauth/index.md).

### 3. Configure secrets

```bash
# Generate local secret files from templates
cp secrets/*.example secrets/

# Fill OAuth credentials for the providers you use
$EDITOR secrets/google_client_id.txt
$EDITOR secrets/google_client_secret.txt
$EDITOR secrets/github_client_id.txt
$EDITOR secrets/github_client_secret.txt

# Generate JWT secret (or use your own value)
openssl rand -hex 32 > secrets/jwt_secret.txt

# Required when running --profile full (admin panel)
openssl rand -base64 24 > secrets/admin_password.txt

# Restrict file permissions
chmod 600 secrets/*.txt
```

初回導入で `secret ... not found` が出た場合は、[`docs/installation.md` の最短復旧コマンド](docs/installation.md#1-docker-compose-up-で-secret-未設定エラーになる) を実行してください。

#### Self-hosted secret layout example

`docker-compose.yml` reads from `./secrets/*.txt`. For self-hosted deployments,
prepare a dedicated secret directory and mount it as `./secrets` with a symlink:

```text
/opt/yesod-auth/
  app/        # git checkout
  secrets/
    current/
      google_client_id.txt
      google_client_secret.txt
      discord_client_id.txt
      discord_client_secret.txt
      jwt_secret.txt
      admin_password.txt   # only for --profile full
```

```bash
cd /opt/yesod-auth/app
ln -sfn ../secrets/current secrets
```

### 4. Start the service

```bash
# API + DB + Valkey (開発用)
docker compose --profile default up -d

# Admin画面も含めて起動
docker compose --profile default --profile full up -d

# CI用（軽量構成）
docker compose --profile ci up -d
```

最小動作確認は [`docs/installation.md` の「docker compose利用時の最小確認手順」](docs/installation.md#docker-compose利用時の最小確認手順) を参照してください。

### 5. Access the API

- API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000/health
- Callback URL validation checklist: [docs/getting-started.md](docs/getting-started.md#25-コールバックurlの検証)

Quick API connectivity check:

```bash
curl -sS http://localhost:8000/health
# {"status":"healthy"}

curl -sS -o /dev/null -w "%{http_code}\n" http://localhost:8000/api/v1/metrics
# 200
```

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
| GET | `/auth/x` | Start X OAuth flow |
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

運用時の注意点（refresh token のローテーション/再ログイン方針）は [docs/installation.md](docs/installation.md#リフレッシュトークン運用時の注意) を参照してください。
認証エラーコードの運用向け一覧は [`docs/api/auth.md`](docs/api/auth.md) を参照してください。
`invalid_grant` が断続的に発生する場合は、[clock skew 診断手順](docs/help/troubleshooting.md#oauth-clock-skew) を参照してください。

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
| `JWT_LIFETIME_SECONDS` | Token expiration time | `86400` (24 hours) |
| `CORS_ORIGINS` | Allowed CORS origins | `http://localhost:3000` |
| `FRONTEND_URL` | Frontend URL for redirects | `http://localhost:3000` |

### Docker Secrets

| File | Description |
|------|-------------|
| `secrets/google_client_id.txt` | Google OAuth Client ID |
| `secrets/google_client_secret.txt` | Google OAuth Client Secret |
| `secrets/github_client_id.txt` | GitHub OAuth Client ID |
| `secrets/github_client_secret.txt` | GitHub OAuth Client Secret |
| `secrets/discord_client_id.txt` | Discord OAuth Client ID |
| `secrets/discord_client_secret.txt` | Discord OAuth Client Secret |
| `secrets/x_client_id.txt` | X (Twitter) OAuth Client ID |
| `secrets/x_client_secret.txt` | X (Twitter) OAuth Client Secret |
| `secrets/linkedin_client_id.txt` | LinkedIn OAuth Client ID |
| `secrets/linkedin_client_secret.txt` | LinkedIn OAuth Client Secret |
| `secrets/facebook_client_id.txt` | Facebook OAuth Client ID |
| `secrets/facebook_client_secret.txt` | Facebook OAuth Client Secret |
| `secrets/slack_client_id.txt` | Slack OAuth Client ID |
| `secrets/slack_client_secret.txt` | Slack OAuth Client Secret |
| `secrets/twitch_client_id.txt` | Twitch OAuth Client ID |
| `secrets/twitch_client_secret.txt` | Twitch OAuth Client Secret |
| `secrets/jwt_secret.txt` | JWT signing secret |
| `secrets/admin_password.txt` | Admin panel password (`--profile full` only) |

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

### セルフホスト時の最小監視項目

運用開始直後は、まず次の4項目を監視対象に設定してください。

| 項目 | 確認方法 | 異常の目安 |
|------|----------|------------|
| APIヘルス | `curl -sS -o /dev/null -w "%{http_code}\n" http://localhost:8000/health` | `200` 以外が連続 |
| APIエラー率 | `docker logs --since 5m yesod-api \| rg " 5[0-9]{2} "` | 5分窓で5xxが継続発生 |
| DB接続健全性 | `docker logs --since 5m yesod-db \| rg -i "error|fatal|panic"` | 接続エラー/再起動ループ |
| OAuth失敗兆候 | `docker logs --since 10m yesod-api \| rg "invalid_client|Invalid state|OAuth callback failed"` | 同種エラーが短時間に複数回 |

### 運用時ログ確認ポイント（最小）

障害切り分け時は、次の順で 1〜3 分以内に確認すると再現性が高いです。

1. API コンテナログ: `docker logs --tail 200 yesod-api`
2. DB コンテナログ: `docker logs --tail 200 yesod-db`
3. 監査イベント件数: `docker exec yesod-db psql -U yesod_user -d yesod -c "select event_type, count(*) from audit.auth_events group by 1 order by 2 desc;"`

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

### セッション失効時の再ログイン

`401 Unauthorized` が返る場合は、`POST /api/v1/auth/refresh` でトークン再発行を試し、失敗時は OAuth ログインを再実行してください。運用時の手順は [`docs/getting-started.md`](docs/getting-started.md) の「セッション失効時の再ログイン手順」にまとめています。

### Running Tests

```bash
cd api
pip install -r requirements.txt
pytest
```

### Generated Artifacts Policy

`artifacts/` と `api/.hypothesis/`、`.codex/skills/` は再生成可能またはローカル専用のため、Git 管理対象に含めません。
週次棚卸しやレビュー時に未追跡で残っていても、コミット対象へ含めない運用を推奨します。

```bash
# 必須エントリの確認（出力されれば設定済み）
rg -n '^/artifacts/$|^artifacts/\\*\\*$|^api/.hypothesis/$|^\\.codex/skills/$' .gitignore
```

## PR Auto-Approve + Auto-Merge

This repository includes GitHub Actions workflows for automatic PR approval and merge:

- `.github/workflows/pr-auto-approve.yml`
  - Automatically approves pull requests targeting `main` or `master`
- `.github/workflows/pr-auto-merge.yml`
  - Enables GitHub auto-merge (squash) for pull requests targeting `main` or `master`
  - Actual merge happens only after all required checks pass

### Required GitHub repository settings

1. Enable `Allow auto-merge` in repository settings
2. Configure branch protection for `main`/`master` with required status checks
3. Register your CI checks (including external CI like Woodpecker) as required checks
4. Keep `PR Auto Approve` and `PR Auto Merge` workflows enabled in GitHub Actions
5. Bootstrap Codex labels when setting up the repository:

```bash
./scripts/ensure_github_labels.sh
# dry-run only (no write):
./scripts/ensure_github_labels.sh --dry-run
```

This script ensures the repository keeps the labels used by Codex / codex-orch automation:
`codex`, `codex-automation`, `codex:queue`, `codex:claimed`, `codex:blocked`, `codex:pr-opened`.

If a pull request was opened while the auto-approve / auto-merge workflows were disabled, enabling the workflows later does not retroactively register auto-merge for that PR. In that case, reopen/synchronize the PR or enable auto-merge manually.

With this setup, a PR is auto-approved and put into auto-merge waiting state on open/update, then merged automatically when required CI checks complete successfully.

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
