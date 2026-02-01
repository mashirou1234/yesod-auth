# Webhook API

## 管理エンドポイント

| メソッド | パス | 説明 |
|---------|------|------|
| GET | `/api/v1/admin/webhooks/endpoints` | エンドポイント一覧 |
| GET | `/api/v1/admin/webhooks/deliveries` | 配信履歴 |
| POST | `/api/v1/admin/webhooks/reload` | 設定リロード |

---

## エンドポイント一覧

```bash
GET /api/v1/admin/webhooks/endpoints
```

**レスポンス:**

```json
[
  {
    "id": "my-service",
    "url": "https://example.com/webhooks",
    "events": ["user.created", "user.deleted"],
    "enabled": true,
    "description": "外部サービス連携"
  }
]
```

---

## 配信履歴

```bash
GET /api/v1/admin/webhooks/deliveries
```

**レスポンス:**

```json
[
  {
    "id": "delivery-uuid",
    "event_id": "event-uuid",
    "event_type": "user.created",
    "endpoint_id": "my-service",
    "endpoint_url": "https://example.com/webhooks",
    "status": "success",
    "http_status": 200,
    "error_message": null,
    "attempt_count": 1,
    "latency_ms": 150,
    "created_at": "2026-01-01T00:00:00Z",
    "completed_at": "2026-01-01T00:00:00Z"
  }
]
```

---

## 設定リロード

設定ファイルを変更した後、再起動なしで反映：

```bash
POST /api/v1/admin/webhooks/reload
```

**レスポンス:**

```json
{
  "status": "reloaded",
  "endpoints_count": 2
}
```

---

## イベントタイプ

| イベント | 説明 | データ |
|---------|------|--------|
| `user.created` | ユーザー作成 | user_id, provider, email |
| `user.updated` | プロフィール更新 | user_id, changes |
| `user.deleted` | アカウント削除 | user_id, email |
| `user.login` | ログイン | user_id, provider |
| `user.oauth_linked` | OAuth連携 | user_id, provider |
| `user.oauth_unlinked` | OAuth連携解除 | user_id, provider |

詳細な設定方法は[Webhook設定ガイド](../guides/webhooks.md)を参照してください。
