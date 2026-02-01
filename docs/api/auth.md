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
| POST | `/api/v1/auth/refresh` | トークンリフレッシュ |
| POST | `/api/v1/auth/logout` | ログアウト |

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

**利用可能なプロバイダー:** `google`, `github`, `discord`, `x`, `linkedin`

### ユーザー一覧

```bash
GET /api/v1/auth/mock/users
```
