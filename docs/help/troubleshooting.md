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

### `401 Unauthorized` / `invalid_client`

```json
{"detail":"OAuth callback failed: invalid_client"}
```

**原因:** OAuth provider の `client_id` または `client_secret` が未設定、または誤っている

**確認事項:**

1. provider 用シークレットファイルの中身を確認
   ```bash
   ls -l secrets/*github* secrets/*google* 2>/dev/null
   ```

2. APIログで provider 側エラーを確認
   ```bash
   docker compose logs --tail=100 api | rg -n "invalid_client|401|client_secret|client_id"
   ```

**解決策:**

1. `secrets/*.txt` を正しい値へ更新（例: `secrets/github_client_id.txt`, `secrets/github_client_secret.txt`）
2. Compose を再起動して設定を反映
   ```bash
   docker compose up -d --force-recreate api admin
   ```
3. 認証を再実行し、失敗時は provider 側アプリ設定（redirect URI / secret再発行）も確認

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

### 全サービスのログ

```bash
docker compose logs -f
```
