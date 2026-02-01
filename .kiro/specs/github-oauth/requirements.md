# 要件ドキュメント

## 概要

YESOD AuthにGitHub OAuth 2.0認証プロバイダーを追加し、開発者向けの認証オプションを提供する。既存のGoogle/Discord OAuthと同様のパターンで実装し、PKCEをサポートする。

## 用語集

- **GitHub_OAuth**: GitHub OAuth 2.0認証プロバイダークラス
- **PKCE**: Proof Key for Code Exchange - 認可コード横取り攻撃を防ぐセキュリティ拡張
- **Code_Verifier**: PKCEで使用するランダムな文字列
- **Code_Challenge**: Code_Verifierから生成されるハッシュ値
- **OAuth_State**: CSRF攻撃を防ぐためのランダムなトークン
- **Access_Token**: GitHubリソースにアクセスするためのトークン
- **User_Info**: GitHubから取得するユーザー情報（ID、メール、名前、アバター）

## 要件

### 要件 1: GitHub OAuth認可URLの生成

**ユーザーストーリー:** 開発者として、GitHubアカウントでログインを開始したい。そうすることで、GitHubの認証情報を使ってYESOD Authにアクセスできる。

#### 受け入れ基準

1. WHEN ユーザーが`/auth/github`エンドポイントにアクセスした時、THE GitHub_OAuth SHALL GitHubの認可URLにリダイレクトする
2. WHEN 認可URLを生成する時、THE GitHub_OAuth SHALL client_id、redirect_uri、scope、stateパラメータを含める
3. WHEN PKCEが有効な時、THE GitHub_OAuth SHALL code_challengeとcode_challenge_methodパラメータを含める
4. THE GitHub_OAuth SHALL scopeに`read:user`と`user:email`を含める
5. THE GitHub_OAuth SHALL stateをValkeyに保存してCSRF攻撃を防ぐ

### 要件 2: 認可コードの交換

**ユーザーストーリー:** 開発者として、GitHubでの認証後にアクセストークンを取得したい。そうすることで、GitHubのユーザー情報を取得できる。

#### 受け入れ基準

1. WHEN GitHubからコールバックを受信した時、THE GitHub_OAuth SHALL stateを検証する
2. IF stateが無効または期限切れの場合、THEN THE GitHub_OAuth SHALL エラーを返す
3. WHEN 認可コードを受信した時、THE GitHub_OAuth SHALL GitHubのトークンエンドポイントでアクセストークンと交換する
4. WHEN PKCEが使用されている時、THE GitHub_OAuth SHALL code_verifierをトークンリクエストに含める
5. IF トークン交換が失敗した場合、THEN THE GitHub_OAuth SHALL 適切なエラーメッセージを返す

### 要件 3: ユーザー情報の取得

**ユーザーストーリー:** 開発者として、GitHubのプロフィール情報を使ってYESOD Authアカウントを作成・更新したい。

#### 受け入れ基準

1. WHEN アクセストークンを取得した時、THE GitHub_OAuth SHALL GitHubのユーザー情報APIを呼び出す
2. THE GitHub_OAuth SHALL ユーザーID、ログイン名、表示名、アバターURLを取得する
3. WHEN ユーザーのメールがプライベートの場合、THE GitHub_OAuth SHALL `/user/emails`エンドポイントからプライマリメールを取得する
4. IF ユーザー情報の取得が失敗した場合、THEN THE GitHub_OAuth SHALL エラーを返す

### 要件 4: 既存システムとの統合

**ユーザーストーリー:** システム管理者として、GitHub OAuthを既存のOAuth基盤に統合したい。そうすることで、一貫した認証体験を提供できる。

#### 受け入れ基準

1. THE GitHub_OAuth SHALL 既存のGoogleOAuth、DiscordOAuthクラスと同じインターフェースを持つ
2. THE GitHub_OAuth SHALL `get_authorize_url()`、`exchange_code()`、`get_user_info()`メソッドを実装する
3. WHEN 新規ユーザーがGitHubでログインした時、THE System SHALL 新しいユーザーアカウントを作成する
4. WHEN 既存ユーザーがGitHubでログインした時、THE System SHALL OAuthアカウントをリンクする
5. THE System SHALL GitHubログインを監査ログに記録する

### 要件 5: 設定管理

**ユーザーストーリー:** システム管理者として、GitHub OAuthの認証情報を安全に管理したい。

#### 受け入れ基準

1. THE System SHALL GITHUB_CLIENT_IDをDocker Secretsまたは環境変数から読み込む
2. THE System SHALL GITHUB_CLIENT_SECRETをDocker Secretsまたは環境変数から読み込む
3. IF 認証情報が設定されていない場合、THEN THE System SHALL GitHub OAuthエンドポイントを無効化する

### 要件 6: Mock OAuthサポート

**ユーザーストーリー:** 開発者として、実際のGitHub認証なしでテストしたい。そうすることで、開発とテストを効率化できる。

#### 受け入れ基準

1. WHEN MOCK_OAUTH_ENABLEDが有効な時、THE System SHALL モックGitHubログインエンドポイントを提供する
2. THE MockOAuthUser SHALL `to_github_format()`メソッドを持つ
3. THE Mock_OAuth SHALL GitHubフォーマットのユーザー情報を返す（id、login、name、avatar_url、email）

### 要件 7: エラーハンドリング

**ユーザーストーリー:** ユーザーとして、認証エラーが発生した時に適切なフィードバックを受けたい。

#### 受け入れ基準

1. IF GitHubがエラーを返した場合、THEN THE System SHALL エラーの詳細をログに記録する
2. IF ネットワークエラーが発生した場合、THEN THE System SHALL 適切なHTTPステータスコードを返す
3. WHEN 認証が失敗した時、THE System SHALL 監査ログに失敗を記録する
4. THE System SHALL ユーザーに安全なエラーメッセージを表示する（内部詳細を漏らさない）
