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

## 本番環境での注意点

!!! warning "リダイレクトURIの更新"
    本番環境では、リダイレクトURIを本番ドメインに更新してください：
    ```
    https://your-domain.com/api/v1/auth/google/callback
    https://your-domain.com/api/v1/auth/github/callback
    https://your-domain.com/api/v1/auth/discord/callback
    https://your-domain.com/api/v1/auth/x/callback
    ```

!!! tip "PKCE"
    Google OAuth、GitHub OAuth、X OAuthはPKCE（Proof Key for Code Exchange）に対応しています。
    YESOD Authは自動的にPKCEを使用してセキュリティを強化します。
