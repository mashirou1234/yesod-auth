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

## リトライ動作

配信失敗時は指数バックオフでリトライします：

- 1回目リトライ: 2秒後
- 2回目リトライ: 4秒後
- 3回目リトライ: 8秒後
- 4回目リトライ: 16秒後
- 5回目リトライ: 32秒後

HTTP 4xx エラーはリトライしません（クライアントエラーのため）。

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
