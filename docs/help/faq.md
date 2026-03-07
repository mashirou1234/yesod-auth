# FAQ

## 一般

### YESOD Authとは？

YESOD Authは、OAuth 2.0認証を簡単に実装するためのオープンソース認証基盤です。
Google、Discordに対応し、Webhook連携機能も備えています。

### ライセンスは？

MIT Licenseです。商用利用も可能です。

---

## 認証

### アクセストークンの有効期限は？

デフォルトで15分（900秒）です。`ACCESS_TOKEN_LIFETIME_SECONDS`環境変数で変更できます。

### リフレッシュトークンの有効期限は？

デフォルトで7日間です。`REFRESH_TOKEN_LIFETIME_DAYS`環境変数で変更できます。

### トークンローテーションとは？

リフレッシュトークンを使用するたびに、新しいリフレッシュトークンが発行され、
古いトークンは無効化されます。これにより、トークン漏洩時のリスクを軽減します。

### PKCEとは？

Proof Key for Code Exchangeの略で、OAuth 2.0の認可コードフローをより安全にする拡張機能です。
YESOD AuthはGoogle OAuthでPKCEを自動的に使用します。

### どのsecretを必須で用意すべき？

必須なのは`jwt_secret`と、実際に有効化して使うOAuthプロバイダーの`*_client_id`/`*_client_secret`だけです。
たとえばGoogleのみ使う最小構成ならGoogle分だけ、複数プロバイダー運用なら有効化した各プロバイダー分を追加してください。

### GitHubログインをorganizationメンバーだけに制限できる？

現状のYESOD AuthはGitHub OAuthでorganization所属チェックを行いません。
organization制限が必要な場合は、`read:org`スコープとコールバック後の所属検証を追加実装してください。

---

## 開発

### Mock OAuthとは？

開発・テスト時に、実際のOAuthプロバイダーなしで認証フローをテストできる機能です。
`MOCK_OAUTH_ENABLED=1`で有効化できます。

### ローカルでテストするには？

```bash
# 起動
docker compose --profile default up -d

# Mock OAuthでログイン
curl "http://localhost:8000/api/v1/auth/mock/login?user=alice&provider=google"
```

<a id="admin-i18n-untranslated-fallback"></a>

### Adminで未翻訳キーが出たときの表示は？

`admin/i18n.py` の現在実装では、次の順でフォールバックします。

1. 言語コードが未対応なら `en` を使用
2. キーが未定義なら翻訳文ではなくキー文字列（例: `nav.unknown`）をそのまま表示
3. フォーマット引数が不足しても例外は出さず、テンプレート文字列をそのまま返す

運用上は「画面にドット区切りキーが見えたら未翻訳」と判定し、翻訳データ追加対象として扱ってください。  
確認手順は [トラブルシューティング: Admin i18n 未翻訳キーの確認手順](./troubleshooting.md#admin-i18n-fallback) を参照してください。

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

### スケールアウトできる？

はい。APIサーバーはステートレスなので、複数インスタンスで実行できます。
セッション情報はValkeyに保存されます。
