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

## 本番環境での注意点

!!! warning "リダイレクトURIの更新"
    本番環境では、リダイレクトURIを本番ドメインに更新してください：
    ```
    https://your-domain.com/api/v1/auth/google/callback
    https://your-domain.com/api/v1/auth/discord/callback
    ```

!!! tip "PKCE"
    Google OAuthはPKCE（Proof Key for Code Exchange）に対応しています。
    YESOD Authは自動的にPKCEを使用してセキュリティを強化します。
