# インストール

## システム要件

| 要件 | バージョン |
|------|-----------|
| Docker | 20.10+ |
| Docker Compose | 2.0+ |

障害時の確認手順は[トラブルシューティング: 障害時の参照順](help/troubleshooting.md#障害時の参照順最短導線)を参照してください。

## Docker Composeプロファイル

YESOD Authは3つのプロファイルを提供しています：

| プロファイル | 用途 | サービス |
|-------------|------|---------|
| `default` | ローカル開発 | db, api, docs (`valkey` は常時有効) |
| `full` | 管理画面含む | db, api, admin, docs (`valkey` は常時有効) |
| `ci` | CI/CD | db-ci, api-ci (`valkey` は常時有効) |

### 開発環境

```bash
docker compose --profile default up -d
```

### 管理画面付き

```bash
docker compose --profile full up -d
```

管理画面は http://localhost:8501 でアクセスできます。

### CI相当

```bash
docker compose --profile ci up -d
```

## docker compose利用時の最小確認手順

`docker compose --profile default up -d` 実行後、次の3項目だけ確認すれば最小動作確認が完了します。

1. コンテナ状態の確認

```bash
docker compose --profile default ps
```

期待値:
- `api`, `db`, `docs`, `valkey` が `Up`（または `running`）

2. API ヘルスチェック確認

```bash
curl -fsS http://localhost:8000/health
```

期待値:
- HTTP 200 が返る

3. API ドキュメント到達確認

```bash
curl -fsS -o /dev/null -w '%{http_code}\n' http://localhost:8000/docs
```

期待値:
- `200`

終了時は次のコマンドで後片付けできます。

```bash
docker compose --profile default down
```

## profile整合確認手順

`docker-compose.yml` と本ドキュメントの profile 記載が一致していることを、変更時に必ず確認してください。

1. Compose定義上の profile 一覧を確認する

```bash
docker compose config --profiles
```

期待値:

```text
ci
default
full
```

2. profile ごとのサービス対応を確認する（`docker-compose.yml` を根拠に照合）

```bash
docker compose --profile default config --services
docker compose --profile full config --services
docker compose --profile ci config --services
```

3. 起動コマンド例が `default` / `full` / `ci` の3つをすべて網羅していることを確認する

```bash
rg -n "docker compose --profile (default|full|ci) up -d" docs/installation.md
```

## 初回導入で起きやすい失敗パターン

初回セットアップ時に発生しやすい失敗を、症状ごとの確認順でまとめます。

### 1. `docker compose up` で secret 未設定エラーになる

症状例:

- `Error: secret ... not found`
- API コンテナが `CreateContainerConfigError` で起動しない

確認:

```bash
ls -1 secrets | head
ls -1 secrets/*.txt 2>/dev/null | wc -l
```

対処:

1. `secrets/*.example` から必要な `.txt` を作成する
2. 最低限 `jwt_secret.txt` は必ず作成する
3. 有効化するOAuthプロバイダー分の client id/secret を作成する

### 2. `default` 以外で起動して Mock OAuth が使えない

症状例:

- `/api/v1/auth/mock/login` が想定どおり動作しない
- 初回確認で外部OAuth設定まで要求される

確認:

```bash
docker compose --profile default config --services
docker compose --profile full config --services
```

対処:

1. 初回動作確認は `docker compose --profile default up -d` を使う
2. `full` は管理画面込みの確認時に切り替える
3. `ci` はローカル初回導入用途では使わない

### 3. 8000/5432/6379 が使用中で起動失敗する

症状例:

- `Bind for 0.0.0.0:8000 failed: port is already allocated`
- 一部サービスだけ `Exited` になる

確認:

```bash
docker compose ps
lsof -nP -iTCP:8000 -iTCP:5432 -iTCP:6379 -sTCP:LISTEN
```

対処:

1. 競合プロセスや既存コンテナを停止する
2. 必要なら `docker compose down` 後に再起動する
3. 競合が解消しない場合は `.env` 側のポート割当を見直す

### 4. 古いコンテナ状態が残って挙動が不安定になる

症状例:

- 設定変更後も以前の挙動のまま
- `healthy` にならない

確認:

```bash
docker compose ps
docker compose logs --tail=100 api
```

対処:

```bash
docker compose down
docker compose up -d --build
```

## 環境変数

| 変数名 | 説明 | デフォルト |
|--------|------|-----------|
| `DATABASE_URL` | PostgreSQL接続URL | - |
| `VALKEY_URL` | Valkey接続URL | - |
| `CORS_ORIGINS` | 許可するオリジン | - |
| `FRONTEND_URL` | フロントエンドURL | - |
| `MOCK_OAUTH_ENABLED` | Mock OAuth有効化（アプリ既定値は`0`。`docker compose --profile default`/`ci`ではCompose側で`1`に上書き） | `0` |
| `ACCESS_TOKEN_LIFETIME_SECONDS` | アクセストークン有効期限 | `900` |
| `REFRESH_TOKEN_LIFETIME_DAYS` | リフレッシュトークン有効期限 | `7` |

`CORS_ORIGINS` が未設定または空文字の場合、API起動時に警告ログを出し、開発用デフォルト値（`http://localhost:3000,http://localhost:5173`）で起動します。

### 環境変数・Secrets の優先順位

設定元が複数ある場合は、以下の優先順位で値が決まります。

| 対象 | 優先順位（高 → 低） | 根拠 |
|------|----------------------|------|
| OAuthクライアントID/Secret、`JWT_SECRET` | `/run/secrets/<name>` → 同名の環境変数（大文字）→ 既定値 | `api/app/config.py` の `read_secret()` |
| `DATABASE_URL` / `VALKEY_URL` / `CORS_ORIGINS` / `FRONTEND_URL` など | 環境変数 → 既定値 | `api/app/config.py` の `os.getenv()` |
| `MOCK_OAUTH_ENABLED`（`default`/`ci`プロファイル） | Compose の service `environment` での指定（`1`）→ アプリ既定値（`0`） | `docker-compose.yml` と `api/app/config.py` |

`read_secret()` の優先順は `api/tests/test_config.py` でテストされています（secret file 優先、次に環境変数、最後に既定値）。

### 管理画面用環境変数

| 変数名 | 説明 | デフォルト |
|--------|------|-----------|
| `ADMIN_USER` | 管理者ユーザー名 | `admin` |
| `SESSION_EXPIRY_HOURS` | セッション有効期限（時間） | `24` |
| `DEFAULT_LANGUAGE` | デフォルト言語（en, ja, fr, ko, de） | `en` |

## OAuth認証情報

Docker Secretsまたは環境変数で設定：

初回導入時は、設定後に [初回導入チェックリスト](getting-started.md#初回導入チェックリスト) を順に実行して動作確認してください。

| シークレット名 | 説明 |
|---------------|------|
| `google_client_id` | Google OAuth Client ID |
| `google_client_secret` | Google OAuth Client Secret |
| `github_client_id` | GitHub OAuth Client ID |
| `github_client_secret` | GitHub OAuth Client Secret |
| `discord_client_id` | Discord OAuth Client ID |
| `discord_client_secret` | Discord OAuth Client Secret |
| `x_client_id` | X (Twitter) OAuth Client ID |
| `x_client_secret` | X (Twitter) OAuth Client Secret |
| `linkedin_client_id` | LinkedIn OAuth Client ID |
| `linkedin_client_secret` | LinkedIn OAuth Client Secret |
| `facebook_client_id` | Facebook OAuth Client ID (App ID) |
| `facebook_client_secret` | Facebook OAuth Client Secret (App Secret) |
| `slack_client_id` | Slack OAuth Client ID |
| `slack_client_secret` | Slack OAuth Client Secret |
| `twitch_client_id` | Twitch OAuth Client ID |
| `twitch_client_secret` | Twitch OAuth Client Secret |
| `jwt_secret` | JWT署名用シークレット |

## ポート

| サービス | ポート |
|---------|-------|
| API | 8000 |
| PostgreSQL | 5432 |
| Valkey | 6379 |
| Admin | 8501 |

## 初回起動で詰まった場合

`docker compose --profile default up -d` 実行後の確認順（`/health`、`/docs`、必須 secrets）は
[初回起動トラブルシュート](help/first-start-troubleshooting.md) を参照してください。
