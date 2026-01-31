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
docker compose up -d
```

### 5. Access the API

- API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000/health

## API Endpoints

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/auth/google` | Start Google OAuth flow |
| GET | `/auth/google/callback` | Google OAuth callback |
| GET | `/auth/discord` | Start Discord OAuth flow |
| GET | `/auth/discord/callback` | Discord OAuth callback |
| GET | `/auth/me` | Get current user info |
| POST | `/auth/logout` | Logout (invalidate token) |

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
window.location.href = 'http://localhost:8000/auth/google';

// After callback, store the token
const token = new URLSearchParams(window.location.search).get('token');
localStorage.setItem('auth_token', token);

// Use token for API requests
fetch('http://localhost:8000/auth/me', {
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
    window.location.href = `http://localhost:8000/auth/${provider}`;
  };

  const logout = () => {
    localStorage.removeItem('auth_token');
    token.value = null;
    user.value = null;
  };

  const fetchUser = async () => {
    if (!token.value) return;
    const res = await fetch('http://localhost:8000/auth/me', {
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

## License

MIT License - feel free to use this in your projects!
