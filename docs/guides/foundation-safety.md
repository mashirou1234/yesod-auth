# 基盤の安全設定と検証

YESOD Auth は公開前の開発段階です。
この増分は CI、起動設定、管理画面セッションを改善しますが、本番利用可能という判定ではありません。
OAuth コールバックが access token と refresh token を URL に渡す問題は [#680](https://github.com/mashirou1234/yesod-auth/issues/680) として残り、次の増分で一回限りのコード交換に置き換える必要があります。

## 実行モード

API と管理画面は、設定インスタンス生成時に環境変数と Docker secrets を読みます。
`RUNTIME_MODE` の既定値は `production` です。
値は前後の空白と大文字小文字を正規化し、`development`、`test`、`production` 以外を拒否します。
既存の `ENVIRONMENT=DEV` は実行モードを指定しません。

| 設定 | 既定値 | 制約 |
|---|---|---|
| `RUNTIME_MODE` | `production` | 開発時は明示的に `development` を指定 |
| `JWT_SECRET` | 本番では空 | 本番で 32 バイト以上、12 種類以上の文字。空白、既知の弱いパターン、placeholder を拒否 |
| `ADMIN_PASSWORD` | 本番では空 | 本番で 16 文字以上、8 種類以上の文字。ユーザー名と同じ値、既知の弱いパターン、placeholder を拒否 |
| `ADMIN_USER` | `admin` | 空文字を拒否 |
| `JWT_ISSUER` | `yesod-auth` | 空文字を拒否。発行・検証時に使用 |
| `JWT_AUDIENCE` | `yesod-api` | 空文字を拒否。現時点では単一の対象 |
| `MOCK_OAUTH_ENABLED` | `false` | 本番で `true` を拒否 |
| `DEBUG_OAUTH_ENABLED` | `false` | 本番で `true` を拒否。無効時の debug-tokens は 404 |
| `TESTING` | test モードのみ `true` | 本番で `true` を拒否 |
| `SESSION_EXPIRY_HOURS` | `1` | 管理画面の絶対有効期限。1〜24 時間。整数でない値・非正値は警告後に 1 時間へ戻す |

`password`、`qwerty`、`letmein`、連続した数字・英字などの既知パターンを、大文字小文字を区別せず部分一致で拒否します。
このリストは限定的で、未知の辞書語、変形、使い回しを網羅しません。
文字数・文字種類・既知パターンの検査を通過しても、秘密値の推測困難性やエントロピーは証明できません。
JWT 秘密鍵と管理画面パスワードは別々にランダム生成し、Docker secrets などで渡します。
`/run/secrets/jwt_secret` と `/run/secrets/admin_password` が存在すると、対応する環境変数より優先します。
設定エラーには秘密値を出力しません。

```bash
umask 077
openssl rand -hex 32 > secrets/jwt_secret.txt
openssl rand -base64 24 > secrets/admin_password.txt
```

API の secret ファイルは、末尾の LF（`\n`）または CRLF（`\r\n`）を 1 個だけ取り除いて読みます。
改行なしのファイルも受け付けます。
それ以外の先頭・途中・末尾の空白は保持し、本番の JWT 秘密鍵に残っていれば拒否します。
末尾に改行が 2 個あるファイルや、空白のあとに改行があるファイルも拒否対象です。

環境変数 `JWT_SECRET` は改行も含めて一切トリムしません。
本番では空白文字（スペース、タブ、改行、Python の `str.isspace()` が空白と判定する Unicode 文字）を含む値を拒否します。
管理画面の secret ファイルは従来どおり前後の空白を除去して読み、JWT のファイル・環境変数ルールとは区別します。

リポジトリの Compose はローカル開発用です。
API と管理画面は `development`、CI API は `test` を明示し、開発 API の mock OAuth を有効にしています。
本番の設定見本としてそのまま公開しないでください。
開発で debug-tokens を使う場合も、`DEBUG_OAUTH_ENABLED=1` を明示します。

新しい access JWT は `iss`、`aud`、`exp`、`sub` を必須として検証します。
古い JWT への互換 fallback はありません。
アプリ登録による audience の選択、OIDC ID Token、Discovery、JWKS は未実装です。

## 管理画面のセッション

ログイン状態は Streamlit サーバーのセッションメモリーだけに保持します。
ログイン時に単調時計から固定の期限を計算し、操作しても延長しません。
期限切れ、欠損、不正な型、過大な期限、管理者名の変更を検出すると認証状態と API テスト用トークンを消去します。
画面の入口と、DB・Valkey・API を呼ぶ直前に期限を確認します。
期限切れを放置中のタブから検知して既表示の情報を消すタイマーはなく、次の操作時にアクセスを拒否します。

URL の `session` は認証に使わず、見つけた場合は削除します。
ログイン保持チェックボックスとブックマーク案内を除去し、ログアウト時はセッション状態を全消去します。
ページの再読み込み、接続切断、サーバー再起動では再ログインが必要になる場合があります。
以前に保存したトークン付きブックマークも削除してください。

アプリ独自の認証 Cookie は発行しません。
削除した `SESSION_COOKIE_SECURE` と `SESSION_COOKIE_SAMESITE` は、Streamlit 自体の Cookie 設定を変更するものではありませんでした。
HttpOnly Cookie を実装したという主張も行いません。
管理画面のレート制限、MFA、管理者別の RBAC と監査は、この増分の完了条件に含まれません。

## CI とローカル検証

GitHub の push・pull request と Woodpecker は Python の検査を実行します。
GitHub の無条件自動承認と自動マージの workflow は削除しました。
リモートのブランチ保護や必須 check の設定は変更していません。

共通コマンドは `scripts/verify-foundation.sh` です。
Python 3.12、Bun 1.4.4、API と管理画面の requirements、Ruff 0.14.2 を用意します。
検証スクリプトは 8 プロバイダーすべてにテスト専用の client ID / secret を渡し、実際の認証情報は使用しません。

```bash
python -m pip install -r api/requirements.txt -r admin/requirements.txt ruff==0.14.2
bash scripts/verify-foundation.sh lint
bash scripts/verify-foundation.sh build
bash scripts/verify-foundation.sh unit
```

lint は API の既存 Ruff ルールと、管理画面の Ruff 既定ルールを検査します。
format は API を対象にし、管理画面の既存ファイルを一括整形しません。
build は Python の構文・OpenAPI 読み込みに加え、管理画面のツアー資産を固定 lockfile から生成し、コピー元との一致を検査します。
GitHub では API と管理画面の Docker image もビルドします。

実サービス統合検証には、破棄できる PostgreSQL 16 と Valkey 8 を用意してください。
DB 名は `yesod_foundation_test` に限定し、開発データや本番データの接続先を渡さないでください。
検証は migration を適用し、作成したテストユーザー、監査行、state を後始末します。

```bash
export FOUNDATION_TEST_DATABASE_URL='postgresql+asyncpg://<user>:<password>@127.0.0.1:5432/yesod_foundation_test'
export FOUNDATION_TEST_VALKEY_URL='redis://127.0.0.1:6379/0'
bash scripts/verify-foundation.sh integration
# 全 gate を連続実行
bash scripts/verify-foundation.sh all
```

単体テストは SQLite とサービス mock を使います。
統合テストは PostgreSQL 上の migration、refresh token の保存・失効・更新、監査記録、Bearer 認証による API 参照、Valkey の TTL と state の一回消費を実接続で検証します。
外部 OAuth プロバイダーの実ログイン、pg_cron の運用、TLS 配備、ホスト側のブランチ保護は別途検証が必要です。
