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

<a id="state-mismatch-flow"></a>

#### `state mismatch` 診断フロー

1. 発生時刻とリクエストを特定する（APIログ）
   ```bash
   docker compose logs api --since=30m | rg "Invalid state|/auth/.*/callback"
   ```
2. `state` が一度だけ消費される前提を確認する（再送/二重callbackの有無）
   - 同一ブラウザ操作で callback が複数回呼ばれていないか
   - リバースプロキシや監視が callback URL を再実行していないか
3. Valkey の接続状態を確認する（保存済みstateが即時消失していないか）
   ```bash
   docker compose logs valkey --since=30m
   ```
4. OAuth開始URLとcallback URLの組み合わせを確認する（環境不一致の検出）
   - 開始: `GET /api/v1/auth/{provider}`
   - callback: `GET /api/v1/auth/{provider}/callback?code=...&state=...`
   - `API_URL` / `FRONTEND_URL` の環境差分を確認

| 想定原因 | 観測シグナル | 対処 |
| --- | --- | --- |
| callback の二重実行 | 同一 `state` で callback ログが連続する | ブラウザ再送・プロキシ再試行を止め、ログイン導線を1回実行に統一 |
| Valkey 接続不安定 | `OAuthStateStore` 参照前後で Valkey エラーが発生 | Valkey を復旧し、`docker compose ps/logs valkey` で安定化確認後に再試行 |
| OAuth開始とcallbackの環境不一致 | `API_URL` と実アクセス先のホスト/スキームが異なる | 環境変数を一致させて再デプロイし、再度 `/api/v1/auth/{provider}` から開始 |

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

### 管理者トークン失効で管理APIが `401 Unauthorized` になる

**症状:** 管理画面操作や `GET /api/v1/admin/*` 呼び出しが `401 Unauthorized` を返す

**再認証導線:**

1. まず現在トークンの失効を確認
   ```bash
   curl -i -H "Authorization: Bearer <access_token>" \
     http://localhost:8000/api/v1/admin/webhooks/endpoints
   ```
2. 有効な `refresh_token` が残っている場合は `POST /api/v1/auth/refresh` で再発行
   ```bash
   curl -sS -X POST http://localhost:8000/api/v1/auth/refresh \
     -H "Content-Type: application/json" \
     -d '{"refresh_token":"<refresh_token>"}'
   ```
3. `refresh_token` も失効済みなら、OAuth ログインを最初から実行して新しいトークンを取得
4. 新しい `access_token` で管理APIを再実行し、`200` を確認
5. 同事象が頻発する場合は `ACCESS_TOKEN_LIFETIME_SECONDS` を見直し、運用手順に定期再認証を追加

**補足:** フロントエンド実装では、管理APIで `401` を受けた場合に `/api/v1/auth/refresh` を1回試し、失敗時に再ログインへ遷移すると再現性高く復旧できます。

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
