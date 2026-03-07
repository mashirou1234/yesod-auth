# 認証API

## エンドポイント一覧

| メソッド | パス | 説明 |
|---------|------|------|
| GET | `/api/v1/auth/google` | Google OAuth開始 |
| GET | `/api/v1/auth/google/callback` | Googleコールバック |
| GET | `/api/v1/auth/github` | GitHub OAuth開始（organization所属の制限判定は未実装） |
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

### OAuth provider が無効な場合

対象: `GET /api/v1/auth/{provider}`（google / github / discord / x / linkedin / facebook / slack / twitch）

- 条件: 対象 provider の `*_CLIENT_ID` または `*_CLIENT_SECRET` が未設定
- 応答: `503 Service Unavailable`
- 例:

```json
{
  "detail": "OAuth provider 'google' is disabled. Configure GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET."
}
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

### refresh失敗時エラー分類

`POST /api/v1/auth/refresh` で失敗した場合は、まずレスポンスコードと API ログを突き合わせて次の表で分類します。

| 症状 | APIレスポンス/ログ例 | 主な原因 | 初動対応 |
| --- | --- | --- | --- |
| トークン欠落・形式不正 | `422 Unprocessable Entity` / `refresh_token` の入力エラー | リクエストボディが欠落、JSONキー名の誤り | 送信 payload を `{ "refresh_token": "..." }` に統一して再試行 |
| 期限切れ・改ざん・失効済み | `401 Unauthorized` / `Could not validate credentials` | refresh token の期限切れ、署名不一致、logout/revoke 済み | 再ログインして新しい token pair を払い出し、古い token を破棄 |
| サーバー設定不整合 | `401 Unauthorized` が継続し複数ユーザーで再現 | `JWT_SECRET` 差し替え、環境差分、ローテーション手順漏れ | 稼働中コンテナの secret 読み込み元を確認し、全ノードの設定を揃える |
| 一時的な基盤障害 | `500 Internal Server Error` / DB・Valkey 接続失敗ログ | DB/Valkey 疎通不安定、依存サービス瞬断 | `docker compose ps` と各サービスログを確認し復旧後に再試行 |

詳細な切り分け手順は [`トラブルシューティング > 認証エラー`](../help/troubleshooting.md#認証エラー) を参照してください。

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
