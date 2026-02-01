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

Google Cloud Console / Discord Developer Portalで、リダイレクトURIを本番ドメインに更新：

```
https://api.your-domain.com/api/v1/auth/google/callback
https://api.your-domain.com/api/v1/auth/discord/callback
```

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

## バックアップ

PostgreSQLのバックアップ：

```bash
docker exec yesod-db pg_dump -U yesod_user yesod > backup.sql
```
