# OAuth設定

YESOD Authは複数のOAuthプロバイダーに対応しています。各プロバイダーの設定方法は個別のページを参照してください。

## 対応プロバイダー

| プロバイダー | 公式PKCE | 独自PKCE | OpenID Connect | ID Token生成 | 備考 |
|-------------|----------|----------|----------------|--------------|------|
| [Google](google.md) | ✅ | - | ✅ | - | 推奨 |
| [GitHub](github.md) | ✅ | - | ❌ | ✅ | |
| [X (Twitter)](x.md) | ✅ | - | ❌ | ✅ | メールアドレス取得不可 |
| [LinkedIn](linkedin.md) | ✅ | - | ✅ | - | |
| [Facebook](facebook.md) | ✅ | - | ❌ | ✅ | [Graph API v18.0](https://developers.facebook.com/docs/graph-api/){:target="_blank"} |
| [Discord](discord.md) | - | ✅ | ❌ | ✅ | プロバイダーは対応しているが公式ドキュメントなし |
| [Slack](slack.md) | - | ✅ | ✅ | - | プロバイダー未サポート |
| [Twitch](twitch.md) | - | ✅ | ❌ | ✅ | プロバイダー未サポート、[Helix API](https://dev.twitch.tv/docs/api/){:target="_blank"} |

### ID Token生成について

OpenID Connect非対応のプロバイダー（GitHub, Discord, X, Facebook, Twitch）では、YESOD Authが独自にID Tokenを生成します。これにより、すべてのプロバイダーで統一的なOIDC互換の認証フローを実現できます。

- **JWKSエンドポイント**: `/.well-known/jwks.json` で公開鍵を取得可能
- **OpenID設定**: `/.well-known/openid-configuration` で設定情報を取得可能
- **署名アルゴリズム**: RS256（RSA + SHA-256）

詳細は[認証API - OIDC互換エンドポイント](../api/auth.md#oidc互換エンドポイント)を参照してください。

### PKCEについて

PKCE（Proof Key for Code Exchange）は、認可コード横取り攻撃を防ぐためのセキュリティ拡張です。

- **公式PKCE**: プロバイダーが公式にサポートしており、ドキュメントに記載されています
- **独自PKCE**: プロバイダーが公式にはサポートしていないため、YESOD Authが独自にPKCEパラメータを送信しています

!!! info "独自PKCE実装について"
    プロバイダー側でPKCEパラメータが無視される場合でも、セキュリティ上の問題はありません。
    将来的にプロバイダーがPKCEをサポートした場合、自動的にセキュリティが強化されます。

## 共通設定

### シークレットファイルの配置

各プロバイダーのクライアントIDとシークレットは`secrets/`ディレクトリに配置します：

```
secrets/
├── google_client_id.txt
├── google_client_secret.txt
├── github_client_id.txt
├── github_client_secret.txt
├── discord_client_id.txt
├── discord_client_secret.txt
├── x_client_id.txt
├── x_client_secret.txt
├── linkedin_client_id.txt
├── linkedin_client_secret.txt
├── facebook_client_id.txt
├── facebook_client_secret.txt
├── slack_client_id.txt
├── slack_client_secret.txt
├── twitch_client_id.txt
└── twitch_client_secret.txt
```

### 本番環境での注意点

!!! warning "リダイレクトURIの更新"
    本番環境では、各プロバイダーの設定画面でリダイレクトURIを本番ドメインに更新してください：
    ```
    https://your-domain.com/api/v1/auth/{provider}/callback
    ```

!!! tip "PKCE"
    PKCEに対応しているプロバイダーでは、YESOD Authが自動的にPKCEを使用してセキュリティを強化します。
