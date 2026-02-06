# X (Twitter) OAuth

## 1. Twitter Developer Portalでアプリ作成

1. [Twitter Developer Portal](https://developer.twitter.com/en/portal/dashboard){:target="_blank"}にアクセス
2. 「Projects & Apps」→「+ Add App」をクリック
3. アプリ名を入力して作成

## 2. OAuth 2.0設定

!!! warning "HTTPS必須"
    X OAuth 2.0ではCallback URIとWebsite URLにHTTPSが必須です。
    ローカル開発では[ngrok](https://ngrok.com/)などのトンネリングサービスを使用してください。
    
    ```bash
    # 1. ngrokのAuthtokenを取得してsecretsに保存
    echo "your-ngrok-authtoken" > secrets/ngrok_authtoken.txt
    
    # 2. ngrokを起動
    docker compose --profile default --profile ngrok up
    ```
    
    ngrokが発行するURL（例: `https://abc123.ngrok-free.app`）を使用します。
    `http://localhost:4040`でngrokダッシュボードを開いてURLを確認できます。

1. 作成したアプリの「Settings」を開く
2. 「User authentication settings」→「Set up」をクリック
3. 以下を設定：
    - App permissions: 「Read」を選択
    - Type of App: 「Web App, Automated App or Bot」を選択
    - Callback URI: `https://<ngrok-url>/api/v1/auth/x/callback`
    - Website URL: `https://<ngrok-url>`
4. 「Save」をクリック

## 3. クライアント認証情報の取得

1. 「Keys and tokens」タブを開く
2. 「OAuth 2.0 Client ID and Client Secret」セクションから認証情報をコピー

!!! note "必要な認証情報"
    YESOD Authで必要なのは「OAuth 2.0 Client ID」と「Client Secret」のみです。
    
    以下のトークンは**不要**です：
    
    - API Key / API Key Secret（OAuth 1.0a用）
    - Bearer Token（App-only認証用）
    - Access Token / Access Token Secret（OAuth 1.0a用）

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

## 技術仕様

| 項目 | 値 |
|------|-----|
| 認可エンドポイント | `https://twitter.com/i/oauth2/authorize` |
| トークンエンドポイント | `https://api.twitter.com/2/oauth2/token` |
| ユーザー情報エンドポイント | `https://api.twitter.com/2/users/me` |
| スコープ | `users.read tweet.read` |
| PKCE | ✅ 必須 |
| OpenID Connect | ❌ 非対応 |
