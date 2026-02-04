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

## 技術仕様

| 項目 | 値 |
|------|-----|
| 認可エンドポイント | `https://accounts.google.com/o/oauth2/v2/auth` |
| トークンエンドポイント | `https://oauth2.googleapis.com/token` |
| ユーザー情報エンドポイント | `https://www.googleapis.com/oauth2/v2/userinfo` |
| スコープ | `openid email profile` |
| PKCE | ✅ 対応 |
| OpenID Connect | ✅ 対応 |
