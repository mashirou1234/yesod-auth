# Facebook OAuth

## 1. Facebook Developer Portalでアプリ作成

1. [Facebook for Developers](https://developers.facebook.com/){:target="_blank"}にアクセス
2. 「マイアプリ」→「アプリを作成」をクリック
3. アプリタイプ：「消費者」を選択
4. アプリ名を入力して作成

## 2. Facebookログインの設定

1. 作成したアプリのダッシュボードを開く
2. 「製品を追加」→「Facebookログイン」→「設定」をクリック
3. 「ウェブ」を選択
4. サイトURL: `http://localhost:8000`を入力

## 3. OAuth設定

1. 左メニューの「Facebookログイン」→「設定」を開く
2. 「有効なOAuthリダイレクトURI」に以下を追加：
    ```
    http://localhost:8000/api/v1/auth/facebook/callback
    ```
3. 「変更を保存」をクリック

## 4. クライアント認証情報の取得

1. 左メニューの「設定」→「ベーシック」を開く
2. 「アプリID」と「app secret」をコピー（「表示」をクリックして表示）

## 5. シークレットファイルの設定

```bash
echo "your-app-id" > secrets/facebook_client_id.txt
echo "your-app-secret" > secrets/facebook_client_secret.txt
```

!!! info "Graph API v18.0"
    YESOD Authは[Facebook Graph API v18.0](https://developers.facebook.com/docs/graph-api/){:target="_blank"}を使用します。
    `email`と`public_profile`スコープを要求し、ユーザー情報を取得します。

## 技術仕様

| 項目 | 値 |
|------|-----|
| 認可エンドポイント | `https://www.facebook.com/v18.0/dialog/oauth` |
| トークンエンドポイント | `https://graph.facebook.com/v18.0/oauth/access_token` |
| ユーザー情報エンドポイント | `https://graph.facebook.com/v18.0/me` |
| スコープ | `email public_profile` |
| PKCE | ✅ 対応 |
| OpenID Connect | ❌ 非対応 |
