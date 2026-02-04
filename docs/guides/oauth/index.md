# OAuth設定

YESOD Authは複数のOAuthプロバイダーに対応しています。各プロバイダーの設定方法は個別のページを参照してください。

## 対応プロバイダー

| プロバイダー | PKCE | OpenID Connect | 備考 |
|-------------|------|----------------|------|
| [Google](google.md) | ✅ | ✅ | 推奨 |
| [GitHub](github.md) | ✅ | ❌ | |
| [Discord](discord.md) | ❌ | ❌ | |
| [X (Twitter)](x.md) | ✅ (必須) | ❌ | メールアドレス取得不可 |
| [LinkedIn](linkedin.md) | ✅ | ✅ | |
| [Facebook](facebook.md) | ✅ | ❌ | Graph API v18.0 |
| [Slack](slack.md) | ❌ | ✅ | |
| [Twitch](twitch.md) | ❌ | ❌ | Helix API |

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
