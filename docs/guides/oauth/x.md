# X (Twitter) OAuth

## 1. Twitter Developer Portalでアプリ作成

1. [Twitter Developer Portal](https://developer.twitter.com/en/portal/dashboard){:target="_blank"}にアクセス
2. 「Projects & Apps」→「+ Add App」をクリック
3. アプリ名を入力して作成

## 2. OAuth 2.0設定

1. 作成したアプリの「Settings」を開く
2. 「User authentication settings」→「Set up」をクリック
3. 以下を設定：
    - App permissions: 「Read」を選択
    - Type of App: 「Web App, Automated App or Bot」を選択
    - Callback URI: `http://localhost:8000/api/v1/auth/x/callback`
    - Website URL: `http://localhost:8000`
4. 「Save」をクリック

## 3. クライアント認証情報の取得

1. 「Keys and tokens」タブを開く
2. 「OAuth 2.0 Client ID and Client Secret」セクションから認証情報をコピー

## 4. シークレットファイルの設定

```bash
echo "your-client-id" > secrets/x_client_id.txt
echo "your-client-secret" > secrets/x_client_secret.txt
```

!!! warning "メールアドレスについて"
    X APIはユーザーのメールアドレスを提供しません。
    YESOD Authでは、`{username}@x.yesod-auth.local`形式の仮メールアドレスを生成します。

!!! tip "PKCEは必須"
    X OAuth 2.0ではPKCEが必須です。YESOD Authは自動的にPKCEを使用します。

## よくあるエラーレスポンス例

### `401 Unauthorized` / `invalid_client`

X の `client_id` / `client_secret` が未設定または不正な場合に発生します。

```json
{
  "detail": "OAuth callback failed: invalid_client"
}
```

確認ポイント:

- `secrets/x_client_id.txt` と `secrets/x_client_secret.txt` の値
- X Developer Portal 側での Client Secret 再発行有無
- Callback URI が `http://localhost:8000/api/v1/auth/x/callback` と一致しているか

### `400 Bad Request` / `invalid_request`

認可コードの期限切れや callback パラメータ不整合で発生します。

```json
{
  "detail": "OAuth callback failed: invalid_request"
}
```

確認ポイント:

- 認証開始 (`/api/v1/auth/x`) からやり直す
- ブラウザ戻る操作や callback URL の再実行を避ける
- `API_URL` と実アクセス先ホスト/スキームの一致

復旧時は古い callback URL を再読み込みせず、必ず次の固定順で再取得します。

1. 古い認可タブを閉じる
2. `GET /api/v1/auth/x` から新しい `state` と PKCE verifier を発行する
3. X の認可画面で同意する
4. callback 後に API ログで `auth/x|invalid_request|state` が再発していないことを確認する

```bash
docker compose logs api --since=30m | rg -n "auth/x|invalid_request|Invalid state|callback"
```

### `400 Bad Request` / `Failed to exchange code`

認可コード交換に失敗した場合に発生します。X 側の callback URL 設定不一致
（`redirect_uri_mismatch`）でも同じ API レスポンスになります。

```json
{
  "detail": "Failed to exchange code"
}
```

確認ポイント:

- X Developer Portal の Callback URI が `.../api/v1/auth/x/callback` と完全一致しているか
- API 側の `API_URL` / リバースプロキシ設定が実アクセス先と一致しているか
- 詳細切り分けは [トラブルシューティング: redirect_uri_mismatch](../../help/troubleshooting.md#redirect_uri_mismatch正規化差分の診断) を参照

## 技術仕様

| 項目 | 値 |
|------|-----|
| 認可エンドポイント | `https://twitter.com/i/oauth2/authorize` |
| トークンエンドポイント | `https://api.twitter.com/2/oauth2/token` |
| ユーザー情報エンドポイント | `https://api.twitter.com/2/users/me` |
| スコープ | `users.read tweet.read offline.access` |
| 補足 | `offline.access` は refresh token を受け取り長期セッションを維持するために必要 |
| PKCE | ✅ 必須 |
| OpenID Connect | ❌ 非対応 |
