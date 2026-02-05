# 認証API

## エンドポイント一覧

| メソッド | パス | 説明 |
|---------|------|------|
| GET | `/api/v1/auth/google` | Google OAuth開始 |
| GET | `/api/v1/auth/google/callback` | Googleコールバック |
| GET | `/api/v1/auth/github` | GitHub OAuth開始 |
| GET | `/api/v1/auth/github/callback` | GitHubコールバック |
| GET | `/api/v1/auth/discord` | Discord OAuth開始 |
| GET | `/api/v1/auth/discord/callback` | Discordコールバック |
| GET | `/api/v1/auth/x` | X (Twitter) OAuth開始 |
| GET | `/api/v1/auth/x/callback` | Xコールバック |
| GET | `/api/v1/auth/linkedin` | LinkedIn OAuth開始 |
| GET | `/api/v1/auth/linkedin/callback` | LinkedInコールバック |
| GET | `/api/v1/auth/facebook` | Facebook OAuth開始 |
| GET | `/api/v1/auth/facebook/callback` | Facebookコールバック |
| GET | `/api/v1/auth/slack` | Slack OAuth開始 |
| GET | `/api/v1/auth/slack/callback` | Slackコールバック |
| GET | `/api/v1/auth/twitch` | Twitch OAuth開始 |
| GET | `/api/v1/auth/twitch/callback` | Twitchコールバック |
| POST | `/api/v1/auth/refresh` | トークンリフレッシュ |
| POST | `/api/v1/auth/logout` | ログアウト |
| GET | `/.well-known/jwks.json` | JWKS（公開鍵セット） |
| GET | `/.well-known/openid-configuration` | OpenID設定 |

---

## OAuth認証フロー

### 1. 認証開始

ユーザーを認証エンドポイントにリダイレクト：

```
GET /api/v1/auth/google
```

### 2. コールバック

認証成功後、フロントエンドにリダイレクト：

```
https://your-frontend.com/auth/callback?access_token=xxx&refresh_token=xxx
```

### 3. トークン使用

APIリクエストにアクセストークンを含める：

```bash
curl -H "Authorization: Bearer <access_token>" \
  http://localhost:8000/api/v1/users/me
```

---

## トークンリフレッシュ

```bash
POST /api/v1/auth/refresh
Content-Type: application/json

{
  "refresh_token": "your-refresh-token"
}
```

**レスポンス:**

```json
{
  "access_token": "new-access-token",
  "refresh_token": "new-refresh-token"
}
```

!!! info "トークンローテーション"
    リフレッシュ時に新しいリフレッシュトークンが発行されます。
    古いリフレッシュトークンは無効化されます。

---

## ログアウト

```bash
POST /api/v1/auth/logout
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "refresh_token": "your-refresh-token"
}
```

---

## Mock OAuth（開発用）

`MOCK_OAUTH_ENABLED=1`の場合のみ利用可能：

### ログイン

```bash
GET /api/v1/auth/mock/login?user=alice&provider=google
```

**利用可能なユーザー:** `alice`, `bob`, `charlie`

**利用可能なプロバイダー:** `google`, `github`, `discord`, `x`, `linkedin`, `facebook`, `slack`, `twitch`

### ユーザー一覧

```bash
GET /api/v1/auth/mock/users
```

---

## OIDC互換エンドポイント

YESOD AuthはOpenID Connect非対応プロバイダー（GitHub, Discord, X, Facebook, Twitch）でもID Tokenを生成し、OIDC互換のエンドポイントを提供します。

### JWKS（JSON Web Key Set）

```bash
GET /.well-known/jwks.json
```

**レスポンス:**

```json
{
  "keys": [
    {
      "kty": "RSA",
      "use": "sig",
      "alg": "RS256",
      "kid": "yesod-auth-key-1",
      "n": "...",
      "e": "AQAB"
    }
  ]
}
```

### OpenID設定

```bash
GET /.well-known/openid-configuration
```

**レスポンス:**

```json
{
  "issuer": "http://localhost:8000",
  "jwks_uri": "http://localhost:8000/.well-known/jwks.json",
  "id_token_signing_alg_values_supported": ["RS256"],
  "subject_types_supported": ["public"],
  "response_types_supported": ["code", "token", "id_token"]
}
```

### ID Token

OIDC非対応プロバイダーでログイン時、レスポンスに`id_token`が含まれます：

```json
{
  "access_token": "...",
  "refresh_token": "...",
  "id_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6Inllc29kLWF1dGgta2V5LTEifQ..."
}
```

**ID Tokenのクレーム:**

| クレーム | 説明 |
|---------|------|
| `iss` | 発行者（YESOD AuthのURL） |
| `sub` | ユーザーID |
| `aud` | オーディエンス（クライアントID） |
| `exp` | 有効期限 |
| `iat` | 発行日時 |
| `provider` | OAuthプロバイダー名 |
| `email` | メールアドレス（取得可能な場合） |
| `name` | 表示名（取得可能な場合） |
| `picture` | アバターURL（取得可能な場合） |

!!! info "ID Token生成対象プロバイダー"
    GitHub, Discord, X, Facebook, TwitchでログインするとID Tokenが生成されます。
    Google, LinkedIn, SlackはネイティブでOIDCをサポートしているため、プロバイダーからのID Tokenがそのまま使用されます。
