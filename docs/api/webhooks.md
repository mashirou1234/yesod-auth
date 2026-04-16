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

### 冪等性の注意点（再送時）

- 同一イベントの再送では、`event_id` は同じ値のまま `attempt_count` だけ増加します。
- `id`（delivery レコードID）や `attempt_count` は再送ごとに変わるため、冪等キーとして使わないでください。
- 受信側は `event_id`（必要に応じて `endpoint_id` も併用）を冪等キーにして重複処理を防止してください。
- タイムアウトや 5xx の場合は再送が発生するため、同一 `event_id` の処理は再実行しても結果が変わらない実装を推奨します。

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

### 署名鍵ローテーション時の利用

- `config/webhooks.yaml` が参照するシークレット値を切り替えた直後に `POST /api/v1/admin/webhooks/reload` を実行してください。
- 切替後に署名検証失敗が増えた場合は、旧鍵へ戻して再度 `reload` することで復旧できます。
- 詳細手順は [Webhook設定ガイドの署名鍵ローテーション最小手順](../guides/webhooks.md#署名鍵ローテーション最小手順) を参照してください。

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
- 非推奨キー: 配信履歴の `id` や `attempt_count`（再送で変わるため）
- 管理用途: `X-Webhook-ID` と `X-Webhook-Event` を監査ログに残す
- 保持期間: 少なくとも Webhook 再送が起こり得る期間（運用で定義したリトライ期間）以上

### 最小再現手順（ローカル）

1. 受信側で `event_id` の処理履歴を保存するログを有効化する
2. 同じペイロード（同じ `event_id`）を2回送信する
3. 1回目のみ業務処理が実行され、2回目は重複としてスキップされることを確認する

詳細な設定方法は[Webhook設定ガイド](../guides/webhooks.md)を参照してください。

---

## 再試行上限到達時の監査ログ

Webhook 配信が再試行上限に到達した場合、ワーカーは固定キー
`webhook_delivery_retry_exhausted` を含むエラーログを出力します。

最低限、次の key-value を確認してください。

- `attempts`: 実際に試行した回数
- `max_attempts`: 設定上の最大試行回数
- `failure_reason`: 失敗理由（HTTP エラー本文または `Request timeout` など）
- `http_status`: HTTP ステータス（取得できない場合は `None`）
- `endpoint_id` / `event_id`: 影響範囲の追跡キー

---

## 署名検証エラー分類

受信側の署名検証では、以下の `failure_reason` を固定値として扱うことを推奨します。

| failure_reason | 説明 |
|------|------|
| `missing_signature_header` | `X-Webhook-Signature` ヘッダーがない |
| `missing_timestamp_header` | `X-Webhook-Timestamp` ヘッダーがない |
| `timestamp_skew` | 許容時刻差を超過している |
| `invalid_signature_format` | `algorithm=digest` 形式でない |
| `unsupported_signature_algorithm` | 未対応の署名方式が指定された（例: `sha1`） |
| `hmac_mismatch` | 署名がペイロードと一致しない |
| `replay_detected` | リプレイ攻撃が疑われる |

アプリ内の `WebhookSigner.verify_or_raise()` を使う場合は、例外分類は次の 2 つに丸められます。

| code | 説明 |
|------|------|
| `missing_signature_header` | `X-Webhook-Signature` ヘッダが欠落または空 |
| `invalid_signature` | 署名検証に失敗した |

`invalid_signature` 例外メッセージは、調査ログの構造を一定にするため次の key-value 形式を含みます。

- `error_code=<failure_reason>`（例: `hmac_mismatch`, `unsupported_signature_algorithm`）
- `signature_algorithm=<algorithm>`（例: `sha256`, `sha1`）

### 署名検証失敗時の最小調査フロー

`invalid_signature` または `hmac_mismatch` が連続する場合は、次の順で切り分けると最短で原因に到達できます。

1. 直近 30 分の API ログから `webhook` / `signature` を抽出し、失敗が特定 endpoint のみかを確認する
2. 送信側の署名鍵と、`config/webhooks.yaml` が参照する受信側シークレットが同一値かを確認する
3. 鍵を更新した直後であれば `POST /api/v1/admin/webhooks/reload` を実行し、同一イベントを再送して結果を比較する
4. 改善しない場合は旧鍵へ一時ロールバックし、`reload` 後に成功可否を確認して鍵不一致か実装差異かを判定する

詳細なログ確認コマンドと復旧パターンは [トラブルシューティングの「署名検証に失敗する」](../help/troubleshooting.md#署名検証に失敗する) を参照してください。
調査時に最低限確認する監査ログ項目（`event_type`, `failure_reason`, `webhook_id`, `x_webhook_event`, `request_id`）は、
[Webhook設定ガイド: 署名検証失敗時の監査ログ項目](../guides/webhooks.md#署名検証失敗時の監査ログ項目) を参照してください。
