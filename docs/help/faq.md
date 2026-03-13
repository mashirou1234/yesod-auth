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

### OAuth secretを更新したら再起動は必要？

必要です。YESOD Auth は起動時に `/run/secrets/*` を読み込むため、`secrets/*.txt` を更新した直後は、対象コンテナを再作成して新しい値を読み込ませてください。

| 変更内容 | 再起動要否 | 実行コマンド |
| --- | --- | --- |
| `secrets/<provider>_client_id.txt` / `secrets/<provider>_client_secret.txt` を更新 | 必須 | `docker compose up -d --force-recreate api worker` |
| `secrets/jwt_secret.txt` を更新 | 必須 | `docker compose up -d --force-recreate api worker` |
| `.env` のみ更新（secretは未変更） | 必須 | `docker compose up -d --force-recreate api worker` |
| ドキュメントのみ更新 | 不要 | なし |

再起動後は次の 2 点を固定で確認します。

1. `docker compose ps` で `api` と `worker` が `Up` になっていること
2. `curl -fsS http://localhost:8000/health` が `{"status":"ok"}` を返すこと

シークレットの配置方針は [インストールガイド: OAuth認証情報](../installation.md#oauth認証情報)、
プロバイダー別の有効化手順は [OAuth設定ガイド](../guides/oauth/index.md#セルフホスト向け最短手順) を参照してください。

<a id="oauth-secret-permission-recovery"></a>

### OAuth secret の権限不備を最短で復旧するには？

次の順に実施してください（症状→確認→復旧）。

1. `docker compose logs --tail=100 api | rg -n "permission denied|/run/secrets"` で症状を確認する
2. Linux: `stat -c '%n %a %U:%G' secrets/*.txt` / macOS: `stat -f '%N %Lp %Su:%Sg' secrets/*.txt` で権限と所有者を確認する
3. `chmod 600 secrets/*.txt` と `sudo chown "$(id -un):$(id -gn)" secrets/*.txt` で復旧する
4. `docker compose up -d --force-recreate api worker` 後に `curl -fsS http://localhost:8000/health` を確認する

詳細手順は [トラブルシューティング: secrets 権限不備で `Permission denied` が出る](./troubleshooting.md#secrets-permission-recovery) を参照してください。  
受け入れ時は FAQ / installation / troubleshooting の3点で、コマンドと手順順が一致していることを確認してください。

### 429（Too Many Requests）が出たときの確認手順は？

認証レート制限の切り分け手順を [トラブルシューティング: 429 Too Many Requests](./troubleshooting.md#auth-rate-limit-429) にまとめています。  
`api/app/auth/rate_limit.py` の設定値（`RATE_LIMIT_PER_MINUTE` / `VALKEY_URL`）確認から着手してください。

### GitHubログインをorganizationメンバーだけに制限できる？

現状のYESOD AuthはGitHub OAuthでorganization所属チェックを行いません。
organization制限が必要な場合は、`read:org`スコープとコールバック後の所属検証を追加実装してください。

### 認証失敗時の一次分類は？

まずは HTTP ステータスと代表メッセージで次の4分類に分けると切り分けが速くなります。

| 一次分類 | 典型シグナル | 主な原因 | 最初に見る場所 |
| --- | --- | --- | --- |
| 入力不正（422） | `Field required` / `Input should be a valid string` | `refresh_token` の欠落・型不正 | [`認証API: refresh失敗時エラー分類`](../api/auth.md#refresh失敗時エラー分類) |
| 認証失敗（401） | `Not authenticated` / `Could not validate credentials` | access/refresh token の期限切れ・失効・改ざん | [`トラブルシューティング: 認証エラー`](./troubleshooting.md#認証エラー) |
| state不整合（400） | `Invalid or expired state` | callback 二重実行、Valkey不安定、環境不一致 | [`トラブルシューティング: state mismatch 診断フロー`](./troubleshooting.md#state-mismatch-flow) |
| レート制限（429） | `Rate limit exceeded` / `Too Many Requests` | 短時間の連続アクセス、制限値過小 | [`トラブルシューティング: 429 Too Many Requests`](./troubleshooting.md#auth-rate-limit-429) |

運用メモとして、分類時は「発生時刻」「対象エンドポイント」「利用プロバイダー（mock/google/github等）」をセットで記録すると再現調査が容易です。

---

## 開発

### Mock OAuthとは？

開発・テスト時に、実際のOAuthプロバイダーなしで認証フローをテストできる機能です。
`MOCK_OAUTH_ENABLED=1`で有効化できます。

### Mock OAuthから本番OAuthへ切り替える最小確認は？

本番切替時は次の3項目だけ先に確認してください。

1. `MOCK_OAUTH_ENABLED=0` になっていること（アプリ既定値は `0`。開発用 `default`/`ci` プロファイルでは Compose 側で `1` に上書きされるため、本番運用値を再確認）
2. 利用するOAuthプロバイダーの `*_client_id` / `*_client_secret` が本番値で設定され、不要な開発用値が混在していないこと
3. provider管理画面の callback URL と `GET /api/v1/auth/{provider}/callback` の実運用URLが一致していること

切り分け手順は [トラブルシューティング: state mismatch 診断フロー](./troubleshooting.md#state-mismatch-flow) と [トラブルシューティング: 401 Unauthorized / invalid_client](./troubleshooting.md#401-unauthorized--invalid_client) を参照してください。  
前提の設定差分は [インストール: profile別の環境変数優先順位](../installation.md#profile別の環境変数優先順位) を参照してください。

### 複数providerを有効化するときの順序チェックは？

複数 provider を導入するときは、次の順で確認すると取りこぼしを防げます。

1. profile を先に固定する（`default` / `full` / `ci` のどれで起動するかを決める）
2. 実際に有効化する provider 分だけ `secrets/<provider>_client_id.txt` / `secrets/<provider>_client_secret.txt` を用意する
3. provider 管理画面の callback URL を `https://<api-domain>/api/v1/auth/<provider>/callback` に一致させる
4. `GET /api/v1/auth/<provider>` の開始と callback を同じ環境（同一 host/scheme）で通す

導線は次の順で参照してください。

- インストール: [OAuth認証情報](../installation.md#oauth認証情報)
- クイックスタート: [2.5 コールバックURLの検証](../getting-started.md#25-コールバックurlの検証)
- トラブルシューティング: [401 Unauthorized / invalid_client](./troubleshooting.md#401-unauthorized--invalid_client)

受け入れ時は、FAQ / installation / troubleshooting の3点同期（手順・用語・リンク先）が保たれていることを確認してください。

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
