# OAuth設定

YESOD Authは複数のOAuthプロバイダーに対応しています。各プロバイダーの設定方法は個別のページを参照してください。

## 対応プロバイダー

| プロバイダー | 公式PKCE | 独自PKCE | OpenID Connect | 備考 |
|-------------|----------|----------|----------------|------|
| [Google](google.md) | ✅ | - | ✅ | 推奨 |
| [GitHub](github.md) | ✅ | - | ❌ | |
| [X (Twitter)](x.md) | ✅ | - | ❌ | メールアドレス取得不可 |
| [LinkedIn](linkedin.md) | ✅ | - | ✅ | |
| [Facebook](facebook.md) | ✅ | - | ❌ | [Graph API v18.0](https://developers.facebook.com/docs/graph-api/){:target="_blank"} |
| [Discord](discord.md) | - | ✅ | ❌ | プロバイダーは対応しているが公式ドキュメントなし |
| [Slack](slack.md) | - | ✅ | ✅ | プロバイダー未サポート |
| [Twitch](twitch.md) | - | ✅ | ❌ | プロバイダー未サポート、[Helix API](https://dev.twitch.tv/docs/api/){:target="_blank"} |

### PKCEについて

PKCE（Proof Key for Code Exchange）は、認可コード横取り攻撃を防ぐためのセキュリティ拡張です。

- **公式PKCE**: プロバイダーが公式にサポートしており、ドキュメントに記載されています
- **独自PKCE**: プロバイダーが公式にはサポートしていないため、YESOD Authが独自にPKCEパラメータを送信しています

!!! info "独自PKCE実装について"
    プロバイダー側でPKCEパラメータが無視される場合でも、セキュリティ上の問題はありません。
    将来的にプロバイダーがPKCEをサポートした場合、自動的にセキュリティが強化されます。

## 共通設定

### セルフホスト向け最短手順

1. 利用するOAuthプロバイダーを決める（例: GitHubのみ）
2. `secrets/` に対象プロバイダーの `*_client_id.txt` と `*_client_secret.txt` を配置する
3. `MOCK_OAUTH_ENABLED=0` で実OAuthを有効化する
4. API公開URLに合わせてリダイレクトURIを更新する
5. `/api/v1/auth/{provider}` へアクセスして、プロバイダー画面へ遷移することを確認する

!!! note "docker-compose の既定設定"
    `docker-compose.yml` の既定では `api` / `api-ci` に `google_*` と `discord_*` がマウントされています。
    GitHubなど他プロバイダーを使う場合は、`docker-compose.override.yml` で `secrets` を追加してください。

    ```yaml
    services:
      api:
        secrets:
          - github_client_id
          - github_client_secret
      api-ci:
        secrets:
          - github_client_id
          - github_client_secret

    secrets:
      github_client_id:
        file: ./secrets/github_client_id.txt
      github_client_secret:
        file: ./secrets/github_client_secret.txt
    ```

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

## provider追加時チェックリスト

新しいOAuth providerを追加・有効化するときは、次の順で確認してください。

1. `docs/guides/oauth/index.md` の対応プロバイダー表に行を追加する（PKCE/OpenID Connect/備考を含む）。
2. `docs/guides/oauth/<provider>.md` を作成または更新し、以下を明記する。
   - Provider管理画面での設定手順
   - Redirect URI（`/api/v1/auth/<provider>/callback`）
   - 必要スコープ
   - クライアントID/シークレットの配置方法
3. `secrets/<provider>_client_id.txt` と `secrets/<provider>_client_secret.txt` の命名で統一する。
4. `docs/installation.md` と `docs/help/faq.md` の「有効化したprovider分だけsecretを用意する」方針と矛盾がないか確認する。
5. セルフホスト公開前に、本番ドメインのRedirect URIへ更新し、ローカル値（`localhost`）が残っていないか確認する。

上記を満たすと、導入時の設定漏れを抑えつつ、OSSとして再利用しやすい説明構成を維持できます。
