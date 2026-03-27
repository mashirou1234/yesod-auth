# インストール

初回導入では、まず本ページで要件とプロファイル差分を確認し、その後に[クイックスタート](getting-started.md)を実行してください。
起動前後の最終確認は [クイックスタート: 初回導入チェックリスト](getting-started.md#初回導入チェックリスト) を基準に進めると、secret 不足や callback URL 不一致を早期に検出できます。
全体の読み進め順は [docs index: 導入者向け最短導線（3ステップ）](index.md#導入者向け最短導線3ステップ) を参照してください。

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

### profile選択チェック表

初回導入時は、用途に応じて次の表で profile を選択してください。実行前後に [profile整合確認手順](#profile整合確認手順) で定義との差分を確認すると安全です。

| profile | この条件なら選ぶ | 最小確認コマンド |
|---|---|---|
| `default` | ローカルで API/Docs を最短で確認したい | `docker compose --profile default up -d`<br>`docker compose --profile default ps`<br>`curl -fsS http://localhost:8000/health` |
| `full` | 管理画面 (`admin`) まで含めて導入確認したい | `ls -l secrets/admin_password.txt`<br>`docker compose --profile full up -d`<br>`docker compose --profile full config --services` |
| `ci` | CI 相当の軽量構成だけ確認したい | `docker compose --profile ci up -d`<br>`docker compose --profile ci config --services`<br>`docker compose --profile ci ps` |

### provider 未設定時の最短スキップ手順

OAuth provider をまだ一部用意できていない場合は、次の手順で初回確認を進めます。

1. `default` profile で起動し、Mock OAuth で疎通確認する
2. 必須 secret は `jwt_secret` と、今回有効化する provider 分だけ作成する
3. 未設定 provider は `GET /api/v1/auth/<provider>` を呼ばず、先に health/docs 到達確認を完了する
4. OAuth 設定完了後に provider の secret を追加し、`docker compose --profile default up -d --force-recreate api` で再開する

再開ポイント:
- 起動確認の継続: [docker compose利用時の最小確認手順](#docker-compose利用時の最小確認手順)
- 実 OAuth の再開: [クイックスタート: Mock OAuthから実OAuthへ切り替える最小チェック](./getting-started.md#mock-oauthから実oauthへ切り替える最小チェック)
- 失敗時: [トラブルシューティング: provider 未設定のまま認証導線を実行した](./help/troubleshooting.md#provider-未設定のまま認証導線を実行した)
- FAQ での要点確認: [Mock OAuthから実OAuthへ切り替える最小確認は？](./help/faq.md#mock-oauthから実oauthへ切り替える最小確認は)

## Docker起動前チェック項目

`docker compose up` 実行前に、次の4項目を確認してください。

1. Docker Engine / Docker Compose のバージョン確認

```bash
docker --version
docker compose version
```

期待値:
- Docker 20.10 以上
- Docker Compose 2.0 以上

2. 必須 secret ファイルの存在確認

```bash
ls -1 secrets/jwt_secret.txt
```

必要に応じて、有効化する OAuth プロバイダーの `secrets/*.txt` も追加してください。

3. 主要ポートの競合確認（8000 / 5432 / 6379）

```bash
lsof -nP -iTCP:8000 -iTCP:5432 -iTCP:6379 -sTCP:LISTEN
```

競合がある場合は既存プロセスまたは既存コンテナを停止してから起動します。

4. 初回確認で使用する profile の決定

- 初回導入確認: `default`
- 管理画面確認まで行う場合: `full`
- CI相当確認のみ: `ci`

### 開発環境

```bash
docker compose --profile default up -d
```

### 管理画面付き

`full` プロファイルは「設定」「起動」「確認」の順で実施してください。
profile 差分の前提は [profile選択チェック表](#profile選択チェック表) で先に確認してください。

#### 1. 設定

1. 管理画面向けシークレットを用意する（必須・空ファイル禁止）

```bash
ls -l secrets/admin_password.txt
test -s secrets/admin_password.txt && echo "admin_password: OK" || (echo "admin_password が未作成または空です" >&2; exit 1)
```

2. 管理画面向け環境変数の確認観点

- `ADMIN_USER`: 管理者ログイン名。既定値は `admin`（`docker-compose.yml` で設定）
- `SESSION_EXPIRY_HOURS`: 管理画面セッション期限（時間）。未指定時はアプリ既定値 `24`

#### 2. 起動

```bash
docker compose --profile full up -d
```

#### 3. 確認

1. `full` で必要サービスが起動対象に含まれること

```bash
docker compose --profile full config --services
```

期待値（順不同）: `db`, `api`, `admin`, `docs`, `valkey`

2. 管理画面到達確認

- URL: http://localhost:8501
- `ADMIN_USER` と `secrets/admin_password.txt` の値でログインできること

3. セッション設定確認（任意）

- ログイン後、指定した `SESSION_EXPIRY_HOURS` が運用要件に合うことを確認する

#### 代表的な失敗例

- 症状: `admin` サービスが起動失敗する / ログインできない
- 原因例: `secrets/admin_password.txt` 未作成、空ファイル、または想定外の値
- 対処: `secrets/admin_password.txt` を作成・更新し、`test -s secrets/admin_password.txt` で非空を確認してから `docker compose --profile full up -d` を再実行

#### 受け入れ基準チェックリスト（full profile / admin_password）

1. `full` プロファイル手順に `admin_password` の非空チェック（`test -s`）が含まれている
2. 未設定時の症状（起動失敗/ログイン失敗）と復旧手順が同じ節に記載されている
3. FAQ / installation / troubleshooting の3点同期を確認できる  
   - FAQ: [どのsecretを必須で用意すべき？](./help/faq.md#どのsecretを必須で用意すべき)  
   - Installation: [管理画面付き](#管理画面付き)  
   - Troubleshooting: [認証エラー](./help/troubleshooting.md#認証エラー)

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

診断:

```bash
docker compose --profile default up -d 2>&1 | rg -n "secret .* not found|CreateContainerConfigError"
```

出力された `secret <name> not found` の `<name>` が不足している必須secretです。

次に、`default` プロファイルで要求されるsecretと手元の `.txt` を照合します。

```bash
printf '%s\n' google_client_id google_client_secret discord_client_id discord_client_secret jwt_secret
ls -1 secrets/*.txt 2>/dev/null | sed -E 's#^.*/##; s#\\.txt$##' | sort
```

最短復旧コマンド（secret不足）:

```bash
# 1) まず不足している secret 名を抽出
MISSING="$(docker compose --profile default up -d 2>&1 \
  | rg -o 'secret [a-z0-9_]+ not found' \
  | sed -E 's/^secret ([a-z0-9_]+) not found$/\\1/' \
  | sort -u)"

# 2) 不足分だけ secrets/<name>.txt を補完（雛形があればコピー）
for name in $MISSING; do
  [ -f "secrets/${name}.txt" ] || cp "secrets/${name}.txt.example" "secrets/${name}.txt"
done

# 3) jwt_secret は必須。未作成なら生成して再起動
[ -s secrets/jwt_secret.txt ] || openssl rand -hex 32 > secrets/jwt_secret.txt
docker compose --profile default up -d --force-recreate api
docker compose --profile default ps
```

期待値:
- `docker compose --profile default ps` で `api` が `Up`（または `running`）
- `secret ... not found` が再発しない

`invalid_client` が続く場合は、`secrets/*.txt` の値が実値であることを確認し、[`docs/help/troubleshooting.md` の `invalid_client` 手順](help/troubleshooting.md#invalid_client-or-401-from-provider-token-endpoint) を参照してください。

### OAuth secret ファイル権限の復旧手順

`permission denied` で起動に失敗する場合は、次の順で復旧してください。

1. 症状確認
   ```bash
   docker compose logs --tail=100 api | rg -n "permission denied|/run/secrets"
   ```
2. 権限確認（Linux/macOS）
   ```bash
   # Linux
   stat -c '%n %a %U:%G' secrets/*.txt
   # macOS
   stat -f '%N %Lp %Su:%Sg' secrets/*.txt
   ```
3. 復旧
   ```bash
   chmod 600 secrets/*.txt
   sudo chown "$(id -un):$(id -gn)" secrets/*.txt
   docker compose up -d --force-recreate api worker
   ```

詳細な切り分けは [トラブルシューティング: secrets 権限不備で `Permission denied` が出る](./help/troubleshooting.md#secrets-permission-recovery) を参照してください。

対処:

1. 不足している `<name>` について、`secrets/<name>.txt` を作成する
2. `jwt_secret.txt` は必須として必ず作成する（例: `openssl rand -hex 32 > secrets/jwt_secret.txt`）
3. OAuthは `default` で最低限 `google_*` と `discord_*` が必要（`docker-compose.yml` の `api`/`api-ci` secrets 定義）
4. サンプル値が必要な場合は `secrets/*.example` を参照し、値を設定後に再起動する

```bash
docker compose --profile default up -d --force-recreate api
docker compose --profile default ps
```

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

<a id="environment-variables"></a>

### 区分付き一覧（必須 / 推奨 / 任意）

| 区分 | 変数/シークレット | 用途 | 未設定時の症状 | 既定値/補足 |
|------|-------------------|------|----------------|------------|
| 必須 | `DATABASE_URL` | PostgreSQL接続先 | API/管理画面がDB接続エラーで起動失敗、または意図しないDBへ接続 | 開発向け既定値あり。セルフホストでは明示設定推奨 |
| 必須 | `VALKEY_URL` | Valkey接続先（state/レート制御） | OAuthの`state mismatch`やセッション関連エラーが発生しやすくなる | 開発向け既定値あり。セルフホストでは明示設定推奨 |
| 必須 | `FRONTEND_URL` | OAuth完了後のリダイレクト先 | ログイン後の遷移先が不正になり、認証完了後のUXが壊れる | 既定値 `http://localhost:3000` |
| 必須 | `CORS_ORIGINS` | API許可オリジン | ブラウザから`CORS`エラーでAPI呼び出し失敗 | 既定値 `http://localhost:3000,http://localhost:5173` |
| 必須 | `jwt_secret` | JWT署名鍵 | トークン検証不整合や`401`が発生。既定値運用はセキュリティ上非推奨 | Docker Secret推奨（`secrets/jwt_secret.txt`） |
| 必須 | `<provider>_client_id` / `<provider>_client_secret` | OAuth provider資格情報 | 該当providerで`invalid_client`や認証失敗が発生 | 有効化して使うprovider分のみ必須 |
| 推奨 | `ACCESS_TOKEN_LIFETIME_SECONDS` | アクセストークン有効期限 | セキュリティポリシーに対して寿命が長すぎる/短すぎる状態になりやすい | `900` |
| 推奨 | `REFRESH_TOKEN_LIFETIME_DAYS` | リフレッシュトークン有効期限 | 再認証頻度と失効リスクのバランスが運用要件とずれる | `7` |
| 推奨 | `SESSION_EXPIRY_HOURS` | 管理画面セッション有効期限（時間） | 管理画面セッションが運用要件より長期化/短期化する | `24` |
| 任意 | `MOCK_OAUTH_ENABLED` | Mock OAuth有効化（アプリ既定値は`0`。`docker compose --profile default`/`ci`ではCompose側で`1`に上書き） | 期待したログイン経路（Mock/実OAuth）と実挙動がずれる | `0` |
| 任意 | `ADMIN_USER` | 管理者ユーザー名 | 管理画面ログイン時に想定と異なるユーザー名を参照して混乱が起きる | `admin` |
| 任意 | `DEFAULT_LANGUAGE` | 管理画面デフォルト言語（en, ja, fr, ko, de） | 管理画面の初期表示言語が運用想定と一致しない | `en` |

`CORS_ORIGINS` が未設定または空文字の場合、API起動時に警告ログを出し、開発用デフォルト値（`http://localhost:3000,http://localhost:5173`）で起動します。

### 設定チェック表（記入用）

| 項目 | 区分 | 設定値確認 | 未設定時症状の理解確認 |
|------|------|------------|------------------------|
| `DATABASE_URL` | 必須 | ☐ | ☐ |
| `VALKEY_URL` | 必須 | ☐ | ☐ |
| `FRONTEND_URL` | 必須 | ☐ | ☐ |
| `CORS_ORIGINS` | 必須 | ☐ | ☐ |
| `jwt_secret` | 必須 | ☐ | ☐ |
| `<provider>_client_id` / `<provider>_client_secret` | 必須 | ☐ | ☐ |
| `ACCESS_TOKEN_LIFETIME_SECONDS` | 推奨 | ☐ | - |
| `REFRESH_TOKEN_LIFETIME_DAYS` | 推奨 | ☐ | - |
| `SESSION_EXPIRY_HOURS` | 推奨 | ☐ | - |
| `MOCK_OAUTH_ENABLED` | 任意 | ☐ | - |
| `ADMIN_USER` | 任意 | ☐ | - |
| `DEFAULT_LANGUAGE` | 任意 | ☐ | - |

### 環境変数・Secrets の優先順位

設定元が複数ある場合は、以下の優先順位で値が決まります。

| 対象 | 優先順位（高 → 低） | 根拠 |
|------|----------------------|------|
| OAuthクライアントID/Secret、`JWT_SECRET` | `/run/secrets/<name>` → 同名の環境変数（大文字）→ 既定値 | `api/app/config.py` の `read_secret()` |
| `DATABASE_URL` / `VALKEY_URL` / `CORS_ORIGINS` / `FRONTEND_URL` など | 環境変数 → 既定値 | `api/app/config.py` の `os.getenv()` |
| `MOCK_OAUTH_ENABLED`（`default`/`ci`プロファイル） | Compose の service `environment` での指定（`1`）→ アプリ既定値（`0`） | `docker-compose.yml` と `api/app/config.py` |

`read_secret()` の優先順は `api/tests/test_config.py` でテストされています（secret file 優先、次に環境変数、最後に既定値）。

### profile別の環境変数優先順位

`MOCK_OAUTH_ENABLED` はアプリ既定値 `0` ですが、Compose 運用では profile ごとに環境変数で上書きされます。  
本番誤設定を避けるため、profile 別に以下を固定値として扱ってください。

| profile | Compose上の期待値 | 実行時の期待値 | 根拠 |
| --- | --- | --- | --- |
| `default` | `MOCK_OAUTH_ENABLED=1` が `api.environment` に含まれる | `1`（Mock OAuth 有効） | `docker-compose.yml` (`api.profiles: default/full`) |
| `full` | `MOCK_OAUTH_ENABLED=1` が `api.environment` に含まれる | `1`（Mock OAuth 有効） | `docker-compose.yml` (`api.profiles: default/full`) |
| `ci` | `MOCK_OAUTH_ENABLED=1` が `api-ci.environment` に含まれる | `1`（Mock OAuth 有効） | `docker-compose.yml` (`api-ci.profiles: ci`) |

確認コマンド（default/full/ci の3点を毎回実施）:

```bash
docker compose --profile default config | rg -n "MOCK_OAUTH_ENABLED"
docker compose --profile full config | rg -n "MOCK_OAUTH_ENABLED"
docker compose --profile ci config | rg -n "MOCK_OAUTH_ENABLED"
```

判定:

- `default`/`full`/`ci` すべてで `MOCK_OAUTH_ENABLED=1` が見えること
- Compose を使わずアプリを単体起動する場合は既定値 `0` になること（`api/app/config.py`）

### 受け入れ基準チェックリスト（MOCK_OAUTH_ENABLED / profile差分）

1. 上記の profile 比較表で、アプリ既定値 `0` と Compose profile 上書き `1` を 1 表で確認できる
2. default/full/ci の `docker compose config` 実行結果で期待値に一致する
3. 利用する provider の secrets（`<provider>_client_id` / `<provider>_client_secret`）が揃っている
4. provider 管理画面の callback URL と `GET /api/v1/auth/{provider}/callback` が一致している
5. FAQ / installation / troubleshooting の3点同期を確認する  
   - FAQ: [OAuth secret の権限不備を最短で復旧するには？](./help/faq.md#oauth-secret-の権限不備を最短で復旧するには)  
   - Installation: [profile別の環境変数優先順位](#profile別の環境変数優先順位)  
   - Troubleshooting: [secrets 権限不備で `Permission denied` が出る](./help/troubleshooting.md#secrets-permission-recovery)

## リフレッシュトークン運用時の注意

`/api/v1/auth/refresh` は「アクセストークンの延命」ではなく「ローテーションを伴う再発行」です。導入時は次の3点を必ず満たしてください。

1. クライアントは refresh 応答で返る最新トークンに必ず置き換える（旧トークンの再利用を避ける）。
2. `REFRESH_TOKEN_LIFETIME_DAYS` を短縮する場合は、セッション再認証頻度が上がる前提で運用手順を見直す。
3. `401` が継続する場合は refresh ループを止め、再ログインにフォールバックする。

確認コマンド（最小再現）:

```bash
rg -n "REFRESH_TOKEN_LIFETIME_DAYS|/api/v1/auth/refresh|再ログイン" docs/installation.md README.md
```

関連ヘルプ:
- [トラブルシューティング（認証エラー）](./help/troubleshooting.md#認証エラー)
- [初回起動トラブルシュート](./help/first-start-troubleshooting.md)

## OAuth認証情報

<a id="oauth-credentials"></a>

Docker Secretsまたは環境変数で設定：

初回導入時は、設定後に [初回導入チェックリスト](getting-started.md#初回導入チェックリスト) を順に実行して動作確認してください。
provider別の対応表は [OAuth設定ハブの一覧](guides/oauth/index.md#provider別必須環境変数一覧) を参照してください。

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

!!! note "Compose運用時の注意"
    `docker-compose.yml` の既定では `api` / `api-ci` に `google_*` / `discord_*` / `jwt_secret` が定義されています。
    GitHub など他プロバイダーを利用する場合は、[OAuth設定ガイド](guides/oauth/index.md#セルフホスト向け最短手順) の
    override 例を使って対象 provider の `secrets` を追加してください。

## OAuth provider追加時の事前チェック

新しい OAuth provider を追加する前に、次の4点を確認してください。事前に差分を揃えることで、導入時の手戻りを減らせます。

1. 対応表と導線を更新する
   - `docs/guides/oauth/index.md` の provider 一覧へ追記する
   - `docs/index.md` の対応プロバイダー表示と導線を整合させる
2. 必要な secret 名を定義する
   - `secrets/<provider>_client_id.txt.example`
   - `secrets/<provider>_client_secret.txt.example`
   - `docker-compose.yml` の `api.secrets` に読み込み定義を追加する
3. callback URL の前提を確定する
   - provider 管理画面に登録する callback を `GET /api/v1/auth/{provider}/callback` で揃える
   - 開発環境と本番環境でホスト名・スキームが一致することを確認する
4. 最小動作確認を実行する
   - API 起動後に `GET /api/v1/auth/{provider}` へアクセスして認可開始できること
   - callback 後に `invalid_client` / `Invalid or expired state` が出ないこと

### 事前チェック実行コマンド

```bash
# 1) docs 導線の更新漏れ確認
rg -n "OAuth|プロバイダー|provider" docs/index.md docs/installation.md docs/getting-started.md docs/guides/oauth/index.md

# 2) 追加providerの secret 雛形確認（<provider> は実名に置換）
ls secrets/<provider>_client_id.txt.example secrets/<provider>_client_secret.txt.example

# 3) callback 前提の確認
rg -n "/api/v1/auth/\\{provider\\}/callback|invalid_client|Invalid or expired state" docs/guides/oauth/index.md docs/help/troubleshooting.md
```

### API認証トラブル時の確認順

1. このセクションのシークレットが有効化した provider 分そろっていることを確認する
2. [クイックスタート](getting-started.md#4-動作確認)で API 到達性を確認する
3. [トラブルシューティング: 障害時の参照順（最短導線）](help/troubleshooting.md#障害時の参照順最短導線) で `health -> auth -> provider -> webhook` の順に切り分ける
4. `auth` / `provider` で詰まった場合は [state mismatch](help/troubleshooting.md#state-mismatch-flow) と [`401 Unauthorized` / `invalid_client`](help/troubleshooting.md#401-unauthorized--invalid_client) を順に確認する

## セルフホスト向け秘密情報配置例

`docker-compose.yml` は `./secrets/*.txt` を参照します。セルフホスト環境では
「アプリ配置」と「秘密情報配置」を分離し、`./secrets` をシンボリックリンクで
接続するとローテーションしやすくなります。

```text
/opt/yesod-auth/
  app/        # このリポジトリを配置
  secrets/
    current/
      google_client_id.txt
      google_client_secret.txt
      discord_client_id.txt
      discord_client_secret.txt
      jwt_secret.txt
      admin_password.txt   # --profile full を使う場合のみ
```

作成例:

```bash
mkdir -p /opt/yesod-auth/secrets/current
cp secrets/*.example /opt/yesod-auth/secrets/current/
openssl rand -hex 32 > /opt/yesod-auth/secrets/current/jwt_secret.txt
openssl rand -base64 24 > /opt/yesod-auth/secrets/current/admin_password.txt
chmod 600 /opt/yesod-auth/secrets/current/*.txt

cd /opt/yesod-auth/app
ln -sfn ../secrets/current secrets
```

検証:

```bash
docker compose --profile default config >/dev/null
docker compose --profile full config >/dev/null
```

### secret/環境変数の解決優先順位

`api/app/config.py` の `read_secret` は、以下の優先順位で値を解決します（上位が優先）:

1. `/run/secrets/<name>`（Docker Secrets）
2. 環境変数 `<NAME_UPPERCASE>`
3. `read_secret(name, default)` の `default` 値

根拠:

- 実装: `api/app/config.py`
- テスト: `api/tests/test_config.py`

### 具体例1: Docker Secrets と環境変数が両方ある場合

`/run/secrets/github_client_secret` と `GITHUB_CLIENT_SECRET` の両方を設定した場合、`/run/secrets/github_client_secret` が使われます。

```bash
# 優先される値（Docker Secrets）
echo "secret-from-file" > /run/secrets/github_client_secret

# フォールバック値（このケースでは使われない）
export GITHUB_CLIENT_SECRET="secret-from-env"
```

### 具体例2: Docker Secrets がない場合

`/run/secrets/jwt_secret` がない場合は `JWT_SECRET` が使われ、環境変数もない場合はデフォルト値へフォールバックします。

```bash
# /run/secrets/jwt_secret が存在しない前提
export JWT_SECRET="jwt-from-env"
# -> read_secret("jwt_secret", "change-me-in-production") は jwt-from-env を返す

unset JWT_SECRET
# -> read_secret("jwt_secret", "change-me-in-production") は change-me-in-production を返す
```

### 開発/CIでの推奨設定

- 開発（`docker compose --profile default`）: `secrets/*.txt` を Compose の `secrets` 経由で渡し、環境変数はローカル確認用途に限定する。
- CI（`docker compose --profile ci`）: CIシークレットストアを使って `secrets` を生成・注入し、平文の環境変数直書きを避ける。
- 運用: 本番相当では Docker Secrets を第一候補にし、環境変数は一時的フォールバックとして扱う。

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
