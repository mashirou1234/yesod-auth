# クイックスタート

このガイドでは、YESOD Authを5分でセットアップする方法を説明します。

!!! info "先に確認すると安全な項目"
    Docker要件や `default` / `full` / `ci` の違いは[インストール](installation.md)に整理しています。初回導入時は先に確認してください。
    導入順で迷った場合は [docs index: 導入者向け最短導線（3ステップ）](index.md#導入者向け最短導線3ステップ) を起点に進めてください。

## 前提条件

- Docker & Docker Compose
- 利用するOAuth providerの開発者アカウント（Google/Discord/GitHubなど）

## 1. リポジトリのクローン

```bash
git clone https://github.com/mashirou1234/yesod-auth.git
cd yesod-auth
```

## 2. シークレットファイルの作成

```bash
# サンプルファイルをコピー
cp secrets/google_client_id.txt.example secrets/google_client_id.txt
cp secrets/google_client_secret.txt.example secrets/google_client_secret.txt
cp secrets/discord_client_id.txt.example secrets/discord_client_id.txt
cp secrets/discord_client_secret.txt.example secrets/discord_client_secret.txt
cp secrets/jwt_secret.txt.example secrets/jwt_secret.txt
```

各ファイルを編集して、OAuthプロバイダーから取得したクレデンシャルを設定します。

providerごとの必須 secret 名は [OAuth設定ハブの一覧](guides/oauth/index.md#provider別必須環境変数一覧) を参照してください。

!!! tip "provider追加時は先にチェック"
    新しい OAuth provider を追加する場合は、先に [OAuth provider追加時の事前チェック](installation.md#oauth-provider追加時の事前チェック) を実施してから secrets を作成してください。

!!! tip "JWTシークレットの生成"
    ```bash
    openssl rand -base64 32 > secrets/jwt_secret.txt
    ```

### provider 未設定時の最短スキップ手順

未設定の provider がある場合でも、初回起動確認は中断せずに進められます。

1. 起動対象を `default` profile に固定する（Mock OAuth 前提）
2. 必須 secret は `jwt_secret` と、今回有効化する provider 分だけ作成する
3. 未設定 provider は触らず、[3. 起動](#3-起動) と [4. 動作確認](#4-動作確認) まで先に完了させる
4. 実 OAuth を使うタイミングで、対象 provider の `*_client_id` / `*_client_secret` を追加して再起動する

再開ポイント:
- 起動確認を先に進める場合は [4. 動作確認](#4-動作確認)
- 実 OAuth を再開する場合は [Mock OAuthから実OAuthへ切り替える最小チェック](#mock-oauthから実oauthへ切り替える最小チェック)
- 失敗時の切り分けは [トラブルシューティング](help/troubleshooting.md#provider-未設定のまま認証導線を実行した) を参照

### FAQ / installation / troubleshooting 同期チェックコマンド

```bash
rg -n "provider 未設定時の最短スキップ手順|再開ポイント" \
  docs/getting-started.md docs/installation.md docs/help/faq.md docs/help/troubleshooting.md
```

### OAuthガイドへの導線

クイックスタートで起動確認した後、利用するプロバイダーの設定を進めてください。

- [OAuth設定ハブ](guides/oauth/index.md)
- [Google OAuth ガイド](guides/oauth/google.md)
- [Discord OAuth ガイド](guides/oauth/discord.md)
- [GitHub OAuth ガイド](guides/oauth/github.md)

## 2.5 `redirect_uri_mismatch` の最短確認（5ステップ）

OAuth 導入時は、実装前に「provider 管理画面の callback URL」と「YESOD Auth が受ける URL」が一致することをこの手順だけで確認します。

### 基本ルール

- 形式は `https://<api-domain>/api/v1/auth/<provider>/callback`
- `http` はローカル開発以外で使わない
- 末尾スラッシュを付けない（`.../callback/` は不可）
- `provider` は実際に有効化したものだけ登録する

### 最短確認手順（5ステップ）

1. 公開 API URL を固定する（例: `https://api.example.com`）
2. callback URL を組み立てる（例: `https://api.example.com/api/v1/auth/google/callback`）
3. provider 管理画面の callback 設定値と、[認証APIの callback パス仕様](api/auth.md#callback-url-spec) が一致することを確認する
4. リバースプロキシ利用時は `X-Forwarded-Proto=https` が API へ渡ることを確認する
5. ログインを1回実行し、`redirect_uri_mismatch` または `Invalid or expired state` が出ないことを確認する

失敗時は次の順で参照してください。

- `redirect_uri_mismatch` / `invalid_client`: [トラブルシューティング: 401 Unauthorized / invalid_client](help/troubleshooting.md#401-unauthorized--invalid_client)
- `Invalid or expired state`: [トラブルシューティング: state mismatch 診断フロー](help/troubleshooting.md#state-mismatch-flow)
- profile や secret 前提の再確認: [インストール](installation.md#oauth認証情報)

### FAQ / installation / troubleshooting 同期チェック（受け入れ基準）

- [FAQ の実OAuth切替手順](help/faq.md#mock-oauthから実oauthへ切り替える最小確認は) にある callback 確認手順と矛盾がない
- [インストールの OAuth 認証情報](installation.md#oauth認証情報) と callback 前提（URL 形式・provider 単位）が一致している
- [トラブルシューティング](help/troubleshooting.md#認証エラー) への参照導線が残っている

## 3. 起動

```bash
docker compose --profile default up -d
```

`default`プロファイルでは、Compose設定により`MOCK_OAUTH_ENABLED=1`がAPIサービスへ適用されます（アプリ既定値は`0`）。

### Compose profile差分の確認

起動前に、利用するプロファイルで有効になるサービス差分を確認できます。

```bash
# default: ローカル開発用（db / valkey / api / docs）
docker compose --profile default config --services

# full: 管理画面込み（db / valkey / admin / api / docs）
docker compose --profile full config --services

# ci: テスト用の軽量構成（db-ci / valkey / api-ci）
docker compose --profile ci config --services
```

`MOCK_OAUTH_ENABLED` の適用差分は次で確認できます。

```bash
docker compose --profile default config | rg "MOCK_OAUTH_ENABLED|api:"
docker compose --profile ci config | rg "MOCK_OAUTH_ENABLED|api-ci:"
```

### profile別の初回確認コマンド表

初回導入では、使う profile を1つ決めてから次の表の順で実行すると、確認漏れを防げます。

| profile | 使う場面 | 初回確認コマンド（順番どおり） | 合格基準 |
| --- | --- | --- | --- |
| `default` | API と Docs の最短導入確認 | `docker compose --profile default up -d`<br>`docker compose --profile default ps`<br>`curl -fsS http://localhost:8000/health` | `db` `valkey` `api` `docs` が `Up`、`{"status":"healthy"}` が返る |
| `full` | 管理画面 (`admin`) を含めて確認 | `ls -l secrets/admin_password.txt`<br>`docker compose --profile full up -d`<br>`docker compose --profile full config --services` | `secrets/admin_password.txt` が存在し、`admin` が services 一覧に出る |
| `ci` | CI相当の軽量構成で確認 | `docker compose --profile ci up -d`<br>`docker compose --profile ci config --services`<br>`docker compose --profile ci ps` | `db-ci` `valkey` `api-ci` が起動し、不要な `admin` が含まれない |

詳細な profile 判定観点は [インストール: profile選択チェック表](installation.md#profile選択チェック表) を参照してください。
## 3.5 初回ヘルスチェック（推奨）

初回起動時は、次の3点を順に確認すると原因切り分けがしやすくなります。

### 1. コンテナ状態を確認

```bash
docker compose --profile default ps
```

`db` `valkey` `api` `docs` が `Up` になっていることを確認します。

### 2. APIログを確認

```bash
docker compose --profile default logs --tail=100 api
```

エラーで停止していないか、ポート `8000` で待受を開始しているかを確認します。

### 3. HTTPヘルスエンドポイントを確認

```bash
curl -i http://localhost:8000/health
```

`HTTP/1.1 200 OK`（または `HTTP/2 200`）と `{"status":"healthy"}` が返れば初回ヘルスチェックは完了です。
## 4. 動作確認

### ヘルスチェック

```bash
curl http://localhost:8000/health
# {"status":"healthy"}
```

### curlだけで行う最小スモーク手順（GUI不要）

初期導入後は、次の3コマンドだけでAPIの疎通を確認できます。

```bash
# 1) APIの生存確認（200 + healthy）
curl -fsS http://localhost:8000/health

# 2) APIドキュメント到達確認（200）
curl -fsS -o /dev/null -w '%{http_code}\n' http://localhost:8000/docs

# 3) Mock OAuth開始エンドポイントの到達確認（302）
curl -fsS -o /dev/null -w '%{http_code}\n' \
  "http://localhost:8000/api/v1/auth/mock/login?user=alice&provider=google"
```

期待値:
- 1) `{"status":"healthy"}`
- 2) `200`
- 3) `302`

### Mock OAuthでテスト

開発環境では、実際のOAuthプロバイダーなしでテストできます：

```bash
curl "http://localhost:8000/api/v1/auth/mock/login?user=alice&provider=google"
```

### Mock OAuthから実OAuthへ切り替える最小チェック

Mock 検証が完了したら、実 OAuth へ切り替える前に次の3点だけ確認します。

1. モード切替: `MOCK_OAUTH_ENABLED=0`（または未設定）になっている
2. 秘密情報: 利用する provider の `client_id` / `client_secret` を `secrets/*.txt` に設定済み
3. redirect URI: provider 管理画面の callback URL が `https://<api-domain>/api/v1/auth/<provider>/callback` と一致している

切替後の最小確認コマンド:

```bash
# 1) APIの生存確認
curl -fsS http://localhost:8000/health

# 2) 実OAuth開始導線の到達確認（302 を期待）
curl -fsS -o /dev/null -w '%{http_code}\n' \
  "http://localhost:8000/api/v1/auth/google"
```

`invalid_client` や `redirect_uri_mismatch` が出る場合は
[トラブルシューティング](help/troubleshooting.md) を参照してください。

再開ポイント:
- [FAQ: Mock OAuthから実OAuthへ切り替える最小確認は？](help/faq.md#mock-oauthから実oauthへ切り替える最小確認は)
- [インストール: provider 未設定時の最短スキップ手順](installation.md#provider-未設定時の最短スキップ手順)
- [トラブルシューティング: provider 未設定のまま認証導線を実行した](help/troubleshooting.md#provider-未設定のまま認証導線を実行した)

### セッション失効時の再ログイン手順

アクセストークン失効で `401 Unauthorized` が返る場合は、次の順序で復旧します。

1. まずリフレッシュトークンで再発行を試す

```bash
curl -sS -X POST "http://localhost:8000/api/v1/auth/refresh" \
  -H "Content-Type: application/json" \
  -d '{"refresh_token":"<refresh_token>"}'
```

判定基準:
- `200` かつ `access_token` が返る: 新しいアクセストークンで API 呼び出しを再開
- `401` / `422`: refresh では復旧できないため、手順2へ進む

2. 再発行できない場合は OAuth ログインを再実行する

```bash
# 例: Google OAuth を再開始
open "http://localhost:8000/api/v1/auth/google"
```

3. 複数端末で状態がずれた場合は古いセッションを失効させる

```bash
curl -sS -X DELETE "http://localhost:8000/api/v1/sessions/me" \
  -H "Authorization: Bearer <access_token>"
```

4. 復旧確認を行う（最小確認）

```bash
curl -sS -o /dev/null -w '%{http_code}\n' \
  "http://localhost:8000/api/v1/users/me" \
  -H "Authorization: Bearer <new_access_token>"
```

`200` なら復旧完了です。`401` が継続する場合は、`Authorization` ヘッダーのトークン更新漏れを確認してください。

補足:
- 認証API詳細は `docs/api/auth.md` を参照してください。
- セッションAPI一覧は `README.md` の `Sessions` セクションと同一です。
- 管理API向けの同等手順は `docs/help/troubleshooting.md` の「管理者トークン失効で管理APIが `401 Unauthorized` になる」を参照してください。

### OAuth callback失敗時の確認順

`/api/v1/auth/{provider}/callback` が失敗した場合は、次の順で確認すると切り分けが早くなります。

1. APIログで callback エラー種別を確認
   ```bash
   docker compose logs api --since=30m | rg -n "callback|Invalid state|invalid_client|401"
   ```
2. `Invalid or expired state` の場合は、`state mismatch` 診断フローを実施
   - [トラブルシューティング: state mismatch 診断フロー](help/troubleshooting.md#state-mismatch-flow)
3. `OAuth callback failed: invalid_client` / `401` の場合は、シークレット値と provider 設定を確認
   - [トラブルシューティング: 401 Unauthorized / invalid_client](help/troubleshooting.md#401-unauthorized--invalid_client)
4. 修正後は認証を最初から再実行し、同じエラーが再現しないことを確認
   ```bash
   curl -I "http://localhost:8000/api/v1/auth/google"
   ```

### ユーザー情報取得API（`/api/v1/users/me`）の前提条件

`/api/v1/users/me` は認証必須APIです。呼び出し前に次の3点を満たしてください。

1. APIが起動済みである（`docker compose --profile default up -d` 実行済み）
2. アクセストークンを取得済みである（例: `GET /api/v1/auth/mock/login`）
3. `Authorization: Bearer <access_token>` ヘッダーを付与する

確認例:

```bash
# 1) トークン取得
TOKEN=$(curl -s "http://localhost:8000/api/v1/auth/mock/login?user=alice&provider=google" | jq -r '.access_token')

# 2) ユーザー情報取得
curl -H "Authorization: Bearer ${TOKEN}" \
  "http://localhost:8000/api/v1/users/me"
```

`limit=1/100` の境界値を含む一覧系確認を同じトークンで行う場合は、[ユーザーAPIの検証例](api/users.md#ページング境界値limit1100の検証例) を参照してください。

### エラーレスポンスの確認

未認証でログアウトAPIを呼ぶと、`401 Unauthorized` とエラーボディを確認できます。

```bash
curl -i -X POST "http://localhost:8000/api/v1/auth/logout" \
  -H "Content-Type: application/json" \
  -d '{"refresh_token":"dummy"}'
```

期待値:

- ステータスコード: `401 Unauthorized`
- `WWW-Authenticate` ヘッダ: `Bearer`
- レスポンスボディ: `{"detail":{"code":"missing_bearer_token","message":"Not authenticated"}}`

値を機械的に確認したい場合は、次のコマンドで HTTP ステータスと本文を同時に検証できます。

```bash
status=$(curl -s -o /tmp/logout-unauth.json -w "%{http_code}" -X POST "http://localhost:8000/api/v1/auth/logout" \
  -H "Content-Type: application/json" \
  -d '{"refresh_token":"dummy"}')
test "$status" = "401"
jq -e '.detail.code == "missing_bearer_token" and .detail.message == "Not authenticated"' /tmp/logout-unauth.json
```

詳細な調査手順は [トラブルシューティング](help/troubleshooting.md) を参照してください。

## 5. Webhook導入の最短導線

Webhookは、getting-started から以下の2クリック以内で設定手順へ到達できます。

1. このページの「次のステップ」から [Webhook設定](guides/webhooks.md) を開く
2. ガイド内の [クイック導入（5分）](guides/webhooks.md#クイック導入5分) に沿って設定する

### Webhook導入の前提条件

- API が起動していること（`docker compose --profile default up -d`）
- `config/webhooks.yaml` を作成済みであること
- Webhook受信先URLを用意できること（例: [webhook.site](https://webhook.site)）

### 送信確認の最小手順

1. [Webhook設定](guides/webhooks.md) の例を使って `config/webhooks.yaml` を作成する
2. Mock OAuth ログインを実行する
3. 配信履歴 API で Webhook 送信結果を確認する

```bash
curl "http://localhost:8000/api/v1/auth/mock/login?user=alice&provider=google"
curl http://localhost:8000/api/v1/admin/webhooks/deliveries
```

## 初回導入チェックリスト

初回セットアップ時は、以下を上から順に確認してください。Quick Start の手順と重なる項目は最小限にし、失敗しやすいポイント（secret不足・callback URL不一致）を優先しています。

- [ ] profile定義が想定どおりか確認する
  コマンド: `docker compose config --profiles`
  確認基準: `default` `full` `ci` の3つが表示される。
- [ ] 必須 secret が存在するか確認する
  コマンド: `ls secrets/*client_id.txt secrets/*client_secret.txt secrets/jwt_secret.txt`
  確認基準: 使うプロバイダー分の `client_id/client_secret` と `jwt_secret` が不足なく存在する。
- [ ] OAuth callback URL の登録値を確認する
  手順:
  1. 期待値を組み立てる（`google` は利用する provider 名へ置換）
     コマンド: `API_BASE_URL=http://localhost:8000 PROVIDER=google echo "${API_BASE_URL}/api/v1/auth/${PROVIDER}/callback"`
  2. provider 管理画面（Redirect/Callback URL 設定）を開く
     確認場所: 各プロバイダー管理画面の OAuth クライアント設定
  3. 管理画面の登録値と 1 の出力結果を照合する
     確認基準: スキーム/ホスト/ポート/パスが完全一致し、末尾 `/` が付かない
  参照先: [OAuth設定ガイド](guides/oauth/index.md) と各プロバイダー節（`docs/guides/oauth/*.md`）
- [ ] API が正常起動しているか確認する
  コマンド: `curl http://localhost:8000/health`
  確認基準: `{"status":"healthy"}` が返る。
- [ ] 認可開始エンドポイントがリダイレクトを返すか確認する
  コマンド: `curl -I http://localhost:8000/api/v1/auth/google/login`
  確認基準: `HTTP/1.1 302` または `HTTP/2 302` が返る。
- [ ] エラー時の参照順を確認する
  確認場所: [トラブルシューティング](help/troubleshooting.md) の `state mismatch` / `provider error` 節
  確認基準: 失敗時に `health -> auth -> provider` の順で切り分けできる。

!!! warning "プロバイダ仕様変更時の更新対象"
    Callback URL や scope の仕様が変わった場合は、`docs/guides/oauth/index.md` と `docs/guides/oauth/*.md` の該当プロバイダー節を先に更新し、本チェックリストの確認基準も合わせて見直してください。
## 次のステップ

- [インストール](installation.md) - profile差分と運用時の確認手順
- [初回起動トラブルシュート](help/first-start-troubleshooting.md) - 初回セットアップで詰まったときの最短切り分け
- [OAuth設定](guides/oauth/index.md) - 各プロバイダーの設定方法
- [OAuthガイド共通チェックテンプレート](guides/oauth/index.md#oauthガイド共通チェックテンプレート) - callback/scope/secrets/test の確認観点
- [障害時の参照順](help/troubleshooting.md#障害時の参照順最短導線) - 調査を health → auth → provider → webhook の順で進める
- [トラブルシューティング](help/troubleshooting.md#state-mismatch-flow) - `Invalid or expired state` の診断手順
- [Webhook設定](guides/webhooks.md) - 外部サービス連携
- [デプロイ](guides/deployment.md) - 本番環境へのデプロイ

## API認証トラブル時の参照順

API認証で問題が発生した場合は、次の順で確認してください。

1. [インストール](installation.md#oauth認証情報)で OAuth シークレットの配置と profile を確認する
2. [クイックスタート](getting-started.md#4-動作確認)で `/health` と `/docs` の到達性を確認する
3. [トラブルシューティング: 障害時の参照順（最短導線）](help/troubleshooting.md#障害時の参照順最短導線) で `health -> auth -> provider -> webhook` の順に切り分ける
4. 認証フローの失敗は [state mismatch 診断フロー](help/troubleshooting.md#state-mismatch-flow)、資格情報エラーは [`401 Unauthorized` / `invalid_client`](help/troubleshooting.md#401-unauthorized--invalid_client) を確認する
