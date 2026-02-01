# ユーザーAPI

## エンドポイント一覧

| メソッド | パス | 説明 |
|---------|------|------|
| GET | `/api/v1/users/me` | 現在のユーザー情報 |
| PATCH | `/api/v1/users/me` | プロフィール更新 |
| DELETE | `/api/v1/users/me` | アカウント削除 |

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
