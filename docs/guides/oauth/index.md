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
| [Slack](slack.md) | - | ✅ | ✅ | |
| [Twitch](twitch.md) | - | ✅ | ❌ | [Helix API](https://dev.twitch.tv/docs/api/){:target="_blank"} |

## provider別必須環境変数一覧

実OAuthで必要なのは、`jwt_secret` と「有効化して使う provider 分の `*_client_id` / `*_client_secret`」だけです。
`MOCK_OAUTH_ENABLED=1` はローカル疎通用であり、実運用では `MOCK_OAUTH_ENABLED=0` を使用します。

| provider | 必須 secret 名 | 環境変数名（secret未使用時） | 個別ガイド |
|---|---|---|---|
| Google | `google_client_id` / `google_client_secret` | `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | [google.md](google.md) |
| GitHub | `github_client_id` / `github_client_secret` | `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` | [github.md](github.md) |
| Discord | `discord_client_id` / `discord_client_secret` | `DISCORD_CLIENT_ID` / `DISCORD_CLIENT_SECRET` | [discord.md](discord.md) |
| X (Twitter) | `x_client_id` / `x_client_secret` | `X_CLIENT_ID` / `X_CLIENT_SECRET` | [x.md](x.md) |
| LinkedIn | `linkedin_client_id` / `linkedin_client_secret` | `LINKEDIN_CLIENT_ID` / `LINKEDIN_CLIENT_SECRET` | [linkedin.md](linkedin.md) |
| Facebook | `facebook_client_id` / `facebook_client_secret` | `FACEBOOK_CLIENT_ID` / `FACEBOOK_CLIENT_SECRET` | [facebook.md](facebook.md) |
| Slack | `slack_client_id` / `slack_client_secret` | `SLACK_CLIENT_ID` / `SLACK_CLIENT_SECRET` | [slack.md](slack.md) |
| Twitch | `twitch_client_id` / `twitch_client_secret` | `TWITCH_CLIENT_ID` / `TWITCH_CLIENT_SECRET` | [twitch.md](twitch.md) |

一覧の定義元は [インストールガイド（OAuth認証情報）](../../installation.md#oauth-credentials) です。
クイックスタートでの初回導入順は [getting-started](../../getting-started.md#2-シークレットファイルの作成) を参照してください。

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

## 有効化判定フロー（最初に確認）

OAuthプロバイダーを「有効化できているか」を、次の順序で確認してください。

1. 利用するプロバイダーを決める
   使う予定のプロバイダー（例: Google / GitHub）だけを対象にします。未使用プロバイダーの認証情報は必須ではありません。
2. 実行モードを決める
   実プロバイダー検証なら通常モード、ローカル疎通だけ先に確認するなら `MOCK_OAUTH_ENABLED=1` を使います。環境変数の意味は [インストールガイド（環境変数）](../../installation.md#environment-variables) を参照してください。
3. 認証情報の入力先を決める
   認証情報は Docker Secrets（`/run/secrets/<name>`）または環境変数（`<NAME>`）で設定します。YESOD Auth は `read_secret` で **Secretsを優先し、未設定時に環境変数へフォールバック** します。
4. プロバイダーごとの必須2項目を満たす
   対象プロバイダーごとに `*_client_id` と `*_client_secret` の両方を設定します。名前一覧は [インストールガイド（OAuth認証情報）](../../installation.md#oauth-credentials) を参照してください。
5. 起動後に導線で確認する
   `GET /api/v1/auth/{provider}` で認可画面へ遷移できることを確認し、失敗時は [トラブルシューティング](../../help/troubleshooting.md) を参照します。
6. 時刻同期を確認する（self-host）
   OAuth認可コードは短命なため、ホスト時刻のずれで `invalid_grant` が発生します。`timedatectl status` で NTP 同期状態を確認し、ずれがある場合は [clock skew 診断](../../help/troubleshooting.md#oauth-clock-skew) を参照してください。

### provider切替時の確認フロー

既存プロバイダー（例: Google）から別プロバイダー（例: GitHub）へ切り替えるときは、次の順で確認してください。

1. 切替対象を1つに固定する
   同時に複数プロバイダーを切り替えず、今回有効化する provider 名を1つ決めます。
2. 新プロバイダーの secret 2点を追加する
   `secrets/<provider>_client_id.txt` と `secrets/<provider>_client_secret.txt` を作成し、値を設定します。名称規約は [OAuth認証情報](../../installation.md#oauth-credentials) に合わせます。
3. Compose 定義へ mount を追加する
   `docker-compose.override.yml` で `api`（必要なら `api-ci` も）に対象 provider の secret を追加し、`docker compose config` で反映を確認します。
4. callback URL を新プロバイダー管理画面へ反映する
   `https://<api-domain>/api/v1/auth/<provider>/callback` を登録し、旧 provider の callback 設定と混在しないことを確認します。
5. 新プロバイダー導線だけで疎通確認する
   `GET /api/v1/auth/<provider>` から認可画面へ遷移できることを確認し、失敗時は [invalid_client 診断](../../help/troubleshooting.md#401-unauthorized--invalid_client) と [state mismatch 診断](../../help/troubleshooting.md#state-mismatch-flow) の順で切り分けます。

!!! tip "旧プロバイダーの扱い"
    旧プロバイダーを無効化する場合は、対応する secret mount を Compose から削除したうえで再起動し、`docker compose config --services` と API ログで不要 provider の導線が呼ばれていないことを確認してください。

### config / secrets の参照関係（要点）

- アプリ設定は `api/app/config.py` の `read_secret()` で読み込みます。
- 優先順位は `Docker Secrets (/run/secrets/<name>)` → `環境変数(<NAME>)` → `既定値` です。
- そのため、同名を両方設定した場合は Secrets 側が採用されます。

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

## セルフホスト運用チェックリスト

1. 公開APIドメインを固定する（例: `https://auth.example.com`）
2. `FRONTEND_URL` と `CORS_ORIGINS` を同一環境のURLに合わせる
3. 利用するプロバイダーだけ `secrets/*_client_id.txt` / `*_client_secret.txt` を配置する
4. 各プロバイダーの callback URL を `https://<api-domain>/api/v1/auth/{provider}/callback` に統一する
5. 本番では `MOCK_OAUTH_ENABLED=0` を確認する
6. デプロイ後に `GET /health` と実際の OAuth ログイン（最低1プロバイダー）を疎通確認する

!!! tip "PKCE"
    PKCEに対応しているプロバイダーでは、YESOD Authが自動的にPKCEを使用してセキュリティを強化します。

## Callback確認の共通チェックリスト {#oauth-callback-checklist}

プロバイダー個別ページに入る前に、まずこの共通チェックで callback 周りの設定漏れを切り分けます。

1. Callback URL を完全一致で登録する
   `http/https`、ホスト、ポート、パス、末尾 `/` を含めて一致しているか確認する。
2. 認可開始エンドポイントから必ず検証する
   `GET /api/v1/auth/{provider}` から開始し、直接 callback URL を叩かない。
3. 失敗時は API ログで callback 関連語を確認する
   `redirect_uri` / `callback` / `state` を起点に直近ログを確認する。
4. FAQ / installation / troubleshooting の三点同期チェック
   共通説明の整合は [インストール](../../installation.md#oauth-credentials) / [FAQ](../../help/faq.md) / [トラブルシューティング](../../help/troubleshooting.md) の3ページで確認する。

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

### OAuthガイド共通チェックテンプレート

新しいOAuthプロバイダーガイドを追加するときは、以下の4観点を必ず埋めてください。

- Callback URL: ローカル/本番の両方で `.../api/v1/auth/{provider}/callback` を明記する
- Scope: 必須スコープと、スコープ不足時に起きる症状を明記する
- Secrets: `secrets/{provider}_client_id.txt` と `secrets/{provider}_client_secret.txt` の作成手順を明記する
- Test: ログイン開始エンドポイントにアクセスして遷移確認する手順を明記する

```md
## 共通チェック観点

- [ ] Callback URL
  - [ ] ローカル: `http://localhost:8000/api/v1/auth/{provider}/callback`
  - [ ] 本番: `https://<your-domain>/api/v1/auth/{provider}/callback`
- [ ] Scope
  - [ ] 使用スコープ: `<space-separated-scopes>`
  - [ ] 不足時の症状: `<example>`
- [ ] Secrets
  - [ ] `secrets/{provider}_client_id.txt`
  - [ ] `secrets/{provider}_client_secret.txt`
- [ ] Test
  - [ ] `curl -I "http://localhost:8000/api/v1/auth/{provider}/login"` が 302 を返す
```
