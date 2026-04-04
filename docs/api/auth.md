# 認証API

## エンドポイント一覧

| メソッド | パス | 説明 |
|---------|------|------|
| GET | `/api/v1/auth/google` | Google OAuth開始 |
| GET | `/api/v1/auth/google/callback` | Googleコールバック |
| GET | `/api/v1/auth/github` | GitHub OAuth開始（organization所属の制限判定は未実装） |
| GET | `/api/v1/auth/github/callback` | GitHubコールバック |
| GET | `/api/v1/auth/discord` | Discord OAuth開始 |
| GET | `/api/v1/auth/discord/callback` | Discordコールバック |
| GET | `/api/v1/auth/x` | X (Twitter) OAuth開始 |
| GET | `/api/v1/auth/x/callback` | Xコールバック |
| GET | `/api/v1/auth/linkedin` | LinkedIn OAuth開始 |
| GET | `/api/v1/auth/linkedin/callback` | LinkedInコールバック |
| GET | `/api/v1/auth/facebook` | Facebook OAuth開始 |
| GET | `/api/v1/auth/facebook/callback` | Facebookコールバック |
| GET | `/api/v1/auth/slack` | Slack OAuth開始 |
| GET | `/api/v1/auth/slack/callback` | Slackコールバック |
| GET | `/api/v1/auth/twitch` | Twitch OAuth開始 |
| GET | `/api/v1/auth/twitch/callback` | Twitchコールバック |
| POST | `/api/v1/auth/refresh` | トークンリフレッシュ |
| POST | `/api/v1/auth/logout` | ログアウト |

---

## レート制限メトリクス

`GET /metrics` では OAuth 関連のレート制限を次のメトリクスで確認できます。

- `yesod_oauth_rate_limit_burst_total{provider="<provider>"}`: provider 別に 429 が返った回数
  - provider をパスから特定できない場合は `provider="missing_provider"` で集計
- `yesod_oauth_failures_total{provider="<provider>",reason="<reason>"}`: OAuth 処理失敗回数（既存）
  - `reason="unknown_error_code"`: provider callback で未知の OAuth error code を受けた回数（provider ラベル付き）

---

## 認可エラー方針（401 / 403）

認証・認可に関するステータスコードは次の方針で使い分けます。

| ステータス | 使う条件 | 代表例 |
| --- | --- | --- |
| `401 Unauthorized` | 認証情報がない、無効、期限切れ | `Authorization` ヘッダー未指定、無効トークン、期限切れトークン |
| `403 Forbidden` | 認証は成功しているが操作権限が不足 | 有効トークンだが管理者専用操作を実行した場合 |

`/api/v1/auth/logout` や `/api/v1/auth/refresh` でトークン検証に失敗した場合は `401` を返します。`403` は「誰かは特定できるが、その操作は許可しない」ケースで返します。

---

## OAuth認証フロー

<a id="callback-url-spec"></a>

### callback URL 仕様（全provider共通）

- callback path は `GET /api/v1/auth/{provider}/callback`
- provider 管理画面に登録する URL 形式は `https://<api-domain>/api/v1/auth/<provider>/callback`
- `http/https`・ホスト名・ポート・パス・末尾スラッシュまで完全一致が必要

`redirect_uri_mismatch` を最短で確認する手順は [クイックスタート](../getting-started.md#25-redirect_uri_mismatch-の最短確認5ステップ) を参照してください。失敗時の切り分けは [トラブルシューティング](../help/troubleshooting.md#認証エラー) へ接続してください。

### 1. 認証開始

ユーザーを認証エンドポイントにリダイレクト：

```
GET /api/v1/auth/google
```

### OAuth provider が無効な場合

対象: `GET /api/v1/auth/{provider}`（google / github / discord / x / linkedin / facebook / slack / twitch）

- 条件: 対象 provider の `*_CLIENT_ID` または `*_CLIENT_SECRET` が未設定
- 応答: `503 Service Unavailable`
- 例:

```json
{
  "detail": "OAuth provider 'google' is disabled. Configure GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET."
}
```

### 未対応 provider path の場合

- 条件: `GET /api/v1/auth/unknown` のように未対応 path を呼び出した場合
- 応答: `404 Not Found`（ルーティング未定義）

### 未知 provider 名のバリデーション時

- 条件: サポート対象外の provider 名が内部バリデーションへ渡された場合
- 応答: `400 Bad Request`
- 例:

```json
{
  "detail": "Unsupported OAuth provider 'unknown'."
}
```

### 2. コールバック

認証成功後、フロントエンドにリダイレクト：

```
https://your-frontend.com/auth/callback?access_token=xxx&refresh_token=xxx
```

### 3. トークン使用

APIリクエストにアクセストークンを含める：

```bash
curl -H "Authorization: Bearer <access_token>" \
  http://localhost:8000/api/v1/users/me
```

---

## トークンリフレッシュ

`/api/v1/auth/refresh` の内部再試行上限は `TOKEN_REFRESH_MAX_RETRIES`（既定: `3`）で設定できます。
一時的な DB 障害などで refresh 処理が失敗した場合、この上限まで再試行します。

```bash
POST /api/v1/auth/refresh
Content-Type: application/json

{
  "refresh_token": "your-refresh-token"
}
```

**レスポンス:**

```json
{
  "access_token": "new-access-token",
  "refresh_token": "new-refresh-token"
}
```

!!! info "トークンローテーション"
    リフレッシュ時に新しいリフレッシュトークンが発行されます。
    古いリフレッシュトークンは無効化されます。

### refresh失敗時エラー分類

`POST /api/v1/auth/refresh` で失敗した場合は、まずレスポンスコードと API ログを突き合わせて次の表で分類します。

| 症状 | APIレスポンス/ログ例 | 主な原因 | 初動対応 |
| --- | --- | --- | --- |
| トークン欠落・形式不正 | `422 Unprocessable Entity` / `refresh_token` の入力エラー | リクエストボディが欠落、JSONキー名の誤り | 送信 payload を `{ "refresh_token": "..." }` に統一して再試行 |
| 期限切れ・改ざん・失効済み | `401 Unauthorized` / `Could not validate credentials` | refresh token の期限切れ、署名不一致、logout/revoke 済み | 再ログインして新しい token pair を払い出し、古い token を破棄 |
| サーバー設定不整合 | `401 Unauthorized` が継続し複数ユーザーで再現 | `JWT_SECRET` 差し替え、環境差分、ローテーション手順漏れ | 稼働中コンテナの secret 読み込み元を確認し、全ノードの設定を揃える |
| 一時的な基盤障害 | `500 Internal Server Error` / DB・Valkey 接続失敗ログ | DB/Valkey 疎通不安定、依存サービス瞬断 | `docker compose ps` と各サービスログを確認し復旧後に再試行 |

詳細な切り分け手順は [`トラブルシューティング > 認証エラー`](../help/troubleshooting.md#認証エラー) を参照してください。

---

## ログアウト

```bash
POST /api/v1/auth/logout
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "refresh_token": "your-refresh-token"
}
```

**未認証時のレスポンス:**

```json
{
  "detail": {
    "code": "missing_bearer_token",
    "message": "Not authenticated"
  }
}
```

ステータスコード: `401 Unauthorized`

## エラーコード早見表（refresh/logout）

`api/app/auth/router.py` の実装定義に合わせた運用向け一覧です。

## エラーレスポンスの trace id 付与方針

障害調査で「利用者のエラー応答」と「APIログ」を突き合わせやすくするため、認証APIのエラーレスポンスには trace id を付与する方針で運用します。

- 対象: `4xx` / `5xx` のエラーレスポンス（`/refresh`・`/logout`・OAuth callback を含む）
- 返却形式: レスポンスヘッダー `X-Trace-Id` と JSON ボディ `trace_id` に同一値を設定
- 値の形式: UUID または同等の十分な一意性を持つ文字列
- 生成ルール: upstream（Ingress/Proxy）から request id が渡される場合はそれを優先し、ない場合は API 側で生成
- セキュリティ: `trace_id` にユーザー識別子・メールアドレス・トークンなどの機微情報を含めない

例（`401 Unauthorized`）:

```json
{
  "detail": "Could not validate credentials",
  "trace_id": "8b3f76c7-6d50-4f22-90f6-e4d8d7275d89"
}
```

運用メモ:

- 問い合わせ対応時は、利用者から `trace_id` と発生時刻（UTC/JST）をセットで受領する
- 既存クライアント互換のため、`detail` の意味は維持し、`trace_id` は追加情報として扱う
- 本節は「方針」定義です。実装を変更した場合は、この章と実装を同時に更新してください

### POST `/api/v1/auth/refresh`

| HTTP | 条件 | 原因の目安 | 対処の目安 |
|------|------|-----------|-----------|
| 200 | リフレッシュ成功 | トークンローテーション成功 | 新しい `access_token` / `refresh_token` を保存 |
| 401 | `Invalid or expired refresh token` | 期限切れ・失効済み・改ざん | 再ログインして新しいトークンを取得 |
| 401 | `User not found` | 紐づくユーザーが削除済み | セッションを破棄して再認証 |
| 422 | リクエスト検証エラー | `refresh_token` 未指定/型不正 | JSON ボディ形式を修正 |
| 429 | レート制限超過 | `/refresh` の短時間連続呼び出し | 間隔を空けて再試行（バックオフ推奨） |

例（型不一致による入力不正 / `422 Unprocessable Entity`）:

```json
{
  "detail": [
    {
      "type": "string_type",
      "loc": ["body", "refresh_token"],
      "msg": "Input should be a valid string",
      "input": 12345
    }
  ]
}
```

### POST `/api/v1/auth/logout`

| HTTP | 条件 | 原因の目安 | 対処の目安 |
|------|------|-----------|-----------|
| 200 | ログアウト成功 | リフレッシュトークン失効処理成功 | クライアント側トークンを削除 |
| 401 | 認証失敗 | `Authorization` ヘッダ欠落/無効 | 有効な Bearer トークンで再実行 |
| 422 | リクエスト検証エラー | `refresh_token` 未指定/型不正 | JSON ボディ形式を修正 |

例（`refresh_token` 欠落による入力不正 / `422 Unprocessable Entity`）:

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "refresh_token"],
      "msg": "Field required",
      "input": {}
    }
  ]
}
```

使い分け: `401` は未認証・無効トークン、`400` 系（本 API では主に `422`）は JSON 入力不正を示します。

### OAuth callback 共通（参考）

| HTTP | 条件 | 原因の目安 | 対処の目安 |
|------|------|-----------|-----------|
| 400 | `Invalid or expired state` | state 不一致/期限切れ | 認証フローを最初から再実行 |
| 400 | `OAuth callback failed: <error_code>` | provider が `error` を返却 | provider 側設定とエラー内容を確認（未知コードは metrics 監視） |
| 400 | `Failed to exchange code` | 認可コード交換失敗 | provider 設定・redirect URI を確認 |
| 400 | `Failed to get user info` | provider API 取得失敗 | provider 側障害・スコープ設定を確認 |
| 429 | レート制限超過 | callback/API 連打 | 一定時間待って再試行 |

### `state mismatch` の最小診断例

`GET /api/v1/auth/{provider}/callback` で `400 Invalid or expired state` が返った場合は、次の2コマンドで「再送」か「状態消失」かを先に切り分けます。

```bash
# 1) callback の重複実行有無を確認
docker compose logs api --since=30m | rg -n "Invalid state|/api/v1/auth/.*/callback"

# 2) state 保持先（Valkey）の異常有無を確認
docker compose logs valkey --since=30m | rg -n "error|timeout|OOM|evicted|fail"
```

判定目安:

- 同一時刻帯に callback ログが連続する: ブラウザ再送・プロキシ再試行を疑う
- callback は1回だが Valkey 側に異常ログがある: state 保持の欠損を疑う
- どちらも該当しない: `API_URL` / `FRONTEND_URL` の環境不一致を確認する

詳細フローは [`トラブルシューティング: state mismatch 診断フロー`](../help/troubleshooting.md#state-mismatch-flow) を参照してください。

!!! tip "維持ルール"
    ルータ変更時は `api/app/auth/router.py` の `HTTPException` と `@limiter.limit(...)` を更新し、本表も同時に更新してください。

---

## Mock OAuth（開発用）

`MOCK_OAUTH_ENABLED=1`の場合のみ利用可能：

### ログイン

```bash
GET /api/v1/auth/mock/login?user=alice&provider=google
```

**利用可能なユーザー:** `alice`, `bob`, `charlie`

**利用可能なプロバイダー:** `google`, `github`, `discord`, `x`, `linkedin`, `facebook`, `slack`, `twitch`

- `provider` は小文字正規化して判定（例: `GitHub` は `github` と同義）
- サポート外 provider は `400 Bad Request` と固定文言を返却

```json
{
  "detail": "Unsupported OAuth provider 'unknown'."
}
```

### ユーザー一覧

```bash
GET /api/v1/auth/mock/users
```

---

## 関連運用ドキュメント

- [Webhook設定ガイド: 署名検証失敗時の監査ログ項目](../guides/webhooks.md#署名検証失敗時の監査ログ項目)
