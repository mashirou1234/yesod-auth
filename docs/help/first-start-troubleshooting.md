# 初回起動トラブルシュート

`docker compose --profile default up -d` 実行直後の、初回セットアップ向け切り分け手順です。

## 0. 最初に確認する項目

1. サービス状態
   ```bash
   docker compose --profile default ps
   ```
2. ヘルスチェック
   ```bash
   curl -fsS http://localhost:8000/health
   ```
3. APIドキュメント
   ブラウザで `http://localhost:8000/docs` を開く
4. 必須 secrets
   ```bash
   ls -1 secrets/{google_client_id,google_client_secret,discord_client_id,discord_client_secret,jwt_secret}.txt
   ```

## 症状1: `/health` が失敗する

- 症状:
  `curl http://localhost:8000/health` が失敗、または `Connection refused`
- 確認コマンド:
  ```bash
  docker compose --profile default ps
  docker compose --profile default logs --tail=100 api db valkey
  ```
- 次アクション:
  - `api` が `Exited` の場合はログ内の設定エラーを修正
  - `db` が `healthy` でない場合は DB ログを優先して解消
  - 復旧後に再度 `curl -fsS http://localhost:8000/health` を実行

## 症状2: `/docs` は開くが OAuth 開始で 500 になる

- 症状:
  `http://localhost:8000/docs` は表示されるが、`/api/v1/auth/{provider}` 呼び出しで 500
- 確認コマンド:
  ```bash
  ls -1 secrets/{google_client_id,google_client_secret,discord_client_id,discord_client_secret,jwt_secret}.txt
  docker compose --profile default logs --tail=100 api | rg -n "secret|oauth|jwt|missing" -i
  ```
- 次アクション:
  - 欠落している `secrets/*.txt` を作成して値を設定
  - `jwt_secret.txt` が空なら再生成
    ```bash
    openssl rand -base64 32 > secrets/jwt_secret.txt
    ```
  - `docker compose --profile default restart api` 後に再確認

## 症状3: OAuth callback で state mismatch / invalid state

- 症状:
  callback で `Invalid or expired state` が返る
- 確認コマンド:
  ```bash
  docker compose --profile default ps valkey api
  docker compose --profile default logs --tail=100 valkey api
  ```
- 次アクション:
  - `valkey` 未起動なら起動して認証を最初からやり直す
  - ブラウザで複数タブ同時ログインを避け、1フローずつ実行
  - 反復する場合は [トラブルシューティング](troubleshooting.md) の認証エラー節へ

## 症状4: コマンドは成功するがログイン後ユーザー情報が取れない

- 症状:
  ログイン成功後に `/api/v1/users/me` が 401/403
- 確認コマンド:
  ```bash
  curl -i http://localhost:8000/api/v1/users/me
  docker compose --profile default logs --tail=100 api | rg -n "token|auth|bearer" -i
  ```
- 次アクション:
  - Authorization ヘッダー (`Bearer <access_token>`) を付与して再試行
  - `auth/refresh` でトークン更新し、再度 `users/me` を確認
  - 継続する場合は API ログと再現手順を添えて issue 化

## 関連ドキュメント

- [クイックスタート](../getting-started.md)
- [インストール](../installation.md)
- [トラブルシューティング](troubleshooting.md)
