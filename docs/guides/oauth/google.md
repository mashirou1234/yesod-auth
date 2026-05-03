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

## 3.1 Callback URL の登録値

Google Cloud Console には、利用環境ごとに次の callback URL を登録します。
本番では `localhost` を残さず、API の公開ドメインに置き換えてください。

| 環境 | 登録する callback URL | 確認先 |
|------|------------------------|--------|
| ローカル開発 | `http://localhost:8000/api/v1/auth/google/callback` | Google Cloud Console の「承認済みのリダイレクト URI」 |
| セルフホスト本番 | `https://<api-domain>/api/v1/auth/google/callback` | 本番 OAuth クライアントの「承認済みのリダイレクト URI」 |

開始エンドポイントは `GET /api/v1/auth/google` です。callback URL を直接開かず、必ず開始エンドポイントから Google 認可画面へ遷移することを確認してください。
共通の確認順は [OAuth設定: Callback確認の共通チェックリスト](index.md#oauth-callback-checklist) を参照してください。

## 4. シークレットファイルの設定

```bash
echo "your-client-id" > secrets/google_client_id.txt
echo "your-client-secret" > secrets/google_client_secret.txt
```

## 4.1 検証環境と本番環境の差分（Google向け）

Google OAuth は「同じ provider」でも、検証環境と本番環境で登録値を分けて管理すると事故を減らせます。

| 観点 | 検証環境（staging / localhost） | 本番環境（production） |
|------|----------------------------------|------------------------|
| Redirect URI | `http://localhost:8000/api/v1/auth/google/callback` または `https://stg.<domain>/api/v1/auth/google/callback` | `https://<domain>/api/v1/auth/google/callback` |
| Callback 再確認 | Google Cloud Console の検証用 OAuth クライアントで、実際に使う検証 URL がスキーム・ホスト・ポート・パス・末尾 `/` まで完全一致していることを確認 | 本番用 OAuth クライアントで、`localhost` や staging URL が残っていないことを確認 |
| OAuth同意画面の公開状態 | Testing（検証ユーザーのみ） | In production（一般ユーザー向け） |
| テストユーザー | Google Cloud Console の Test users に開発メンバーを登録 | 原則不要（一般公開時） |
| OAuth 実行モード | ローカル疎通だけなら `MOCK_OAUTH_ENABLED=1`、Google 実OAuth検証では `MOCK_OAUTH_ENABLED=0` に切り替える | `MOCK_OAUTH_ENABLED=0` を本番構成で確認 |
| クライアントID/Secret | 検証用を発行して `secrets/google_client_*.txt` に設定し、`docker compose config` で secret mount を確認 | 本番用を別発行し、デプロイ先の secret に設定し、環境変数直書きより secret store を優先 |
| API URL / CORS | `API_URL` と `FRONTEND_URL` を検証ドメインに合わせる | `API_URL` と `FRONTEND_URL` を本番ドメインに合わせる |

!!! warning "混在防止"
    検証用クライアントで本番URLを許可したり、本番クライアントを検証環境へ流用しないでください。`redirect_uri_mismatch` と意図しないログイン失敗の主因になります。

## 5. `redirect_uri_mismatch` の切り分け

Google 側で `Error 400: redirect_uri_mismatch` が表示された場合は、以下を順に確認します。

1. 実際に callback を受ける URL を環境ごとに固定
    - ローカル開発: `http://localhost:8000/api/v1/auth/google/callback`
    - 検証環境: `https://stg.<your-domain>/api/v1/auth/google/callback`
    - 本番運用: `https://<your-domain>/api/v1/auth/google/callback`
2. Google Cloud Console の OAuth クライアント設定を再確認
    - 検証環境は検証用クライアント、本番環境は本番用クライアントを開くこと
    - 「承認済みのリダイレクト URI」に上記 URL が **完全一致** で登録されていること
    - スキーム (`http`/`https`)、ホスト、ポート、パス、末尾 `/` の有無が一致していること
3. アプリ側の実行モードと secret 配置を確認
    - 実 Google OAuth を検証する環境では `MOCK_OAUTH_ENABLED=0` になっていること
    - `google_client_id` / `google_client_secret` が対象環境の値で、`secrets/google_client_*.txt` またはデプロイ先の secret に配置されていること
    - `docker compose config | rg -n "MOCK_OAUTH_ENABLED|google_client_(id|secret)"` で Compose 側の反映を確認すること
4. アプリ側 URL 設定を確認
    - `API_URL` が実際の公開 URL と一致していること
    - reverse proxy 配下では `X-Forwarded-Proto` が正しく引き継がれていること
5. 再現確認
    - 必ず `GET /api/v1/auth/google` から開始し、古いタブを再利用しない
    - 失敗時は API ログで callback URL を確認する

```bash
docker compose config | rg -n "MOCK_OAUTH_ENABLED|google_client_(id|secret)"
docker compose logs api --since=30m | rg -n "auth/google|callback|redirect_uri|mismatch"
```

`Invalid or expired state` が同時に発生する場合は、[トラブルシューティング](../../help/troubleshooting.md#state-mismatch-flow) の診断フローも併せて確認してください。

共通の callback 確認手順は [OAuth設定の共通チェックリスト](index.md#oauth-callback-checklist) を先に参照してください。

### 5.1 callback mismatch 早見表（Google）

| 症状 | まず確認する差分 | 修正先 |
| --- | --- | --- |
| `http://` で登録しているのに本番は `https://` | スキーム不一致 | Google Cloud Console の「承認済みのリダイレクト URI」を `https://.../callback` に修正 |
| `api.example.com` ではなく `example.com` で登録している | ホスト不一致 | 実際に API が公開されているホスト名へ統一 |
| `:8000` 付きで登録している（本番） | ポート不一致 | 本番 callback URI から開発用ポートを除外 |
| `.../callback/` で登録している | パス末尾スラッシュ不一致 | `.../callback`（末尾 `/` なし）へ修正 |
| API_URL は正しいが mismatch が続く | 逆プロキシで `X-Forwarded-Proto` が未伝搬 | Nginx/Ingress 側で `X-Forwarded-Proto=https` を API へ引き継ぐ |

最終確認コマンド（Google callback 観点）:

```bash
docker compose logs api --since=30m | rg -n "auth/google|callback|redirect_uri_mismatch|X-Forwarded-Proto"
```

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
