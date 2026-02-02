# OAuth設定

## Google OAuth

### 1. Google Cloud Consoleでプロジェクト作成

1. [Google Cloud Console](https://console.cloud.google.com/)にアクセス
2. 新しいプロジェクトを作成
3. 「APIとサービス」→「認証情報」を開く

### 2. OAuth同意画面の設定

1. 「OAuth同意画面」を選択
2. ユーザータイプ：「外部」を選択
3. 必要な情報を入力：
    - アプリ名
    - ユーザーサポートメール
    - デベロッパーの連絡先情報

### 3. OAuth 2.0クライアントIDの作成

1. 「認証情報を作成」→「OAuth クライアント ID」
2. アプリケーションの種類：「ウェブアプリケーション」
3. 承認済みのリダイレクトURI：
    ```
    http://localhost:8000/api/v1/auth/google/callback
    ```
4. クライアントIDとシークレットを保存

### 4. シークレットファイルの設定

```bash
echo "your-client-id" > secrets/google_client_id.txt
echo "your-client-secret" > secrets/google_client_secret.txt
```

---

## GitHub OAuth

### 1. GitHub OAuth Appの作成

1. [GitHub Developer Settings](https://github.com/settings/developers)にアクセス
2. 「OAuth Apps」→「New OAuth App」をクリック
3. 必要な情報を入力：
    - Application name: アプリ名
    - Homepage URL: `http://localhost:8000`
    - Authorization callback URL: `http://localhost:8000/api/v1/auth/github/callback`
4. 「Register application」をクリック

### 2. クライアントシークレットの生成

1. 作成したアプリの設定ページを開く
2. 「Generate a new client secret」をクリック
3. Client IDとClient Secretをコピー

### 3. シークレットファイルの設定

```bash
echo "your-client-id" > secrets/github_client_id.txt
echo "your-client-secret" > secrets/github_client_secret.txt
```

!!! tip "スコープ"
    YESOD Authは`read:user`と`user:email`スコープを使用します。
    これにより、ユーザーの基本情報とメールアドレスを取得できます。

---

## Discord OAuth

### 1. Discord Developer Portalでアプリ作成

1. [Discord Developer Portal](https://discord.com/developers/applications)にアクセス
2. 「New Application」をクリック
3. アプリ名を入力して作成

### 2. OAuth2設定

1. 左メニューの「OAuth2」を選択
2. 「Redirects」に以下を追加：
    ```
    http://localhost:8000/api/v1/auth/discord/callback
    ```
3. 「Client ID」と「Client Secret」をコピー

### 3. シークレットファイルの設定

```bash
echo "your-client-id" > secrets/discord_client_id.txt
echo "your-client-secret" > secrets/discord_client_secret.txt
```

---

## X (Twitter) OAuth

### 1. Twitter Developer Portalでアプリ作成

1. [Twitter Developer Portal](https://developer.twitter.com/en/portal/dashboard)にアクセス
2. 「Projects & Apps」→「+ Add App」をクリック
3. アプリ名を入力して作成

### 2. OAuth 2.0設定

1. 作成したアプリの「Settings」を開く
2. 「User authentication settings」→「Set up」をクリック
3. 以下を設定：
    - App permissions: 「Read」を選択
    - Type of App: 「Web App, Automated App or Bot」を選択
    - Callback URI: `http://localhost:8000/api/v1/auth/x/callback`
    - Website URL: `http://localhost:8000`
4. 「Save」をクリック

### 3. クライアント認証情報の取得

1. 「Keys and tokens」タブを開く
2. 「OAuth 2.0 Client ID and Client Secret」セクションから認証情報をコピー

### 4. シークレットファイルの設定

```bash
echo "your-client-id" > secrets/x_client_id.txt
echo "your-client-secret" > secrets/x_client_secret.txt
```

!!! warning "メールアドレスについて"
    X APIはユーザーのメールアドレスを提供しません。
    YESOD Authでは、`{username}@x.yesod-auth.local`形式の仮メールアドレスを生成します。

!!! tip "PKCEは必須"
    X OAuth 2.0ではPKCEが必須です。YESOD Authは自動的にPKCEを使用します。

---

## LinkedIn OAuth

### 1. LinkedIn Developer Portalでアプリ作成

1. [LinkedIn Developer Portal](https://www.linkedin.com/developers/apps)にアクセス
2. 「Create app」をクリック
3. 必要な情報を入力：
    - App name: アプリ名
    - LinkedIn Page: 関連付けるLinkedInページ
    - App logo: アプリのロゴ画像
4. 「Create app」をクリック

### 2. OAuth 2.0設定

1. 作成したアプリの「Auth」タブを開く
2. 「OAuth 2.0 settings」セクションで以下を設定：
    - Authorized redirect URLs: `http://localhost:8000/api/v1/auth/linkedin/callback`
3. 「Update」をクリック

### 3. 製品の追加

1. 「Products」タブを開く
2. 「Sign In with LinkedIn using OpenID Connect」を選択して「Request access」をクリック
3. 承認されるまで待機（通常は即時承認）

### 4. クライアント認証情報の取得

1. 「Auth」タブに戻る
2. 「Application credentials」セクションから以下をコピー：
    - Client ID
    - Client Secret（「Show」をクリックして表示）

### 5. シークレットファイルの設定

```bash
echo "your-client-id" > secrets/linkedin_client_id.txt
echo "your-client-secret" > secrets/linkedin_client_secret.txt
```

!!! info "OpenID Connect"
    LinkedInはOpenID Connectを使用します。
    YESOD Authは`openid`、`profile`、`email`スコープを要求し、
    ユーザー情報は`/v2/userinfo`エンドポイントから取得します。

!!! tip "PKCE対応"
    LinkedIn OAuth 2.0はPKCEに対応しています。
    YESOD Authは自動的にPKCEを使用してセキュリティを強化します。

---

## Facebook OAuth

### 1. Facebook Developer Portalでアプリ作成

1. [Facebook for Developers](https://developers.facebook.com/)にアクセス
2. 「マイアプリ」→「アプリを作成」をクリック
3. アプリタイプ：「消費者」を選択
4. アプリ名を入力して作成

### 2. Facebookログインの設定

1. 作成したアプリのダッシュボードを開く
2. 「製品を追加」→「Facebookログイン」→「設定」をクリック
3. 「ウェブ」を選択
4. サイトURL: `http://localhost:8000`を入力

### 3. OAuth設定

1. 左メニューの「Facebookログイン」→「設定」を開く
2. 「有効なOAuthリダイレクトURI」に以下を追加：
    ```
    http://localhost:8000/api/v1/auth/facebook/callback
    ```
3. 「変更を保存」をクリック

### 4. クライアント認証情報の取得

1. 左メニューの「設定」→「ベーシック」を開く
2. 「アプリID」と「app secret」をコピー（「表示」をクリックして表示）

### 5. シークレットファイルの設定

```bash
echo "your-app-id" > secrets/facebook_client_id.txt
echo "your-app-secret" > secrets/facebook_client_secret.txt
```

!!! info "Graph API v18.0"
    YESOD AuthはFacebook Graph API v18.0を使用します。
    `email`と`public_profile`スコープを要求し、ユーザー情報を取得します。

!!! tip "PKCE対応"
    Facebook OAuth 2.0はPKCEに対応しています。
    YESOD Authは自動的にPKCEを使用してセキュリティを強化します。

---

## Slack OAuth

### 1. Slack APIでアプリ作成

1. [Slack API](https://api.slack.com/apps)にアクセス
2. 「Create New App」→「From scratch」をクリック
3. アプリ名とワークスペースを選択して作成

### 2. OAuth & Permissions設定

1. 左メニューの「OAuth & Permissions」を開く
2. 「Redirect URLs」に以下を追加：
    ```
    http://localhost:8000/api/v1/auth/slack/callback
    ```
3. 「Save URLs」をクリック

### 3. OpenID Connect設定

1. 左メニューの「OpenID Connect」を開く
2. 「Enable OpenID Connect」をオンにする

### 4. クライアント認証情報の取得

1. 左メニューの「Basic Information」を開く
2. 「App Credentials」セクションから以下をコピー：
    - Client ID
    - Client Secret

### 5. シークレットファイルの設定

```bash
echo "your-client-id" > secrets/slack_client_id.txt
echo "your-client-secret" > secrets/slack_client_secret.txt
```

!!! info "OpenID Connect"
    SlackはOpenID Connectを使用します。
    YESOD Authは`openid`、`email`、`profile`スコープを要求し、
    ユーザー情報は`/api/openid.connect.userInfo`エンドポイントから取得します。

---

## Twitch OAuth

### 1. Twitch Developer Consoleでアプリ作成

1. [Twitch Developer Console](https://dev.twitch.tv/console/apps)にアクセス
2. 「Register Your Application」をクリック
3. 必要な情報を入力：
    - Name: アプリ名
    - OAuth Redirect URLs: `http://localhost:8000/api/v1/auth/twitch/callback`
    - Category: 適切なカテゴリを選択
4. 「Create」をクリック

### 2. クライアント認証情報の取得

1. 作成したアプリの「Manage」をクリック
2. 「Client ID」をコピー
3. 「New Secret」をクリックしてClient Secretを生成・コピー

### 3. シークレットファイルの設定

```bash
echo "your-client-id" > secrets/twitch_client_id.txt
echo "your-client-secret" > secrets/twitch_client_secret.txt
```

!!! info "Helix API"
    YESOD AuthはTwitch Helix APIを使用します。
    `openid`と`user:read:email`スコープを要求し、
    ユーザー情報は`/helix/users`エンドポイントから取得します。

---

## 本番環境での注意点

!!! warning "リダイレクトURIの更新"
    本番環境では、リダイレクトURIを本番ドメインに更新してください：
    ```
    https://your-domain.com/api/v1/auth/google/callback
    https://your-domain.com/api/v1/auth/github/callback
    https://your-domain.com/api/v1/auth/discord/callback
    https://your-domain.com/api/v1/auth/x/callback
    https://your-domain.com/api/v1/auth/linkedin/callback
    https://your-domain.com/api/v1/auth/facebook/callback
    https://your-domain.com/api/v1/auth/slack/callback
    https://your-domain.com/api/v1/auth/twitch/callback
    ```

!!! tip "PKCE"
    Google OAuth、GitHub OAuth、X OAuth、LinkedIn OAuth、Facebook OAuthはPKCE（Proof Key for Code Exchange）に対応しています。
    YESOD Authは自動的にPKCEを使用してセキュリティを強化します。
