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

## 技術仕様

| 項目 | 値 |
|------|-----|
| 認可エンドポイント | `https://www.linkedin.com/oauth/v2/authorization` |
| トークンエンドポイント | `https://www.linkedin.com/oauth/v2/accessToken` |
| ユーザー情報エンドポイント | `https://api.linkedin.com/v2/userinfo` |
| スコープ | `openid profile email` |
| PKCE | ✅ 対応 |
| OpenID Connect | ✅ 対応 |
