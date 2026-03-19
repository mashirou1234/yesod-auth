# ユーザーAPI

## エンドポイント一覧

| メソッド | パス | 説明 |
|---------|------|------|
| GET | `/api/v1/users/me` | 現在のユーザー情報 |
| PATCH | `/api/v1/users/me` | プロフィール更新 |
| DELETE | `/api/v1/users/me` | アカウント削除 |
| POST | `/api/v1/users/me/sync-from-provider?provider=<name>` | OAuth プロバイダ情報からプロフィール復元 |

---

## ページング境界値（`limit=1/100`）の検証例

`/api/v1/users/me` 自体はページング対象ではありません。  
ただし、ユーザー認証後の一覧系確認を同一トークンで実施する場合は、`/api/v1/sessions` の `limit` 境界値をあわせて確認できます。

```bash
# 前提: OAuthログイン済みトークンを利用
TOKEN="<access_token>"

# 最小件数境界
curl -sS -H "Authorization: Bearer ${TOKEN}" \
  "http://localhost:8000/api/v1/sessions?limit=1" | jq '.items | length'

# 実運用でよく使う上限確認（100件）
curl -sS -H "Authorization: Bearer ${TOKEN}" \
  "http://localhost:8000/api/v1/sessions?limit=100" | jq '.items | length'
```

確認観点:

1. どちらも `200 OK` で返る
2. `.items | length` が指定した `limit` を超えない
3. 同一トークンで `GET /api/v1/users/me` も継続して成功する

上限超過時（`limit > 1000`）は `400 Bad Request` を返し、専用エラーコードと上限値を本文に含みます。

```json
{
  "detail": {
    "code": "SESSIONS_LIMIT_EXCEEDED",
    "message": "limit must be less than or equal to 1000",
    "max_limit": 1000
  }
}
```

!!! tip "切り分け導線"
    `limit=1/100` で期待どおりにならない場合は、[トラブルシューティングの確認手順](../help/troubleshooting.md#users-pagination-limit-check) を参照してください。

---

## 更新系エンドポイントの前提条件

`PATCH /api/v1/users/me` と `DELETE /api/v1/users/me` を呼び出す前に、次を満たしてください。

1. OAuthログイン後に取得した有効なアクセストークンを `Authorization: Bearer <access_token>` で付与する
2. `PATCH` のリクエストボディは `Content-Type: application/json` で送る
3. `PATCH` で更新できる項目は `display_name`（最大255文字）と `avatar_url`（最大500文字）のみ
4. `PATCH` は指定した項目だけ更新され、`null` を送るとその項目をクリアする
5. `DELETE` 実行後のアカウントはソフトデリート状態になり、同一トークンでの継続利用はできない

!!! tip "トークン未取得時"
    先に [認証API](./auth.md) の OAuth フローでアクセストークンを取得してください。

## 認証・認可エラー例

`/api/v1/users/me` 系エンドポイントは Bearer トークン必須です。  
トークン未指定・期限切れ・不正トークン時は `401 Unauthorized` を返します。

```json
{
  "detail": "Not authenticated"
}
```

```json
{
  "detail": "Invalid or expired token"
}
```

!!! tip "確認の目安"
    `Authorization` ヘッダーを外して `GET /api/v1/users/me` を実行すると、
    上記いずれかの `401` レスポンスを再現できます。

---

## 現在のユーザー情報

```bash
GET /api/v1/users/me
Authorization: Bearer <access_token>
```

**レスポンス:**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "user@example.com",
  "display_name": "User Name",
  "avatar_url": "https://example.com/avatar.png",
  "created_at": "2026-01-01T00:00:00Z",
  "oauth_accounts": [
    {
      "provider": "google",
      "provider_email": "user@gmail.com"
    }
  ]
}
```

---

## プロフィール更新

```bash
PATCH /api/v1/users/me
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "display_name": "New Name",
  "avatar_url": "https://example.com/new-avatar.png"
}
```

!!! note "Webhookイベント"
    プロフィール更新時に`user.updated`イベントが発火します。

---

## アカウント削除

```bash
DELETE /api/v1/users/me
Authorization: Bearer <access_token>
```

!!! warning "注意"
    この操作は取り消せません。関連するすべてのデータが削除されます。

!!! note "Webhookイベント"
    アカウント削除時に`user.deleted`イベントが発火します。

---

## プロバイダ情報からプロフィール復元

```bash
POST /api/v1/users/me/sync-from-provider?provider=google
Authorization: Bearer <access_token>
```

**成功レスポンス (`200 OK`)**

```json
{
  "message": "Profile synced from google",
  "provider": "google",
  "updated_fields": ["display_name", "avatar_url"],
  "display_name": "Provider User",
  "avatar_url": "https://example.com/provider-user.png"
}
```

**競合レスポンス (`409 Conflict`)**

ローカルのプロフィール値とプロバイダ保持値が衝突する場合は、`detail.code` と `detail.message` を固定した契約で返します。

```json
{
  "detail": {
    "code": "SYNC_FROM_PROVIDER_CONFLICT",
    "message": "Local profile already has different values. Clear conflicting fields before syncing from provider.",
    "conflicting_fields": ["display_name", "avatar_url"]
  }
}
```
