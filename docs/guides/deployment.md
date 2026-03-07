# デプロイ

## 本番環境の準備

### 1. 環境変数の設定

```bash
# 本番用の環境変数
export DATABASE_URL=postgresql+asyncpg://user:password@db-host:5432/yesod
export VALKEY_URL=redis://valkey-host:6379/0
export CORS_ORIGINS=https://your-frontend.com
export FRONTEND_URL=https://your-frontend.com
export MOCK_OAUTH_ENABLED=0  # 本番では無効化
```

### 2. シークレットの管理

本番環境ではDocker Secretsを使用してください：

```bash
# Docker Swarmモードの場合
echo "your-jwt-secret" | docker secret create jwt_secret -
echo "your-google-client-id" | docker secret create google_client_id -
# ...
```

### 3. OAuthリダイレクトURIの更新

使用する各OAuthプロバイダーの管理画面で、リダイレクトURIを本番ドメインへ更新：

```
https://api.your-domain.com/api/v1/auth/{provider}/callback
```

代表例:

- `https://api.your-domain.com/api/v1/auth/google/callback`
- `https://api.your-domain.com/api/v1/auth/github/callback`
- `https://api.your-domain.com/api/v1/auth/discord/callback`
- `https://api.your-domain.com/api/v1/auth/x/callback`

---

## デプロイオプション

### Docker Compose（単一サーバー）

```bash
docker compose --profile default up -d
```

### AWS ECS

1. ECRにイメージをプッシュ
2. ECSタスク定義を作成
3. ECSサービスをデプロイ

### Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: yesod-auth
spec:
  replicas: 2
  selector:
    matchLabels:
      app: yesod-auth
  template:
    metadata:
      labels:
        app: yesod-auth
    spec:
      containers:
      - name: api
        image: your-registry/yesod-auth:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: yesod-secrets
              key: database-url
```

---

## ヘルスチェック

```bash
curl https://api.your-domain.com/health
```

## ログ監視

```bash
docker compose logs -f api
```

## OAuthシークレットローテーション手順

プロバイダー個別の管理画面差分（Google/Discord など）に依存しない、共通の切替手順です。Compose/ECS/Kubernetes いずれでも「シークレット更新」「API再起動（または再デプロイ）」「疎通確認」の順序は共通です。

### 切替前チェック

- redirect URI が現在の本番ドメインを向いていることを確認する
  - 例: `https://api.your-domain.com/api/v1/auth/google/callback`
  - 例: `https://api.your-domain.com/api/v1/auth/discord/callback`
- 新旧シークレットを同時に参照できる退避手順を準備する（即時ロールバック用）
- 反映対象（Compose の secret / ECS task definition / K8s Secret）を運用手順書に明記する
- 反映前にヘルスチェックの現状値を取得する
  ```bash
  curl -sS -o /dev/null -w "%{http_code}\n" https://api.your-domain.com/health
  # 期待値: 200
  ```

### 切替実施

1. 対象環境へ新しい OAuth client secret を反映する
2. API プロセスを再起動または再デプロイして新シークレットを読み込ませる
3. 起動ログで secret 読み込み失敗や OAuth 初期化失敗がないことを確認する
   ```bash
   docker compose logs --since=10m api | rg -n "secret|oauth|ERROR|FATAL" || true
   ```

### 切替後検証

1. ヘルスチェックが成功すること
   ```bash
   curl -sS -o /dev/null -w "%{http_code}\n" https://api.your-domain.com/health
   # 期待値: 200
   ```
2. 認証開始エンドポイントに到達できること（`docs/api/auth.md` の仕様と整合）
   ```bash
   curl -I https://api.your-domain.com/api/v1/auth/google
   curl -I https://api.your-domain.com/api/v1/auth/discord
   ```
3. 認証コールバック URL が想定ドメインのままであること（`/api/v1/auth/{provider}/callback`）

### 失敗時のロールバック（最小3ステップ）

1. 旧シークレットへ即時切り戻し（更新前バックアップを復元）
2. API を再起動/再デプロイして旧シークレットを再読込
3. `curl https://api.your-domain.com/health` と `/api/v1/auth/{provider}` への到達を再確認

ロールバック後の追加確認は「ロールバック時の最小確認項目」を参照してください。

## ロールバック時の最小確認項目
デプロイ直後に不具合が発生してロールバックした場合は、次の最小確認を順に実施してください。

1. 稼働コンテナがロールバック対象の構成で起動している
   ```bash
   docker compose ps
   ```
2. APIヘルスチェックが成功する
   ```bash
   curl -sS -o /dev/null -w "%{http_code}\n" https://api.your-domain.com/health
   # 期待値: 200
   ```
3. 直近ログに致命的な起動失敗がない
   ```bash
   docker compose logs --since=10m api | rg -n "ERROR|Traceback|FATAL" || true
   ```
4. OAuthコールバックURLが意図した環境を向いている
   - `https://api.your-domain.com/api/v1/auth/google/callback`
   - `https://api.your-domain.com/api/v1/auth/discord/callback`

障害の切り分けが必要な場合は、`docs/help/troubleshooting.md` の認証・起動時エラー項目を参照してください。

## ログ保全設定例

長期運用では「保持期間」「ローテーション」「収集先」を先に決めておくと、障害調査と監査の再現性が上がります。

### Docker ログドライバ（json-file）でローテーション

```yaml
services:
  api:
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "7"
```

`max-size` と `max-file` を設定すると、単一コンテナのログ肥大化を防げます。Compose 本番設定（例: `compose.prod.yml`）に分離して管理する運用を推奨します。

### ホスト側 logrotate で永続ログを保全

```conf
/var/log/yesod-auth/*.log {
  daily
  rotate 14
  compress
  delaycompress
  missingok
  notifempty
  copytruncate
}
```

14日保持の例です。セキュリティ監査や法令対応が必要な環境では、保持日数を要件に合わせて調整してください。

## バックアップ

PostgreSQLのバックアップ：

```bash
docker exec yesod-db pg_dump -U yesod_user yesod > backup.sql
```
