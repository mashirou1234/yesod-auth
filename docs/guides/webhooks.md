# Webhook機能

YESOD Authは、ユーザーイベント発生時に外部サービスへHTTP通知を送信するWebhook機能を提供します。

## 概要

以下のユーザーイベントでWebhookが発火します：

| イベント | 説明 |
|---------|------|
| `user.created` | 新規ユーザー登録時 |
| `user.updated` | プロフィール更新時 |
| `user.deleted` | アカウント削除時 |
| `user.login` | ログイン時 |
| `user.oauth_linked` | OAuthプロバイダー連携時 |
| `user.oauth_unlinked` | OAuthプロバイダー連携解除時 |

## クイック導入（5分）

まず最短で動作確認したい場合は、[クイックスタートの Webhook 導線](../getting-started.md#5-webhook導入の最短導線) からこの節へ到達し、次の 3 手順だけ実行してください。

1. `config/webhooks.yaml` に webhook.site の URL を設定する
2. `docker compose --profile default up -d` で API を起動する
3. Mock OAuth ログインを 1 回実行し、webhook.site で配信を確認する

```bash
curl "http://localhost:8000/api/v1/auth/mock/login?user=alice&provider=google"
```

詳細設定（署名検証、リトライ調整、鍵ローテーション）はこのページの各節を順に参照してください。

## セットアップ

### 1. 設定ファイルの作成

`config/webhooks.yaml`を作成します：

```yaml
endpoints:
  - id: "my-service"
    url: "https://your-service.example.com/webhooks/yesod"
    secret: "${WEBHOOK_SECRET_MY_SERVICE}"
    events:
      - "user.created"
      - "user.deleted"
    enabled: true
    description: "外部サービス連携"

settings:
  max_retries: 5
  retry_base_delay_seconds: 2
  retry_max_delay_seconds: 60
  # 任意: 再送バックオフを明示する場合は非負・単調増加（ms）
  retry_backoff_ms: [500, 1000, 2000]
  delivery_timeout_seconds: 30
```

### 2. シークレットの設定

#### 本番環境（Docker Secrets推奨）

```bash
# シークレットファイルを作成
echo "your-webhook-secret" > secrets/webhook_secret_my_service.txt

# docker-compose.ymlにシークレットを追加
secrets:
  webhook_secret_my_service:
    file: ./secrets/webhook_secret_my_service.txt
```

#### 開発環境（環境変数）

```bash
export WEBHOOK_SECRET_MY_SERVICE="your-webhook-secret"
```

> ⚠️ 環境変数を使用すると起動時に警告が表示されます。本番環境ではDocker Secretsを使用してください。

### 3. Docker Composeの設定

`config/`ディレクトリがマウントされていることを確認：

```yaml
api:
  volumes:
    - ./config:/app/config:ro
```

## ペイロード形式

Webhookは以下の形式でPOSTリクエストを送信します：

### ヘッダー

| ヘッダー | 説明 |
|---------|------|
| `Content-Type` | `application/json` |
| `X-Webhook-ID` | エンドポイントID |
| `X-Webhook-Event` | イベントタイプ |
| `X-Webhook-Timestamp` | UNIXタイムスタンプ |
| `X-Webhook-Signature` | HMAC-SHA256署名 |

### ボディ

```json
{
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "event_type": "user.created",
  "timestamp": "2026-02-01T10:00:00.000000+00:00",
  "data": {
    "user_id": "123e4567-e89b-12d3-a456-426614174000",
    "provider": "google",
    "email": "user@example.com"
  },
  "webhook_id": "my-service"
}
```

## 署名検証

受信側でリクエストの正当性を検証するには、署名を確認します：

### Python

```python
import hmac
import hashlib

def verify_signature(payload: bytes, secret: str, timestamp: str, signature: str) -> bool:
    message = f"{timestamp}.{payload.decode()}"
    expected = hmac.new(
        secret.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)
```

### Node.js

```javascript
const crypto = require('crypto');

function verifySignature(payload, secret, timestamp, signature) {
  const message = `${timestamp}.${payload}`;
  const expected = crypto
    .createHmac('sha256', secret)
    .update(message)
    .digest('hex');
  return signature === `sha256=${expected}`;
}
```

## 署名検証失敗時の調査順

`X-Webhook-Signature` が一致しない場合は、以下の順で原因を切り分けます。

1. 受信側が参照しているシークレットと `config/webhooks.yaml` のシークレット参照先が一致しているか確認する。
2. `X-Webhook-Timestamp` と生のリクエストボディ（JSON再シリアライズ前）で検証しているか確認する。
3. 受信側の実装で `timestamp + "." + raw_body` の形式を使っているか確認する。
4. API 側で配信失敗ログを確認し、対象 endpoint とイベントを特定する。
5. 必要に応じて設定を再読み込みし、同じイベントを再送して再検証する。

```bash
# API側のWebhook失敗ログを確認
docker compose logs api --since=30m | rg "webhook|signature|delivery"

# 現在のWebhook設定を確認
curl http://localhost:8000/api/v1/admin/webhooks/endpoints

# 設定変更後の再読み込み
curl -X POST http://localhost:8000/api/v1/admin/webhooks/reload
```

詳細な障害対応は [トラブルシューティング](../help/troubleshooting.md#署名検証に失敗する) も参照してください。

## 署名鍵ローテーション最小手順

`api/app/webhooks/signer.py` のとおり、送信署名は常に単一シークレットで生成されます。切替時は受信側を先に更新し、失敗時は旧鍵へ戻してください。

1. 新しい署名鍵を作成し、受信側を「新旧どちらの鍵でも検証可能」な状態にしてからデプロイする。
2. `secrets/webhook_secret_<endpoint>.txt`（または `WEBHOOK_SECRET_<endpoint>`）を新しい鍵へ更新し、`config/webhooks.yaml` の参照先が変わっていないことを確認する。
3. `POST /api/v1/admin/webhooks/reload` を実行して設定を再読み込みし、テストイベントを1件送って受信側検証が通ることを確認する。
4. 確認完了後、受信側の旧鍵受け入れ期間を終了し、運用鍵を新鍵に一本化する。

### 切替失敗時の戻し手順

1. 失敗を検知したら、シークレット値を旧鍵へ戻す。
2. `POST /api/v1/admin/webhooks/reload` を再実行して旧鍵へ復帰する。
3. 配信履歴（`GET /api/v1/admin/webhooks/deliveries`）と受信側ログで `hmac_mismatch` が解消したことを確認する。
4. 原因（鍵配布遅延、参照先違い、時刻ずれなど）を修正してから再度ローテーションを実施する。

### 署名検証失敗時の監査ログ項目

署名検証に失敗した場合は、再現性のある調査のために最低限以下を記録してください。

| 項目 | 例 | 用途 |
|------|----|------|
| `event_type` | `webhook.signature_verification_failed` | 監査イベント種別の統一 |
| `verified_at` | `2026-03-05T08:55:12Z` | 発生時刻の特定 |
| `webhook_id` | `my-service` | 対象エンドポイントの特定 |
| `x_webhook_event` | `user.login` | 通知イベント種別の特定 |
| `x_webhook_timestamp` | `1730787312` | リプレイ判定と時刻ずれ調査 |
| `signature_prefix` | `sha256` | 署名方式の判定 |
| `payload_sha256` | `8d1f...` | 本文改ざん有無の比較用（本文は生保存しない） |
| `failure_reason` | `hmac_mismatch` | 失敗理由の分類 |
| `source_ip` | `203.0.113.10` | 送信元調査 |
| `request_id` | `req-7f9d...` | アプリログとの突合 |

`failure_reason` は次のように固定値化しておくと運用しやすくなります。

- `missing_signature_header`
- `missing_timestamp_header`
- `timestamp_skew`
- `invalid_signature_format`
- `unsupported_signature_algorithm`
- `hmac_mismatch`
- `replay_detected`

!!! warning "記録しない情報"
    共有シークレット、平文の署名値、受信ペイロード全文（PII を含む可能性）は監査ログへ保存しないでください。

## リトライ動作

配信失敗時は指数バックオフでリトライします：

- 1回目リトライ: 2秒後
- 2回目リトライ: 4秒後
- 3回目リトライ: 8秒後
- 4回目リトライ: 16秒後
- 5回目リトライ: 32秒後

HTTP 4xx エラーはリトライしません（クライアントエラーのため）。

### 再試行設定の調整早見表

`config/webhooks.yaml` の `settings` は、まず下表の初期値から開始し、配信履歴と受信側負荷を見ながら1項目ずつ調整します。

| 設定キー | 推奨初期値 | 値を上げる判断 | 値を下げる判断 |
|---------|------------|----------------|----------------|
| `max_retries` | `5` | 受信側の瞬断が数分単位で起こり、最終成功率を優先したい | 失敗イベントの陳腐化を避けたい、重複通知コストを抑えたい |
| `retry_base_delay_seconds` | `2` | 受信側が過負荷で 429/タイムアウトを返し、初回再送を遅らせたい | 一時失敗の復旧が速く、早期再送で成功率を上げたい |
| `retry_max_delay_seconds` | `60` | 長時間障害時の再送スパイクを抑えたい | 障害復旧後の反映遅延を短くしたい |
| `delivery_timeout_seconds` | `30` | 外部サービス応答が遅く、成功応答まで待機が必要 | ハング検知を早め、ワーカー詰まりを防ぎたい |

調整の基本手順:
1. `GET /api/v1/admin/webhooks/deliveries` で失敗率と復旧までの時間を確認する。
2. 1回の変更で1項目だけ更新し、`POST /api/v1/admin/webhooks/reload` 後に30分以上観測する。
3. 失敗率・遅延・重複受信のどれを最適化するかを先に決め、目的に対応する設定だけ変更する。

### 配信失敗時のログ確認項目

再試行設定の見直し前に、最低でも次の項目を同一 `request_id` 単位で確認してください。

| 項目 | 例 | 見るポイント |
|------|----|--------------|
| `webhook_id` | `my-service` | どの送信先だけ失敗しているか |
| `event_type` | `user.deleted` | 特定イベントに偏りがないか |
| `status_code` | `429` / `500` / `timeout` | 受信側負荷か送信側障害かの切り分け |
| `attempt` | `3/5` | 何回目で失敗しているか（上限到達の有無） |
| `next_retry_at` | `2026-03-14T10:15:30Z` | バックオフが期待どおり計算されているか |
| `request_id` | `req-7f9d...` | APIログ・受信側ログを突合できるか |

```bash
# 直近30分の webhook 関連ログを確認
docker compose logs api --since=30m | rg "webhook|delivery|retry|timeout|request_id"
```

詳細な切り分け手順は [トラブルシューティング: Webhook](../help/troubleshooting.md#webhook) を参照してください。

## 管理API

### エンドポイント一覧

```bash
curl http://localhost:8000/api/v1/admin/webhooks/endpoints
```

### 配信履歴

```bash
curl http://localhost:8000/api/v1/admin/webhooks/deliveries
```

### 設定リロード

```bash
curl -X POST http://localhost:8000/api/v1/admin/webhooks/reload
```

## ローカルテスト

[webhook.site](https://webhook.site)を使用してローカルでテストできます：

1. webhook.siteにアクセスしてURLを取得
2. `config/webhooks.yaml`を作成：

```yaml
endpoints:
  - id: "test-webhook"
    url: "https://webhook.site/your-unique-url"
    secret: "test-secret"
    events:
      - "user.created"
      - "user.login"
    enabled: true
```

3. Docker Composeを起動：

```bash
docker compose --profile default up -d
```

4. Mock OAuthでログイン：

```bash
curl "http://localhost:8000/api/v1/auth/mock/login?user=alice&provider=google"
```

5. webhook.siteでリクエストを確認
