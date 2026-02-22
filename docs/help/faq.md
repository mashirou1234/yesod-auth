# FAQ

## 一般

### YESOD Authとは？

YESOD Authは、OAuth 2.0認証を簡単に実装するためのオープンソース認証基盤です。
Google、GitHub、Discord、X (Twitter)、LinkedIn、Facebook、Slack、Twitchの8プロバイダーに対応し、
Webhook連携機能やOIDC互換ID Token発行機能も備えています。

### ライセンスは？

MIT Licenseです。商用利用も可能です。

---

## 認証

### 対応しているOAuthプロバイダーは？

以下の8プロバイダーに対応しています：

- Google
- GitHub
- Discord
- X (Twitter)
- LinkedIn
- Facebook
- Slack
- Twitch

各プロバイダーの設定方法は[OAuth設定ガイド](../guides/oauth/index.md)を参照してください。

### アクセストークンの有効期限は？

デフォルトで15分（900秒）です。`ACCESS_TOKEN_LIFETIME_SECONDS`環境変数で変更できます。

### リフレッシュトークンの有効期限は？

デフォルトで7日間です。`REFRESH_TOKEN_LIFETIME_DAYS`環境変数で変更できます。

### トークンローテーションとは？

リフレッシュトークンを使用するたびに、新しいリフレッシュトークンが発行され、
古いトークンは無効化されます。これにより、トークン漏洩時のリスクを軽減します。

### PKCEとは？

Proof Key for Code Exchangeの略で、OAuth 2.0の認可コードフローをより安全にする拡張機能です。
YESOD Authは全プロバイダーでPKCEを使用しています。

### ID Tokenとは？

OpenID Connect (OIDC) で定義されたJWTトークンで、ユーザーの認証情報を含みます。
YESOD Authでは、OIDCをネイティブサポートしないプロバイダー（GitHub、Discord、X、Facebook、Twitch）に対しても
自己発行のID Tokenを生成し、統一的なOIDCインターフェースを提供します。

---

## ngrok

### ngrokとは？

ngrokは、ローカルサーバーにHTTPSのパブリックURLを提供するトンネリングサービスです。
X (Twitter)など、OAuthリダイレクトURIにHTTPSが必須のプロバイダーを開発環境で使用する際に必要です。

### ngrokの設定方法は？

1. [ngrok](https://ngrok.com/)でアカウントを作成
2. 認証トークンを取得
3. `secrets/ngrok_authtoken.txt`にトークンを保存
4. ngrokプロファイル付きで起動：
   ```bash
   docker compose --profile default --profile ngrok up -d
   ```

詳細は[Getting Started](../getting-started.md)のngrokセクションを参照してください。

### ngrok URLはどのように管理される？

ngrok起動時に`ngrok-sync`コンテナがngrok APIからパブリックURLを自動取得し、Valkeyに保存します。
APIサーバーはOAuthコールバックURL生成時にValkeyからngrok URLを自動取得するため、
手動でのURL設定は不要です。

### ngrokは本番環境で使う？

いいえ。ngrokは開発環境でのHTTPSトンネル用です。
本番環境では適切なドメインとSSL証明書を使用してください。

---

## 開発

### Mock OAuthとは？

開発・テスト時に、実際のOAuthプロバイダーなしで認証フローをテストできる機能です。
`MOCK_OAUTH_ENABLED=1`で有効化できます（デフォルトで有効）。

### ローカルでテストするには？

```bash
# 起動
docker compose --profile default up -d

# Mock OAuthでログイン
curl "http://localhost:8000/api/v1/auth/mock/login?user=alice&provider=google"
```

### PostgreSQLのポートは？

開発環境ではホスト側ポート`5434`を使用しています（他プロジェクトとの競合回避のため）。
コンテナ内部は標準の`5432`です。CI環境ではホスト側ポート`5433`を使用します。

---

## Webhook

### Webhookが届かない場合は？

1. `config/webhooks.yaml`が正しく設定されているか確認
2. エンドポイントが`enabled: true`になっているか確認
3. URLがHTTPSで始まっているか確認
4. 配信履歴を確認：`GET /api/v1/admin/webhooks/deliveries`

### 署名検証の方法は？

[Webhook設定ガイド](../guides/webhooks.md#署名検証)を参照してください。

---

## デプロイ

### 本番環境で必要な設定は？

1. `MOCK_OAUTH_ENABLED=0`に設定
2. OAuthリダイレクトURIを本番ドメインに更新
3. Docker Secretsでシークレットを管理
4. HTTPSを有効化
5. ngrokプロファイルは使用しない

### スケールアウトできる？

はい。APIサーバーはステートレスなので、複数インスタンスで実行できます。
セッション情報はValkeyに保存されます。
