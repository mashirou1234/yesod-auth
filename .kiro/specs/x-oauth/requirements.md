# 要件ドキュメント: X (Twitter) OAuth 2.0

## 概要

YESOD AuthにX (Twitter) OAuth 2.0認証プロバイダーを追加し、ソーシャルログインオプションを拡充する。PKCEをサポートする。

## 用語集

- **X_OAuth**: X OAuth 2.0認証プロバイダークラス
- **PKCE**: Proof Key for Code Exchange
- **Bearer_Token**: Xリソースにアクセスするためのトークン

## 要件

### 要件 1: X OAuth認可URLの生成

**ユーザーストーリー:** ユーザーとして、Xアカウントでログインを開始したい。

#### 受け入れ基準

1. WHEN ユーザーが`/auth/x`エンドポイントにアクセスした時、THE X_OAuth SHALL Xの認可URLにリダイレクトする
2. WHEN 認可URLを生成する時、THE X_OAuth SHALL client_id、redirect_uri、scope、stateパラメータを含める
3. WHEN PKCEが有効な時、THE X_OAuth SHALL code_challengeとcode_challenge_methodパラメータを含める
4. THE X_OAuth SHALL scopeに`tweet.read`、`users.read`、`offline.access`を含める
5. THE X_OAuth SHALL stateをValkeyに保存してCSRF攻撃を防ぐ

### 要件 2: 認可コードの交換

**ユーザーストーリー:** ユーザーとして、Xでの認証後にアクセストークンを取得したい。

#### 受け入れ基準

1. WHEN Xからコールバックを受信した時、THE X_OAuth SHALL stateを検証する
2. IF stateが無効または期限切れの場合、THEN THE X_OAuth SHALL エラーを返す
3. WHEN 認可コードを受信した時、THE X_OAuth SHALL Xのトークンエンドポイントでアクセストークンと交換する
4. WHEN PKCEが使用されている時、THE X_OAuth SHALL code_verifierをトークンリクエストに含める
5. THE X_OAuth SHALL Basic認証でclient_idとclient_secretを送信する

### 要件 3: ユーザー情報の取得

**ユーザーストーリー:** ユーザーとして、Xのプロフィール情報を使ってYESOD Authアカウントを作成・更新したい。

#### 受け入れ基準

1. WHEN アクセストークンを取得した時、THE X_OAuth SHALL Xのユーザー情報APIを呼び出す
2. THE X_OAuth SHALL ユーザーID、ユーザー名、表示名、プロフィール画像URLを取得する
3. NOTE: Xはメールアドレスを返さないため、ユーザー名ベースの仮メールを生成する

### 要件 4: 既存システムとの統合

#### 受け入れ基準

1. THE X_OAuth SHALL 既存のOAuthクラスと同じインターフェースを持つ
2. THE System SHALL Xログインを監査ログに記録する
3. THE System SHALL Webhookイベントを発行する

### 要件 5: 設定管理

#### 受け入れ基準

1. THE System SHALL X_CLIENT_IDをDocker Secretsまたは環境変数から読み込む
2. THE System SHALL X_CLIENT_SECRETをDocker Secretsまたは環境変数から読み込む

### 要件 6: Mock OAuthサポート

#### 受け入れ基準

1. THE MockOAuthUser SHALL `to_x_format()`メソッドを持つ
2. THE Mock_OAuth SHALL Xフォーマットのユーザー情報を返す（id、username、name、profile_image_url）
