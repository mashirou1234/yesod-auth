# クイックスタート

このガイドでは、YESOD Authを5分でセットアップする方法を説明します。

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

## 3. 起動

```bash
docker compose --profile default up -d
```

`default`プロファイルでは、Compose設定により`MOCK_OAUTH_ENABLED=1`がAPIサービスへ適用されます（アプリ既定値は`0`）。

### Compose profile差分の確認

起動前に、利用するプロファイルで有効になるサービス差分を確認できます。

```bash
# default: 最小構成（api / admin / db / redis）
docker compose --profile default config --services

# full: default + caddy
docker compose --profile default --profile full config --services

# ci: テスト用の isolated 構成
docker compose --profile ci config --services
```

`MOCK_OAUTH_ENABLED` の適用差分は次で確認できます。

```bash
docker compose --profile default config | rg "MOCK_OAUTH_ENABLED|api:"
docker compose --profile ci config | rg "MOCK_OAUTH_ENABLED|api-ci:"
```

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

- [初回起動トラブルシュート](help/first-start-troubleshooting.md) - 初回セットアップで詰まったときの最短切り分け
- [OAuth設定](guides/oauth/index.md) - 各プロバイダーの設定方法
- [障害時の参照順](help/troubleshooting.md#障害時の参照順最短導線) - 調査を health → auth → provider → webhook の順で進める
- [トラブルシューティング](help/troubleshooting.md#state-mismatch-flow) - `Invalid or expired state` の診断手順
- [Webhook設定](guides/webhooks.md) - 外部サービス連携
- [デプロイ](guides/deployment.md) - 本番環境へのデプロイ
