# 要件: LinkedIn OAuth 2.0認証プロバイダー

## 概要
LinkedIn OAuth 2.0（Sign In with LinkedIn using OpenID Connect）を使用した認証プロバイダーを追加する。

## ユーザーストーリー

### US-1: LinkedInでログイン
ユーザーとして、LinkedInアカウントでログインしたい。
これにより、新しいアカウントを作成せずにサービスを利用できる。

**受け入れ条件:**
- [ ] `/auth/linkedin`エンドポイントでLinkedIn認証フローを開始できる
- [ ] LinkedInで認証後、コールバックでJWTトークンが発行される
- [ ] ユーザー情報（名前、メール、プロフィール画像）が取得される
- [ ] 既存ユーザーの場合はログイン、新規の場合はアカウント作成

### US-2: PKCEによるセキュリティ強化
セキュリティのため、PKCEを使用した認証フローを実装する。

**受け入れ条件:**
- [ ] code_verifierとcode_challengeが生成される
- [ ] 認証リクエストにcode_challengeが含まれる
- [ ] トークン交換時にcode_verifierが送信される

## 技術要件

### LinkedIn OAuth 2.0 (OpenID Connect)
- Authorization URL: `https://www.linkedin.com/oauth/v2/authorization`
- Token URL: `https://www.linkedin.com/oauth/v2/accessToken`
- UserInfo URL: `https://api.linkedin.com/v2/userinfo`
- スコープ: `openid profile email`
- PKCE: 対応

### 注意事項
- LinkedInはOpenID Connectを使用（`openid`スコープが必須）
- UserInfo APIは標準的なOIDCレスポンスを返す
- プロフィール画像URLは`picture`フィールドで取得
