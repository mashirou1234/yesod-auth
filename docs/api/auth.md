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

## エラーコード早見表（refresh/logout）

`api/app/auth/router.py` の実装定義に合わせた運用向け一覧です。

### POST `/api/v1/auth/refresh`

| HTTP | 条件 | 原因の目安 | 対処の目安 |
|------|------|-----------|-----------|
| 200 | リフレッシュ成功 | トークンローテーション成功 | 新しい `access_token` / `refresh_token` を保存 |
| 401 | `Invalid or expired refresh token` | 期限切れ・失効済み・改ざん | 再ログインして新しいトークンを取得 |
| 401 | `User not found` | 紐づくユーザーが削除済み | セッションを破棄して再認証 |
| 422 | リクエスト検証エラー | `refresh_token` 未指定/型不正 | JSON ボディ形式を修正 |
| 429 | レート制限超過 | `/refresh` の短時間連続呼び出し | 間隔を空けて再試行（バックオフ推奨） |

### POST `/api/v1/auth/logout`

| HTTP | 条件 | 原因の目安 | 対処の目安 |
|------|------|-----------|-----------|
| 200 | ログアウト成功 | リフレッシュトークン失効処理成功 | クライアント側トークンを削除 |
| 401 | 認証失敗 | `Authorization` ヘッダ欠落/無効 | 有効な Bearer トークンで再実行 |
| 422 | リクエスト検証エラー | `refresh_token` 未指定/型不正 | JSON ボディ形式を修正 |

### OAuth callback 共通（参考）

| HTTP | 条件 | 原因の目安 | 対処の目安 |
|------|------|-----------|-----------|
| 400 | `Invalid or expired state` | state 不一致/期限切れ | 認証フローを最初から再実行 |
| 400 | `Failed to exchange code` | 認可コード交換失敗 | provider 設定・redirect URI を確認 |
| 400 | `Failed to get user info` | provider API 取得失敗 | provider 側障害・スコープ設定を確認 |
| 429 | レート制限超過 | callback/API 連打 | 一定時間待って再試行 |

!!! tip "維持ルール"
    ルータ変更時は `api/app/auth/router.py` の `HTTPException` と `@limiter.limit(...)` を更新し、本表も同時に更新してください。

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
