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

## OAuth callback監視チェック

セルフホスト運用では、`/api/v1/auth/{provider}/callback` の失敗を「発生後に調査」ではなく「定期監視で先に検知」する運用を推奨します。

### 監視項目（最小3点）

1. callback 失敗ログ件数（`invalid_client` / `Invalid state`）
2. callback URL への 4xx/5xx 応答の増加
3. callback 処理遅延（認証開始から callback 完了まで）が急増していないこと

### 日次確認コマンド（例）

```bash
docker compose logs --since=24h api | rg -n "/api/v1/auth/.*/callback|invalid_client|Invalid state" || true
```

### しきい値の目安（初期値）

- 直近24時間で `invalid_client` が 1 件以上: provider secret の不整合を疑い、即時確認
- 直近24時間で `Invalid state` が 3 件以上: callback 二重実行やセッション保持不安定を疑い、調査開始

`Invalid state` の切り分け手順は `docs/help/troubleshooting.md` の `state mismatch 診断フロー` を参照してください。プロバイダー設定の前提は `docs/guides/oauth/index.md` の `セルフホスト運用チェックリスト` と合わせて確認します。

## OAuthシークレットローテーション手順

プロバイダー個別の管理画面差分（Google/Discord など）に依存しない、共通の切替手順です。Compose/ECS/Kubernetes いずれでも「シークレット更新」「API再起動（または再デプロイ）」「疎通確認」の順序は共通です。

### ロールバック発動条件（先に判定）

次のいずれかに該当した場合は、新シークレットの調査を継続せず、先にロールバックへ移行します。

1. `invalid_client` / `401` が切替直後から継続し、認証開始を再実行しても解消しない
2. provider 管理画面の callback URL と実運用 URL（`/api/v1/auth/{provider}/callback`）が一致しない
3. API 再起動後に secret 読み込みエラーまたは OAuth 初期化失敗が発生する
4. `/health` が期待値 `200` に戻らない

### 運用前提の整合チェック（必須）

本番切替前に、次の3点を必ず同時に確認してください。

1. `MOCK_OAUTH_ENABLED` の本番値が `0` であること
   - 既定値は `0` ですが、`docker-compose.yml` の profile によって開発向け上書きが入るため、実行プロファイルごとに確認します
   ```bash
   docker compose --profile default config | rg -n "MOCK_OAUTH_ENABLED"
   docker compose --profile full config | rg -n "MOCK_OAUTH_ENABLED"
   ```
2. 対象 provider の secret が最新値へ反映済みであること（`*_client_id` / `*_client_secret`）
3. provider 管理画面の callback URL と実際の `/api/v1/auth/{provider}/callback` が一致していること

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

実行順は必ず固定し、途中で確認項目を飛ばさないでください。

1. **旧シークレットへ即時切り戻し**（更新前バックアップを復元）
2. **API を再起動/再デプロイ** して旧シークレットを再読込
3. **疎通確認を実施**（`curl https://api.your-domain.com/health` と `/api/v1/auth/{provider}`）
4. **callback URL 一致を再確認**（provider 管理画面と実運用 URL）

ロールバック後の追加確認は「ロールバック時の最小確認項目」を参照してください。

### 受け入れ基準（運用レビュー）

ローテーション失敗時の手順変更をレビューする場合は、次を満たしていることを受け入れ条件とします。

1. ロールバック条件と実行順が明文化されている
2. `MOCK_OAUTH_ENABLED` / provider secrets / callback URL の確認項目が含まれている
3. FAQ / installation / troubleshooting の三点同期チェックが記載されている

### docs 三点同期チェック（運用記録用）

ローテーション手順を更新した場合は、次の3ドキュメントと導線が一致していることをレビュー記録に残してください。

- `docs/help/faq.md`
- `docs/installation.md`
- `docs/help/troubleshooting.md`

最小確認コマンド:

```bash
rg -n "MOCK_OAUTH_ENABLED|secret|callback|ローテーション" \
  docs/guides/deployment.md docs/help/faq.md docs/installation.md docs/help/troubleshooting.md
```

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
5. OAuth認証開始エンドポイントが到達可能である（最低1 provider）
   ```bash
   curl -I https://api.your-domain.com/api/v1/auth/google
   # 期待値: 302 or 307
   ```

障害の切り分けが必要な場合は、`docs/help/troubleshooting.md` の認証・起動時エラー項目を参照してください。

### ロールバック記録テンプレート（運用ログ最小項目）

ロールバック完了後は、次の4項目を運用ログに残してください。  
OSS 配布時の問い合わせ切り分けと、セルフホスト環境での再発防止を最短化できます。

1. 実施時刻（UTC/JST）と対象デプロイID（または commit SHA）
2. どの確認項目で失敗を検知したか（上記 1〜5）
3. ロールバック後の確認結果（`/health` の HTTP ステータスとログ抽出コマンド結果）
4. provider 設定差分の有無（`client_id` / `client_secret` / callback URL）

## ログ保全設定例

長期運用では「保持期間」「ローテーション」「収集先」を先に決めておくと、障害調査と監査の再現性が上がります。

### 保全ポリシーの最小テンプレート

| 種別 | 推奨保持期間（初期値） | ローテーション | 主な用途 |
| --- | --- | --- | --- |
| API / Admin コンテナ標準出力 | 7日 | Docker `json-file` (`max-size=10m`, `max-file=7`) | 直近障害の一次切り分け |
| 監査・運用ログ（ホスト永続） | 14日 | `logrotate` 日次 (`rotate 14`) | 監査証跡、問い合わせ対応 |

> 監査要件がある環境では、保持期間を法令・社内規程に合わせて延長してください。

### Docker ログドライバ（json-file）でローテーション

`compose.prod.yml` など本番用オーバーレイに次の設定を置くと、起動プロファイルを変えても設定差分を追跡しやすくなります。

```yaml
services:
  api:
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "7"
  admin:
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

### 反映後の確認コマンド（例）

```bash
# Docker logging 設定が反映されているか確認
docker inspect yesod-api --format '{{json .HostConfig.LogConfig}}'
docker inspect yesod-admin --format '{{json .HostConfig.LogConfig}}'

# logrotate 設定の構文と適用対象を確認
sudo logrotate -d /etc/logrotate.d/yesod-auth
```

## バックアップ

PostgreSQLのバックアップ：

```bash
docker exec yesod-db pg_dump -U yesod_user yesod > backup.sql
```
