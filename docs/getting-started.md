# クイックスタート

このガイドでは、YESOD Authを5分でセットアップする方法を説明します。

!!! info "先に確認すると安全な項目"
    Docker要件や `default` / `full` / `ci` の違いは[インストール](installation.md)に整理しています。初回導入時は先に確認してください。

## 前提条件

- Docker & Docker Compose
- Google Cloud ConsoleまたはDiscord Developer Portalのアカウント

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

!!! tip "provider追加時は先にチェック"
    新しい OAuth provider を追加する場合は、先に [OAuth provider追加時の事前チェック](installation.md#oauth-provider追加時の事前チェック) を実施してから secrets を作成してください。

!!! tip "JWTシークレットの生成"
    ```bash
    openssl rand -base64 32 > secrets/jwt_secret.txt
    ```

### OAuthガイドへの導線

クイックスタートで起動確認した後、利用するプロバイダーの設定を進めてください。

- [OAuth設定ハブ](guides/oauth/index.md)
- [Google OAuth ガイド](guides/oauth/google.md)
- [Discord OAuth ガイド](guides/oauth/discord.md)
- [GitHub OAuth ガイド](guides/oauth/github.md)

## 2.5 コールバックURLの検証

OAuth導入時は、実装前に「登録したコールバックURL」と「実際にYESOD Authが受けるURL」が一致することを確認します。

### 基本ルール

- 形式は `https://<api-domain>/api/v1/auth/<provider>/callback`
- `http` はローカル開発以外で使わない
- 末尾スラッシュを付けない（`.../callback/` は不可）
- `provider` は実際に有効化したものだけ登録する

### 検証チェックリスト

1. API公開URLを決める（例: `https://api.example.com`）
2. プロバイダーごとに callback URL を作る（例: `https://api.example.com/api/v1/auth/google/callback`）
3. OAuthプロバイダー管理画面の設定値と、`docs/api/auth.md` のパス仕様が一致することを確認する
4. リバースプロキシ利用時は `X-Forwarded-Proto=https` が正しく渡る構成にする
5. ログイン実行後、`Invalid state` や `redirect_uri_mismatch` が出ないことを確認する

## 3. 起動

```bash
docker compose --profile default up -d
```

`default`プロファイルでは、Compose設定により`MOCK_OAUTH_ENABLED=1`がAPIサービスへ適用されます（アプリ既定値は`0`）。

## 3.5 初回ヘルスチェック（推奨）

初回起動時は、次の3点を順に確認すると原因切り分けがしやすくなります。

### 1. コンテナ状態を確認

```bash
docker compose --profile default ps
```

`api` と `admin` が `Up` になっていることを確認します。

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

### セッション失効時の再ログイン手順

アクセストークン失効で `401 Unauthorized` が返る場合は、次の順序で復旧します。

1. まずリフレッシュトークンで再発行を試す

```bash
curl -X POST "http://localhost:8000/api/v1/auth/refresh" \
  -H "Content-Type: application/json" \
  -d '{"refresh_token":"<refresh_token>"}'
```

2. 再発行できない場合は OAuth ログインを再実行する

```bash
# 例: Google OAuth を再開始
open "http://localhost:8000/api/v1/auth/google"
```

3. 複数端末で状態がずれた場合は古いセッションを失効させる

```bash
curl -X DELETE "http://localhost:8000/api/v1/sessions/me" \
  -H "Authorization: Bearer <access_token>"
```

補足:
- 認証API詳細は `docs/api/auth.md` を参照してください。
- セッションAPI一覧は `README.md` の `Sessions` セクションと同一です。

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
### エラーレスポンスの確認

未認証でログアウトAPIを呼ぶと、`401 Unauthorized` とエラーボディを確認できます。

```bash
curl -i -X POST "http://localhost:8000/api/v1/auth/logout" \
  -H "Content-Type: application/json" \
  -d '{"refresh_token":"dummy"}'
```

期待値:

- ステータスコード: `401 Unauthorized`
- レスポンスボディ: `{"detail":"Not authenticated"}`

詳細な調査手順は [トラブルシューティング](help/troubleshooting.md) を参照してください。

## 5. Webhook導入の最短導線

Webhookは、getting-started から以下の2クリック以内で設定手順へ到達できます。

1. このページの「次のステップ」から [Webhook設定](guides/webhooks.md) を開く
2. ガイド内の [ローカルテスト](guides/webhooks.md#ローカルテスト) に沿って設定する

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
  確認場所: 各プロバイダー管理画面の Redirect/Callback URL 設定
  参照先: [OAuth設定ガイド](guides/oauth/index.md) と各プロバイダー節（`docs/guides/oauth/*.md`）
  確認基準: `http://localhost:8000/api/v1/auth/<provider>/callback` と完全一致（スキーム/ホスト/ポート/パス）。
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
- [障害時の参照順](help/troubleshooting.md#障害時の参照順最短導線) - 調査を health → auth → provider → webhook の順で進める
- [トラブルシューティング](help/troubleshooting.md#state-mismatch-flow) - `Invalid or expired state` の診断手順
- [Webhook設定](guides/webhooks.md) - 外部サービス連携
- [デプロイ](guides/deployment.md) - 本番環境へのデプロイ

## API認証トラブル時の参照順

API認証で問題が発生した場合は、次の順で確認してください。

1. [インストール](installation.md#oauth認証情報)で OAuth シークレットの配置と profile を確認する
2. [クイックスタート](getting-started.md#4-動作確認)で `/health` と `/docs` の到達性を確認する
3. [トラブルシューティング](help/troubleshooting.md#state-mismatch-flow)で症状別の診断手順を実施する
