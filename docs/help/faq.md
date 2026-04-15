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

### 管理者トークンが失効して管理APIで 401 が出たときの再認証手順は？

次の順で復旧してください。

1. 現在の `access_token` で管理API（例: `GET /api/v1/admin/webhooks/endpoints`）を呼び、`401` を確認する
2. `refresh_token` が有効なら `POST /api/v1/auth/refresh` で再発行する
3. `refresh_token` も失効している場合は OAuth ログインを最初からやり直す
4. 新しい `access_token` で管理APIを再実行し、`200` を確認する

コマンド付きの詳細手順は [トラブルシューティング: 管理者トークン失効で管理APIが `401 Unauthorized` になる](./troubleshooting.md#admin-token-reauth) を参照してください。

### PKCEとは？

Proof Key for Code Exchangeの略で、OAuth 2.0の認可コードフローをより安全にする拡張機能です。
YESOD AuthはGoogle OAuthでPKCEを自動的に使用します。

### どのsecretを必須で用意すべき？

必須なのは`jwt_secret`と、実際に有効化して使うOAuthプロバイダーの`*_client_id`/`*_client_secret`だけです。
たとえばGoogleのみ使う最小構成ならGoogle分だけ、複数プロバイダー運用なら有効化した各プロバイダー分を追加してください。

加えて `--profile full` で `admin` を使う場合は、`secrets/admin_password.txt` も必須です（空ファイル不可）。

```bash
ls -l secrets/admin_password.txt
test -s secrets/admin_password.txt && echo "admin_password: OK" || (echo "admin_password が未作成または空です" >&2; exit 1)
```

導線同期:
- インストール: [管理画面付き](../installation.md#管理画面付き)
- トラブルシューティング: [full profile で admin ログインできない（admin_password 未設定/空）](./troubleshooting.md#full-profile-admin-password-missing)

### provider 未設定のまま初回導入を進めてもよい？

可能です。次の順で進めると最短で起動確認できます。

1. `default` profile で起動し、`jwt_secret` と有効化する provider 分だけ先に設定する
2. 未設定 provider の認証導線は呼ばず、`/health` と `/docs` の到達確認を先に完了する
3. OAuth 設定がそろった時点で `docker compose --profile default up -d --force-recreate api` を実行して再開する

再開ポイントは [クイックスタート: provider 未設定時の最短スキップ手順](../getting-started.md#provider-未設定時の最短スキップ手順) を参照してください。  
導線全体は [インストール](../installation.md#provider-未設定時の最短スキップ手順) と [トラブルシューティング](./troubleshooting.md#provider-未設定のまま認証導線を実行した) で同期しています。

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
4. `docker compose up -d --force-recreate api worker` で反映する
5. `docker compose logs --tail=100 api | rg -n "permission denied|/run/secrets"` と `curl -fsS http://localhost:8000/health` で再確認する

詳細手順は [トラブルシューティング: secrets 権限不備で `Permission denied` が出る](./troubleshooting.md#secrets-permission-recovery) を参照してください。  
受け入れ時は FAQ / installation / troubleshooting の3点で、コマンドと手順順が一致していることを確認してください。

### 429（Too Many Requests）が出たときの確認手順は？

認証レート制限の切り分け手順を [トラブルシューティング: 429 Too Many Requests](./troubleshooting.md#auth-rate-limit-429) にまとめています。  
`api/app/auth/rate_limit.py` の設定値（`RATE_LIMIT_PER_MINUTE` / `VALKEY_URL`）確認から着手してください。

### GitHubログインをorganizationメンバーだけに制限できる？

現状の YESOD Auth は GitHub OAuth で organization 所属チェックを行いません。  
そのため、organization 非所属ユーザーでも GitHub 側の認可が成功すれば通常どおりログインできます。

organization 制限が必要な場合は、次を追加実装してください。

1. `read:org` スコープを要求する
2. callback 後に organization 所属を検証する
3. 未所属ユーザーを `403` などで拒否する

実装前の仕様確認は [GitHub OAuth ガイド: organization制限時の挙動](../guides/oauth/github.md#organization制限時の挙動) を参照してください。

### 認証失敗時の一次分類は？

まずは次の順で確認すると、OAuth 導入初期やセルフホスト運用でも誤判定を減らせます。

1. 失敗した API の HTTP ステータスを確定する
2. API ログから代表メッセージ（`detail` / エラーコード）を拾う
3. 下表で一次分類し、対応するドキュメントへ遷移する

| 一次分類 | 典型シグナル | 主な原因 | 初動アクション | 最初に見る場所 |
| --- | --- | --- | --- | --- |
| 入力不正（422） | `Field required` / `Input should be a valid string` | `refresh_token` の欠落・型不正 | リクエスト JSON と型を修正して再送 | [`認証API: refresh失敗時エラー分類`](../api/auth.md#refresh失敗時エラー分類) |
| 認証失敗（401） | `Not authenticated` / `Could not validate credentials` | access/refresh token の期限切れ・失効・改ざん | `/api/v1/auth/refresh` を1回試し、失敗なら再ログイン | [`トラブルシューティング: 認証エラー`](./troubleshooting.md#認証エラー) |
| state不整合（400） | `Invalid or expired state` | callback 二重実行、Valkey不安定、環境不一致 | 同一 host/scheme で認証開始からやり直し、Valkey ログ確認 | [`トラブルシューティング: state mismatch 診断フロー`](./troubleshooting.md#state-mismatch-flow) |
| レート制限（429） | `Rate limit exceeded` / `Too Many Requests` | 短時間の連続アクセス、制限値過小 | 連続試行を止め、制限値とアクセス集中を確認 | [`トラブルシューティング: 429 Too Many Requests`](./troubleshooting.md#auth-rate-limit-429) |

運用メモとして、分類時は「発生時刻」「対象エンドポイント」「利用プロバイダー（mock/google/github等）」をセットで記録すると再現調査が容易です。

### sync-from-provider の 400/404 は何を意味する？

`POST /api/v1/users/me/sync-from-provider` の主な失敗は次の 3 種類です。

1. `400 Unsupported provider`: `provider` が `google` / `discord` 以外
2. `404 No <provider> account linked`: 指定 provider の連携がない
3. `400 No provider info stored ...`: provider 連携はあるが保存済みプロフィール情報がない

API 契約とレスポンス例は [ユーザーAPI: プロバイダ情報からプロフィール復元](../api/users.md#プロバイダ情報からプロフィール復元) を参照してください。  
切り分け手順は [トラブルシューティング: sync-from-provider で 400/404 が返る](./troubleshooting.md#sync-from-provider-errors) を参照してください。

---

## 開発

### Mock OAuthとは？

開発・テスト時に、実際のOAuthプロバイダーなしで認証フローをテストできる機能です。
`MOCK_OAUTH_ENABLED=1`で有効化できます。

### Mock OAuthから実OAuthへ切り替える最小確認は？

実OAuth切替時は次の3項目だけ先に確認してください。

1. `MOCK_OAUTH_ENABLED=0` になっていること（アプリ既定値は `0`。Compose の `default` / `full` / `ci` プロファイルでは `1` に上書きされるため、本番運用値を再確認）
2. 利用するOAuthプロバイダーの `*_client_id` / `*_client_secret` が本番値で設定され、不要な開発用値が混在していないこと
3. provider管理画面の callback URL と `GET /api/v1/auth/{provider}/callback` の実運用URLが一致していること

再開ポイント:
- [クイックスタート: Mock OAuthから実OAuthへ切り替える最小チェック](../getting-started.md#mock-oauthから実oauthへ切り替える最小チェック)
- [インストール: provider 未設定時の最短スキップ手順](../installation.md#provider-未設定時の最短スキップ手順)
- [トラブルシューティング: provider 未設定のまま認証導線を実行した](./troubleshooting.md#provider-未設定のまま認証導線を実行した)

切り分け手順は [トラブルシューティング: state mismatch 診断フロー](./troubleshooting.md#state-mismatch-flow) と [トラブルシューティング: 401 Unauthorized / invalid_client](./troubleshooting.md#401-unauthorized--invalid_client) を参照してください。  
本番切替時の確認で迷ったら [トラブルシューティング: 障害時の参照順（最短導線）](./troubleshooting.md#障害時の参照順最短導線) から再開してください。  
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

受け入れ時は、次の3点を満たしていることを確認してください。

1. FAQ の順序チェック項目が3つ以上あり、今回の運用順（profile固定 → secret配置 → callback一致 → 認可導線確認）を説明できる
2. 参照リンクが [インストール](../installation.md#oauth認証情報) と [クイックスタート](../getting-started.md#25-コールバックurlの検証) を指している
3. [FAQ](./faq.md#複数providerを有効化するときの順序チェックは) / [installation](../installation.md#oauth認証情報) / [troubleshooting](./troubleshooting.md#401-unauthorized--invalid_client) の三点同期（手順・用語・リンク先）が保たれている

### preflight で valkey 到達確認を最短で行うには？

最短では、選んだ profile で `valkey` を起動して `PING` が `PONG` を返すことだけ確認します。

```bash
PROFILE=default # full / ci でも可
docker compose --profile "$PROFILE" up -d valkey
docker compose --profile "$PROFILE" exec valkey sh -lc 'valkey-cli ping || redis-cli ping'
```

失敗時は次の順で切り分けると早いです。

1. `docker compose --profile "$PROFILE" config --services | rg -x 'valkey'`
2. `docker compose ps valkey`
3. `docker compose logs valkey --since=30m`

参照先:
- [インストール: Docker起動前チェック項目](../installation.md#docker起動前チェック項目)
- [トラブルシューティング: preflight で valkey 到達確認に失敗する](./troubleshooting.md#valkey-preflight-failure)

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
