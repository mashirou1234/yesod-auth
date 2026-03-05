# ユーザーAPI

## エンドポイント一覧

| メソッド | パス | 説明 |
|---------|------|------|
| GET | `/api/v1/users/me` | 現在のユーザー情報 |
| PATCH | `/api/v1/users/me` | プロフィール更新 |
| DELETE | `/api/v1/users/me` | アカウント削除 |

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
