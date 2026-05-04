# LinkedIn OAuth

## 1. LinkedIn Developer Portalでアプリ作成

1. [LinkedIn Developer Portal](https://www.linkedin.com/developers/apps){:target="_blank"}にアクセス
2. 「Create app」をクリック
3. 必要な情報を入力：
    - App name: アプリ名
    - LinkedIn Page: 関連付けるLinkedInページ
    - App logo: アプリのロゴ画像
4. 「Create app」をクリック

## 2. OAuth 2.0設定

1. 作成したアプリの「Auth」タブを開く
2. 「OAuth 2.0 settings」セクションで以下を設定：
    - Authorized redirect URLs: `http://localhost:8000/api/v1/auth/linkedin/callback`
3. 「Update」をクリック

## 3. 製品の追加

1. 「Products」タブを開く
2. 「Sign In with LinkedIn using OpenID Connect」を選択して「Request access」をクリック
3. 承認されるまで待機（通常は即時承認）

## 4. クライアント認証情報の取得

1. 「Auth」タブに戻る
2. 「Application credentials」セクションから以下をコピー：
    - Client ID
    - Client Secret（「Show」をクリックして表示）

## 5. シークレットファイルの設定

```bash
echo "your-client-id" > secrets/linkedin_client_id.txt
echo "your-client-secret" > secrets/linkedin_client_secret.txt
```

!!! info "OpenID Connect"
    LinkedInはOpenID Connectを使用します。
    YESOD Authは`openid`、`profile`、`email`スコープを要求し、
    ユーザー情報は`/v2/userinfo`エンドポイントから取得します。

## 6. 必要権限（scope）一覧

YESOD Auth の LinkedIn ログインで要求する最小 scope は次の 3 つです。

| scope | 用途 | 未付与時の主な症状 |
|------|------|------------------|
| `openid` | OpenID Connect の ID トークン取得 | コールバック後に認証が完了しない |
| `profile` | 表示名などの基本プロフィール取得 | `display_name` が空、またはプロフィール取得に失敗 |
| `email` | メールアドレス取得 | メール未取得でユーザー作成/照合に失敗 |

!!! warning "scopeは削らない"
    `openid profile email` の 3 つはセットで必要です。
    一部のみを要求すると、`/v2/userinfo` から必要情報を取得できずログイン失敗の原因になります。

### scope不足時の re-authorization

LinkedIn 側で `Sign In with LinkedIn using OpenID Connect` が未承認、または `openid profile email` の一部だけで認可した場合は、既存セッションを破棄して再認可します。

1. LinkedIn Developer Portal で対象アプリの Product と Authorized redirect URLs を確認する
2. クライアント側の token pair を破棄する
3. `GET /api/v1/auth/linkedin` から認可をやり直す
4. 失敗時は API ログで `linkedin|userinfo|scope|email` を確認する

```bash
docker compose logs api --since=30m | rg -n "linkedin|userinfo|scope|email"
```

## 技術仕様

| 項目 | 値 |
|------|-----|
| 認可エンドポイント | `https://www.linkedin.com/oauth/v2/authorization` |
| トークンエンドポイント | `https://www.linkedin.com/oauth/v2/accessToken` |
| ユーザー情報エンドポイント | `https://api.linkedin.com/v2/userinfo` |
| スコープ | `openid profile email` |
| PKCE | ✅ 対応 |
| OpenID Connect | ✅ 対応 |
