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

---

## 認可エラー方針（401 / 403）

認証・認可に関するステータスコードは次の方針で使い分けます。

| ステータス | 使う条件 | 代表例 |
| --- | --- | --- |
| `401 Unauthorized` | 認証情報がない、無効、期限切れ | `Authorization` ヘッダー未指定、無効トークン、期限切れトークン |
| `403 Forbidden` | 認証は成功しているが操作権限が不足 | 有効トークンだが管理者専用操作を実行した場合 |

`/api/v1/auth/logout` や `/api/v1/auth/refresh` でトークン検証に失敗した場合は `401` を返します。`403` は「誰かは特定できるが、その操作は許可しない」ケースで返します。

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

**未認証時のレスポンス:**

```json
{
  "detail": "Not authenticated"
}
```

ステータスコード: `401 Unauthorized`

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
