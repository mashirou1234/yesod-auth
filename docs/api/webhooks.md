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

---

## Webhook再送時の重複受信対策

配信先のタイムアウトや一時的な `5xx` により、同一イベントが再送されることがあります。  
受信側では `event_id` を冪等キーとして扱い、**同じ `event_id` は1回だけ処理**してください。

### 推奨フロー

1. 受信時に `event_id` を抽出する
2. `event_id` が未処理なら処理を実行して処理済みとして保存する
3. `event_id` が処理済みなら副作用を実行せず `200 OK` を返す

### 実装メモ

- 冪等キー: JSON ボディの `event_id`
- 管理用途: `X-Webhook-ID` と `X-Webhook-Event` を監査ログに残す
- 保持期間: 少なくとも Webhook 再送が起こり得る期間（運用で定義したリトライ期間）以上

### 最小再現手順（ローカル）

1. 受信側で `event_id` の処理履歴を保存するログを有効化する
2. 同じペイロード（同じ `event_id`）を2回送信する
3. 1回目のみ業務処理が実行され、2回目は重複としてスキップされることを確認する

詳細な設定方法は[Webhook設定ガイド](../guides/webhooks.md)を参照してください。
