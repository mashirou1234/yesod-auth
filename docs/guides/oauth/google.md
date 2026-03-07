# Google OAuth

## 1. Google Cloud Consoleでプロジェクト作成

1. [Google Cloud Console](https://console.cloud.google.com/){:target="_blank"}にアクセス
2. 新しいプロジェクトを作成
3. 「APIとサービス」→「認証情報」を開く

## 2. OAuth同意画面の設定

1. 「OAuth同意画面」を選択
2. ユーザータイプ：「外部」を選択
3. 必要な情報を入力：
    - アプリ名
    - ユーザーサポートメール
    - デベロッパーの連絡先情報

## 3. OAuth 2.0クライアントIDの作成

1. 「認証情報を作成」→「OAuth クライアント ID」
2. アプリケーションの種類：「ウェブアプリケーション」
3. 承認済みのリダイレクトURI：
    ```
    http://localhost:8000/api/v1/auth/google/callback
    ```
4. クライアントIDとシークレットを保存

## 4. シークレットファイルの設定

```bash
echo "your-client-id" > secrets/google_client_id.txt
echo "your-client-secret" > secrets/google_client_secret.txt
```

## 5. `redirect_uri_mismatch` の切り分け

Google 側で `Error 400: redirect_uri_mismatch` が表示された場合は、以下を順に確認します。

1. 実際に callback を受ける URL を確認
    - ローカル開発: `http://localhost:8000/api/v1/auth/google/callback`
    - 本番運用: `https://<your-domain>/api/v1/auth/google/callback`
2. Google Cloud Console の OAuth クライアント設定を確認
    - 「承認済みのリダイレクト URI」に上記 URL が **完全一致** で登録されていること
    - スキーム (`http`/`https`)、ホスト、ポート、パス、末尾 `/` の有無が一致していること
3. アプリ側設定を確認
    - `API_URL` が実際の公開 URL と一致していること
    - reverse proxy 配下では `X-Forwarded-Proto` が正しく引き継がれていること
4. 再現確認
    - 必ず `GET /api/v1/auth/google` から開始し、古いタブを再利用しない
    - 失敗時は API ログで callback URL を確認する

```bash
docker compose logs api --since=30m | rg -n "auth/google|callback|redirect_uri|mismatch"
```

`Invalid or expired state` が同時に発生する場合は、[トラブルシューティング](../../help/troubleshooting.md#state-mismatch-flow) の診断フローも併せて確認してください。

## 共通チェック観点の適用例

- [x] Callback URL
  - [x] ローカル: `http://localhost:8000/api/v1/auth/google/callback`
  - [x] 本番: `https://<your-domain>/api/v1/auth/google/callback`
- [x] Scope
  - [x] 使用スコープ: `openid email profile`
  - [x] 不足時の症状: メールアドレス未取得でユーザー同定に失敗する
- [x] Secrets
  - [x] `secrets/google_client_id.txt`
  - [x] `secrets/google_client_secret.txt`
- [x] Test
  - [x] `curl -I "http://localhost:8000/api/v1/auth/google/login"` が `302` を返し、Google認可画面へ遷移する

## 技術仕様

| 項目 | 値 |
|------|-----|
| 認可エンドポイント | `https://accounts.google.com/o/oauth2/v2/auth` |
| トークンエンドポイント | `https://oauth2.googleapis.com/token` |
| ユーザー情報エンドポイント | `https://www.googleapis.com/oauth2/v2/userinfo` |
| スコープ | `openid email profile` |
| PKCE | ✅ 対応 |
| OpenID Connect | ✅ 対応 |
