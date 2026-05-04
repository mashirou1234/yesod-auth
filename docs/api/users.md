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
  "http://localhost:8000/api/v1/sessions?limit=1" | jq '.sessions | length'

# 実運用でよく使う上限確認（100件）
curl -sS -H "Authorization: Bearer ${TOKEN}" \
  "http://localhost:8000/api/v1/sessions?limit=100" | jq '.sessions | length'
```

確認観点:

1. どちらも `200 OK` で返る
2. `.sessions | length` が指定した `limit` を超えない
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

### 実行前の最小チェック（更新系共通）

更新系を実行する直前に、同じトークンで `GET /api/v1/users/me` が `200 OK` で返ることを確認してください。  
この確認が失敗する場合、`PATCH` / `DELETE` も同様に失敗します。

```bash
TOKEN="<access_token>"
curl -sS -o /tmp/users-me.json -w "%{http_code}\n" \
  -H "Authorization: Bearer ${TOKEN}" \
  http://localhost:8000/api/v1/users/me
```

更新系で想定される主な失敗条件:

- `401 Unauthorized`: Bearer トークン未指定・期限切れ・不正
- `422 Unprocessable Entity`: `PATCH` ボディの型不正や `max_length` 超過（`display_name` 255 文字、`avatar_url` 500 文字）

`DELETE` 成功後は、同じトークンで再度 `GET /api/v1/users/me` を呼ぶと `401` になることを確認してください。

## 認証・認可エラー例

`/api/v1/users/me` 系エンドポイントは Bearer トークン必須です。  
トークン未指定・期限切れ・不正トークン時は `401 Unauthorized` を返します。

```json
{
  "detail": {
    "code": "missing_bearer_token",
    "message": "Not authenticated"
  }
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

**成功レスポンス (`200 OK`)**

```json
{
  "message": "Account scheduled for deletion. Will be permanently removed after 30 days.",
  "deleted_user_id": "550e8400-e29b-41d4-a716-446655440000",
  "deleted_email": "user@example.com",
  "scheduled_delete_at": "2026-01-31T00:00:00Z"
}
```

`scheduled_delete_at` は UTC で、永続削除予定時刻を示します。

!!! note "Webhookイベント"
    アカウント削除時に`user.deleted`イベントが発火します。

---

## プロバイダ情報からプロフィール復元

```bash
POST /api/v1/users/me/sync-from-provider?provider=google
Authorization: Bearer <access_token>
```

**前提条件**

1. `provider` は `google` または `discord` のみ指定可能
2. 指定した `provider` の OAuth 連携が、実行ユーザーに紐づいていること
3. `provider_display_name` / `provider_avatar_url` のいずれかが保存済みであること

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

**入力不正 (`400 Bad Request`: 未対応 provider)**

```bash
POST /api/v1/users/me/sync-from-provider?provider=github
Authorization: Bearer <access_token>
```

```json
{
  "detail": "Unsupported provider"
}
```

**未連携 (`404 Not Found`)**

```bash
POST /api/v1/users/me/sync-from-provider?provider=discord
Authorization: Bearer <access_token>
```

```json
{
  "detail": "No discord account linked"
}
```

**保存情報なし (`400 Bad Request`)**

指定した provider は連携済みでも、保存済みプロフィール情報がない場合は `400` を返します。

```json
{
  "detail": "No provider info stored for google. Try re-logging in with google."
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

### sync-from-provider 失敗マトリクス（運用向け）

`POST /api/v1/users/me/sync-from-provider` の失敗時は、まず次の表で `400` と `404` を切り分けてください。

| ステータス | 代表メッセージ | 何が起きているか | 最初の対処 | 次に見る場所 |
| --- | --- | --- | --- | --- |
| `400` | `Unsupported provider` | `provider` が対応外（`google` / `discord` 以外） | `provider` クエリを `google` か `discord` に修正 | [FAQ: sync-from-provider の 400/404 は何を意味する？](../help/faq.md#sync-from-provider-の-400404-は何を意味する) |
| `404` | `No <provider> account linked` | 指定 provider の OAuth 連携が未作成 | 対象 provider で再ログインし、連携作成後に再実行 | [トラブルシューティング: sync-from-provider で 400/404 が返る](../help/troubleshooting.md#sync-from-provider-errors) |
| `400` | `No provider info stored for <provider>...` | 連携はあるが保存済みプロフィール情報が空 | 同 provider で再ログインし、プロフィール情報を再取得 | [トラブルシューティング: sync-from-provider で 400/404 が返る](../help/troubleshooting.md#sync-from-provider-errors) |

!!! note "対応 provider の範囲"
    `sync-from-provider` の `provider` は現時点で `google` / `discord` のみ対応です。

!!! tip "三点同期の確認導線"
    FAQ は [sync-from-provider の 400/404 の意味](../help/faq.md#sync-from-provider-の-400404-は何を意味する)、
    障害対応は [sync-from-provider で 400/404 が返る](../help/troubleshooting.md#sync-from-provider-errors)、
    provider 未設定時の初動は [インストール: provider 未設定時の最短スキップ手順](../installation.md#provider-未設定時の最短スキップ手順) を参照してください。

運用で記録する場合は、`provider`、HTTP ステータス、代表メッセージ、再ログイン有無を 1 セットにしてください。`400 Unsupported provider` は入力修正、`404 No <provider> account linked` は再ログイン、`400 No provider info stored` は同一 provider でプロフィール再取得、という順で処理します。
