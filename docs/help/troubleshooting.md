# トラブルシューティング

## 障害時の参照順（最短導線）

障害調査は次の順で確認してください。前段が正常なら次段へ進みます。

1. `health`: API と依存サービスの生存確認
2. `auth`: 認証フローの失敗箇所を特定（state / callback / session）
3. `provider`: OAuth プロバイダー側設定・資格情報の不一致を確認
4. `webhook`: 認証後処理や外部通知の遅延・失敗を確認

最小コマンド例（最初の切り分け用）:

```bash
curl -fsS http://localhost:8000/health
docker compose logs api --since=30m | rg -n "Invalid state|callback|invalid_client|401"
```

## 起動時のエラー

`secret ... not found` の即時復旧は [`インストールガイド` の secret不足時手順](../installation.md#1-docker-compose-up-で-secret-未設定エラーになる) を先に実行してください。

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

`/api/v1/auth/refresh` の失敗を先に分類したい場合は、[`認証API: refresh失敗時エラー分類`](../api/auth.md#refresh失敗時エラー分類) を起点に確認してください。

### `Invalid or expired state`

**原因:** OAuth認証中にセッションが切れた、または不正なリクエスト

**解決策:**

1. 認証フローを最初からやり直す
2. Valkeyが正常に動作しているか確認

<a id="state-mismatch-flow"></a>

#### `state mismatch` 診断フロー

0. ログ採取ウィンドウを統一する（推奨値）
   ```bash
   SINCE=30m
   docker compose logs api --since="$SINCE" | rg -n "Invalid state|/auth/.*/callback"
   docker compose logs valkey --since="$SINCE"
   ```
   - API/Valkey は同一 `--since` を使い、時系列比較を容易にする
   - 例外調査で範囲を広げる場合も、両ログで同じ値にそろえる
1. 発生時刻とリクエストを特定する（APIログ）
   ```bash
   docker compose logs api --since="$SINCE" | rg "Invalid state|/auth/.*/callback"
   ```
2. `state` が一度だけ消費される前提を確認する（再送/二重callbackの有無）
   - 同一ブラウザ操作で callback が複数回呼ばれていないか
   - リバースプロキシや監視が callback URL を再実行していないか
3. Valkey の接続状態を確認する（保存済みstateが即時消失していないか）
   ```bash
   docker compose logs valkey --since="$SINCE"
   ```
4. OAuth開始URLとcallback URLの組み合わせを確認する（環境不一致の検出）
   - 開始: `GET /api/v1/auth/{provider}`
   - callback: `GET /api/v1/auth/{provider}/callback?code=...&state=...`
   - `API_URL` / `FRONTEND_URL` の環境差分を確認

採取記録テンプレート（最低3項目）:

- 発生時刻（UTC/JST）と調査ウィンドウ値（例: `SINCE=30m`）
- provider 名（`github` / `google` など）と callback URL
- `state` 再送有無（ブラウザ再送・プロキシ再試行・監視アクセス）
- API/Valkey ログの該当行番号または抽出キーワード

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

<a id="provider-未設定のまま認証導線を実行した"></a>

### provider 未設定のまま認証導線を実行した

**症状:** `GET /api/v1/auth/<provider>` 実行時に `invalid_client` や secret 読み込みエラーが発生する。

**最短対応:**

1. 未設定 provider の導線呼び出しを一度止める
2. `curl -fsS http://localhost:8000/health` と `curl -fsS -o /dev/null -w '%{http_code}\n' http://localhost:8000/docs` で起動確認を先に完了する
3. 対象 provider の `*_client_id` / `*_client_secret` を追加し、`docker compose --profile default up -d --force-recreate api` で再開する

再開ポイント:
- [クイックスタート: provider 未設定時の最短スキップ手順](../getting-started.md#provider-未設定時の最短スキップ手順)
- [インストール: provider 未設定時の最短スキップ手順](../installation.md#provider-未設定時の最短スキップ手順)

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

#### invalid_client 再発防止チェック（デプロイ前後で毎回実施）

次の 4 項目を上から順に実施し、すべて満たした場合のみ OAuth 設定変更を完了とします。

1. 対象 provider の secret ファイルが 2 つとも存在することを確認する
   ```bash
   ls -l secrets/github_client_id.txt secrets/github_client_secret.txt
   ```
2. 変更後の Compose 定義に対象 secret が含まれることを確認する
   ```bash
   docker compose config | rg -n "github_client_id|github_client_secret"
   ```
3. API 再作成後に `invalid_client` が新規発生していないことを確認する
   ```bash
   docker compose up -d --force-recreate api
   docker compose logs api --since=10m | rg -n "invalid_client|401"
   ```
4. callback URL が現在の公開 API URL と一致していることを provider 管理画面で確認する
   - 形式: `https://<api-domain>/api/v1/auth/{provider}/callback`
   - self-host 運用時の基準は [OAuth設定ガイド](../guides/oauth/index.md#セルフホスト運用チェックリスト) を参照

上記チェックを実施しても再発する場合は、[インストール時の secret 不足診断](../installation.md#1-docker-compose-up-で-secret-未設定エラーになる) を再実行し、secret 名と実ファイル名の不一致を先に解消してください。

---

<a id="secrets-permission-recovery"></a>

### secrets 権限不備で `Permission denied` が出る

**症状:** `docker compose up -d` 実行時に `permission denied` が出て起動できない。`/run/secrets/*` の読み込みエラーが API ログに残る。

**確認手順（Linux/macOS）:**

1. 対象 secret の所有者とパーミッションを確認する
   ```bash
   ls -l secrets/*.txt
   ```
2. Linux の詳細確認
   ```bash
   stat -c '%n %a %U:%G' secrets/*.txt
   ```
3. macOS の詳細確認
   ```bash
   stat -f '%N %Lp %Su:%Sg' secrets/*.txt
   ```

**復旧手順:**

1. パーミッションを `600` に戻す
   ```bash
   chmod 600 secrets/*.txt
   ```
2. 所有者が現在ユーザーでない場合は修正する（Linux/macOS 共通）
   ```bash
   sudo chown \"$(id -un):$(id -gn)\" secrets/*.txt
   ```
3. API を再作成して反映する
   ```bash
   docker compose up -d --force-recreate api worker
   ```
4. 再確認する
   ```bash
   docker compose logs --tail=100 api | rg -n \"permission denied|/run/secrets|invalid_client\"
   curl -fsS http://localhost:8000/health
   ```

**受け入れ時の三点同期チェック:**

1. FAQ: [OAuth secret の権限不備を最短で復旧するには？](./faq.md#oauth-secret-の権限不備を最短で復旧するには) の手順順序と一致していること
2. Installation: [OAuth secret ファイル権限の復旧手順](../installation.md#oauth-secret-ファイル権限の復旧手順) のコマンドと一致していること
3. 本節（troubleshooting）では症状→確認→復旧の順序になっていること

---

<a id="oauth-clock-skew"></a>

### OAuth callback で `invalid_grant` が断続的に発生する（clock skew）

**症状:** 同一設定でも時間帯やホストごとに `invalid_grant` / `code has expired` が発生し、再試行で一時的に成功する

**原因:** APIサーバー・リバースプロキシ・ホストOSの時刻差（clock skew）により、OAuth認可コードの有効期限判定がずれる

**診断手順（最小）:**

1. 発生時刻の前後で callback 失敗ログを抽出する
   ```bash
   docker compose logs api --since=30m | rg -n "invalid_grant|code has expired|callback"
   ```
2. APIコンテナとホストの現在時刻を比較する（秒差を確認）
   ```bash
   date -u
   docker compose exec api date -u
   ```
3. NTP同期状態を確認する（self-host 環境）
   ```bash
   timedatectl status
   ```
4. プロバイダー側の認可コード発行時刻と、callback受信時刻の乖離を確認する
   - 監査ログ/アクセスログの時刻がUTC基準で連続しているか
   - 特定ノードだけ数十秒以上ずれていないか

| 想定原因 | 観測シグナル | 対処 |
| --- | --- | --- |
| ホスト時刻が遅延/先行 | `date -u` でノード間に秒差がある | NTP再同期後にOAuthを再試行 |
| コンテナ時刻が固定化 | ホスト更新後も `docker compose exec api date -u` が追従しない | コンテナ再作成（`docker compose up -d --force-recreate api`） |
| 逆プロキシ/多段環境の遅延 | callback 到達までの遅延が長い | callback 経路を短縮し、リトライ実装を見直す |

**補足:** OAuth導入時は [OAuth設定ガイド](../guides/oauth/index.md) のセルフホスト手順と併せて、時刻同期を初期チェック項目に含めてください。

---

<a id="auth-rate-limit-429"></a>

### `429 Too Many Requests`（認証レート制限）

```json
{"detail":"Rate limit exceeded"}
```

**原因:** 短時間に認証エンドポイントへアクセスが集中し、`api/app/auth/rate_limit.py` の制限値を超過した

**確認手順（一次切り分け）:**

1. 429 発生時刻と対象エンドポイントを特定する
   ```bash
   docker compose logs api --since=30m | rg -n "429|Too Many Requests|/api/v1/auth/"
   ```

2. 現在の制限値と参照元を確認する
   - 参照元: `api/app/auth/rate_limit.py`
   - 制限値: `settings.RATE_LIMIT_PER_MINUTE`（`default_limits=[f"{settings.RATE_LIMIT_PER_MINUTE}/minute"]`）
   - ストレージ: `settings.VALKEY_URL`（レート制限カウンタ保存先）

3. 実行環境の設定値が意図どおりか確認する
   ```bash
   docker compose exec api env | rg -n "RATE_LIMIT_PER_MINUTE|VALKEY_URL"
   ```

4. Valkey 側の疎通とエラー有無を確認する
   ```bash
   docker compose exec valkey sh -lc 'valkey-cli ping || redis-cli ping'
   docker compose logs valkey --since=30m
   ```

**対処の目安:**

- バースト的なアクセスが原因: クライアント側の再試行間隔を延ばす
- 設定値が過小: `RATE_LIMIT_PER_MINUTE` を運用実態に合わせて調整
- Valkey 障害が疑われる: Valkey 復旧後に再試行し、429/接続エラーの再発有無を確認

<a id="users-pagination-limit-check"></a>

### `/api/v1/sessions` で `limit=1/100` の結果が不安定

**症状:** 同一トークンで `GET /api/v1/users/me` は成功するが、`/api/v1/sessions?limit=1` または `limit=100` の件数/応答が期待とずれる

**確認手順:**

1. 同じアクセストークンで `users/me` が成功することを先に確認する
   ```bash
   curl -i -H "Authorization: Bearer <access_token>" \
     "http://localhost:8000/api/v1/users/me"
   ```
2. `limit=1` と `limit=100` を連続実行し、HTTPステータスと件数を比較する
   ```bash
   curl -sS -H "Authorization: Bearer <access_token>" \
     "http://localhost:8000/api/v1/sessions?limit=1" | jq '.items | length'
   curl -sS -H "Authorization: Bearer <access_token>" \
     "http://localhost:8000/api/v1/sessions?limit=100" | jq '.items | length'
   ```
3. 期待値から外れる場合は API ログを確認する
   ```bash
   docker compose logs api --since=30m | rg -n "/api/v1/sessions|401|422"
   ```

**期待値:**

- 両方とも `200` を返す
- 返却件数は指定 `limit` を超えない
- `401` が混在する場合はトークン失効を疑い、再ログイン後に再検証する

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

<a id="admin-i18n-fallback"></a>

### Admin i18n 未翻訳キーの確認手順

**症状:** Admin 画面で翻訳文の代わりに `nav.xxx` のようなドット区切りキーが表示される

**実装上の期待挙動 (`admin/i18n.py`):**

1. 未対応言語コードは `en` にフォールバック
2. 未翻訳キーはキー文字列をそのまま返却
3. フォーマット引数不足時はテンプレート文字列をそのまま返却

**確認コマンド（最小再現）:**

```bash
python3 - <<'PY'
from admin.i18n import get_text
print("unsupported lang ->", get_text("nav.overview", "zz"))
print("missing key ->", get_text("nav.not_exists", "ja"))
print("missing format arg ->", get_text("common.environment_warning", "en"))
PY
```

**判断基準:**

- `unsupported lang` が英語文言なら言語フォールバックは正常
- `missing key` が `nav.not_exists` のようにキー文字列なら未翻訳フォールバックは正常
- `missing format arg` がテンプレート文字列（例: `{name}` を含む）なら例外回避フォールバックは正常

FAQ での方針説明は [FAQ: Adminで未翻訳キーが出たときの表示は？](./faq.md#admin-i18n-untranslated-fallback) を参照。

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

**診断手順（最小）:**

1. API 側で署名失敗ログを先に抽出する
   ```bash
   docker compose logs api --since=30m | rg -n "webhook|signature|invalid signature|401|403"
   ```
2. 送信側と受信側のシークレット値が同一か確認する
   - 送信側（外部サービス）に設定した署名鍵
   - 受信側（yesod-auth）が参照する `config/webhooks.yaml` / secrets
3. 設定変更直後は管理APIでリロードを実行する
   ```bash
   curl -X POST http://localhost:8000/api/v1/admin/webhooks/reload
   ```
4. 同じペイロードで再送し、HTTP ステータスが `2xx` に戻るか確認する

| 想定原因 | 観測シグナル | 対処 |
| --- | --- | --- |
| 署名鍵の不一致 | 同一イベントで `invalid signature` が継続 | 送受信で同じ鍵へ統一し、`reload` 実行後に再送 |
| ボディ改変（JSON整形/文字コード差分） | 送信元では成功、受信側だけ失敗 | 受信側は raw body をそのまま検証し、ミドルウェア改変を無効化 |
| 時刻ずれや再送遅延 | 特定環境のみ断続的に失敗 | サーバー時刻同期を確認し、遅延経路を短縮 |

署名鍵ローテーション時の手順は [Webhook API の `reload` 説明](../api/webhooks.md#署名鍵ローテーション時の利用) を参照。

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
