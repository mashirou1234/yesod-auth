# トラブルシューティング

## 起動時のエラー

### `pg_cron`関連のエラー

```
ERROR: extension "pg_cron" is not available
```

**原因:** CI環境など、pg_cron拡張がないPostgreSQLを使用している

**解決策:** マイグレーションは自動的にpg_cronの有無を検出してスキップします。
このエラーが出る場合は、マイグレーションファイルを確認してください。

---

### データベース接続エラー

```
sqlalchemy.exc.OperationalError: could not connect to server
```

**解決策:**

1. PostgreSQLコンテナが起動しているか確認
   ```bash
   docker compose ps
   ```

2. ヘルスチェックを確認
   ```bash
   docker compose logs db
   ```

---

### ポート競合エラー

```
Error response from daemon: Ports are not available: listen tcp 0.0.0.0:5434: bind: address already in use
```

**原因:** ホスト側のポート5434が他のプロセスで使用されている

**解決策:**

1. 使用中のプロセスを確認
   ```bash
   lsof -i :5434
   ```

2. 必要に応じてプロセスを停止するか、`docker-compose.yml`のポートマッピングを変更

!!! note "ポート構成"
    - 開発環境のPostgreSQLはホスト側ポート`5434`を使用（他プロジェクトとの競合回避）
    - CI環境はポート`5433`を使用
    - コンテナ内部はいずれも標準の`5432`

---

## 認証エラー

### `Invalid or expired state`

**原因:** OAuth認証中にセッションが切れた、または不正なリクエスト

**解決策:**

1. 認証フローを最初からやり直す
2. Valkeyが正常に動作しているか確認

---

### `Mock OAuth is disabled`

```json
{"detail":"Mock OAuth is disabled. Set MOCK_OAUTH_ENABLED=1 to enable."}
```

**解決策:** 開発環境で`MOCK_OAUTH_ENABLED=1`を設定

```bash
# docker-compose.ymlで設定
environment:
  - MOCK_OAUTH_ENABLED=1
```

---

## ngrok関連

### ngrok URLが取得できない

```
Failed to get ngrok URL
```

**原因:** ngrokコンテナが正常に起動していない、または認証トークンが無効

**解決策:**

1. ngrokコンテナのログを確認
   ```bash
   docker compose logs ngrok
   ```

2. 認証トークンが正しいか確認
   ```bash
   cat secrets/ngrok_authtoken.txt
   ```

3. ngrokダッシュボード（http://localhost:4040）でトンネルの状態を確認

---

### ngrok authtoken無効エラー

```
ERR_NGROK_105: invalid authtoken
```

**原因:** `secrets/ngrok_authtoken.txt`の認証トークンが無効または期限切れ

**解決策:**

1. [ngrokダッシュボード](https://dashboard.ngrok.com/get-started/your-authtoken)で新しいトークンを取得
2. シークレットファイルを更新
   ```bash
   echo "new-authtoken" > secrets/ngrok_authtoken.txt
   ```
3. コンテナを再起動
   ```bash
   docker compose --profile default --profile ngrok down
   docker compose --profile default --profile ngrok up -d
   ```

---

### ngrok URLがValkeyに保存されない

**原因:** `ngrok-sync`コンテナがngrok APIに接続できない

**解決策:**

1. ngrok-syncコンテナのログを確認
   ```bash
   docker compose logs ngrok-sync
   ```

2. ngrokコンテナが先に起動しているか確認（依存関係は設定済みだが、トンネル確立に時間がかかる場合がある）

3. 手動でValkeyに保存する場合
   ```bash
   # ngrok URLを確認
   curl -s http://localhost:4040/api/tunnels | jq '.tunnels[0].public_url'

   # Valkeyに手動保存
   docker exec yesod-valkey valkey-cli SET ngrok:public_url "https://xxxx.ngrok-free.app"
   ```

---

### OAuthコールバックでngrok URLが使われない

**原因:** ValkeyにngrokのURLが保存されていない

**解決策:**

1. Valkeyに保存されているか確認
   ```bash
   docker exec yesod-valkey valkey-cli GET ngrok:public_url
   ```

2. 値が空の場合、ngrok-syncコンテナを再起動
   ```bash
   docker compose --profile ngrok restart ngrok-sync
   ```

---

## Webhook

### Webhookが発火しない

**確認事項:**

1. 設定ファイルの存在確認
   ```bash
   docker exec yesod-api ls -la /app/config/
   ```

2. 設定が読み込まれているか確認
   ```bash
   curl http://localhost:8000/api/v1/admin/webhooks/endpoints
   ```

3. イベントタイプが正しいか確認
   ```yaml
   events:
     - "user.created"  # 正しい
     - "user_created"  # 間違い
   ```

---

### 署名検証に失敗する

**確認事項:**

1. シークレットが一致しているか
2. タイムスタンプの形式が正しいか
3. ペイロードがそのまま（改変なし）で検証されているか

---

## パフォーマンス

### レスポンスが遅い

**確認事項:**

1. データベース接続プールの設定
2. Valkeyの接続状態
3. Webhookワーカーの負荷

**ログ確認:**

```bash
docker compose logs -f api
```

---

## ログの確認

### APIログ

```bash
docker compose logs -f api
```

### データベースログ

```bash
docker compose logs -f db
```

### ngrokログ

```bash
docker compose logs -f ngrok
docker compose logs -f ngrok-sync
```

### 全サービスのログ

```bash
docker compose logs -f
```