# アプリ登録からログインまでの受入仕様

状態: M0 設計確定。以下の管理 API、アプリ登録、OIDC エンドポイントは未実装である。
決定日: 2026-10-23 JST。旧 API の後方互換は要求しない。
この文書は M1 以降の実装契約とし、M0 の実装済み範囲は [改修計画](oss-roadmap.md) を参照する。

## 主体と境界

- 管理者: 自身のプロジェクトにアプリと provider 接続を登録する。
- アプリ開発者: 発行された client_id と登録済み redirect_uri で認証を開始する。
- 一般利用者: 公開ログイン画面から外部 provider で本人確認する。管理 API の権限は持たない。
- プロジェクト: 利用者情報・接続設定・管理権限の境界。同じメールでも別プロジェクトの利用者は自動統合しない。
- アプリ: client_id、redirect URI、許可 origin、許可 scope、token audience の境界。同一プロジェクト内でも別アプリ向け token は拒否する。

最初は既定プロジェクト一つ、同一運営主体の Web アプリを対象とする。SPA と server-side Web client を区別する。
SPA に client secret を発行しない。server-side client の secret はサーバーだけで扱い、一度だけ表示し、その後は再発行する。
モバイル独自 scheme、外部組織のセルフサービス登録、dynamic client registration はこの仕様に含めない。

<a id="project-boundary-800"></a>

## M1 プロジェクト境界の実装範囲（Issue #800）

migration `007` は既定プロジェクト `00000000-0000-4000-8000-000000000001` を一つ作成する。
既存の利用者、プロフィール、メール、OAuth 連携、refresh token、削除待ち利用者、webhook 配信記録、監査記録には、この ID を関連付ける。
既存の ID、データ、token の失効状態は保持する。
既定プロジェクトの再作成は `ensure_default_project(connection)` の `ON CONFLICT DO NOTHING` で並行実行時も重複を防ぐ。

アプリケーションのデータアクセスは `async_session_maker(project_id=...)` を必須とする。
セッションの project は生成後に変更できず、ORM の検索には所有 project の条件を加える。
関連レコードの project と user は複合外部キーで照合し、更新・削除 SQL にも所有 project を含める。
セッション経由の任意 SQL と bulk 更新は拒否し、監査・管理画面・集計の既存 SQL にはサーバー側の project 条件を明示する。
migration と保守用の直接 engine 接続は、権限を持つ運営者向けの別境界として扱う。

PostgreSQL では対象テーブルに強制 RLS を設定し、セッションが transaction ごとに設定する `yesod.project_id` と照合する。
RLS の追加防御は `NOSUPERUSER NOBYPASSRLS` の実行ロールを前提とする。
DB 管理者・superuser・BYPASSRLS ロールによる任意 SQL のアクセス制限は保証しない。
現在の配置でそれらの権限を持つ接続を使う場合も、アプリ側の検索・更新条件は適用される。
DB 実行ロールの分離や audit partition への直接権限管理は、本番配置時に確認する。

現在の公開 API、管理画面、環境変数の OAuth 資格情報、ファイルの webhook 設定は既定プロジェクトに固定する。
URL、query、header から任意の project を選ぶ機能は提供しない。
Access Token は `project_id` を持ち、API は DB セッションの project と一致しない token を拒否する。
既存の project claim がない token は、再発行または再ログインが必要になる。
別プロジェクトは環境変数の provider 接続を利用できず、その利用者の event を既定 webhook 接続へ配信しない。
複数プロジェクト向け接続設定の CRUD、管理者所属・権限、アプリ登録は後続 Issue で実装する。

OAuth 本人識別の一意性は `(project_id, provider, provider_user_id)` に限定する。
同じメールを持つ別 ID・別 provider・別プロジェクトの利用者は自動連携しない。
メールはプロフィール属性として扱い、一意性による統合は行わない。

検証は `bash scripts/verify-foundation.sh integration` で、専用 PostgreSQL/Valkey に対して行う。
二つの project、scope の省略・差し替え、関連レコードの誤接続、改変した detached object、JWT、管理画面、非 bypass role の RLS、既存データを保持する migration を対象とする。
検証用ユーザーには隔離 DB 内での一時 DB・一時ロール作成権限が必要であり、本番 DB に向けて実行しない。
この migration の downgrade は project 関連付けを失うため拒否する。
復旧時は検証済みバックアップと変更前バージョンを使い、本番のデータや失効履歴を巻き戻さない手順を別途確認する。

## 登録項目と管理操作

提案 API prefix は `/api/v1/admin`。通常の利用者 JWT を管理権限の根拠にしない。
全操作で管理者のプロジェクト所属と役割を検証する。UI 側の非表示だけに依存しない。

| 操作 | 入力と制約 | 結果 |
|---|---|---|
| アプリ作成 `POST /projects/{project_id}/applications` | name 1–80文字、client_type `public` / `confidential`、redirect_uris、allowed_origins、allowed_scopes | 推測困難な client_id、設定 version、状態 `draft` |
| 設定更新 `PATCH /projects/{project_id}/applications/{id}` | 現在の version を必須とし、競合は 409 | version を更新し、旧版の接続確認を無効化 |
| provider 接続登録 | 種別、資格情報または外部 Secret 参照、最小 scope | 秘密値を返さず、管理元・更新時刻・状態を返す |
| 検証開始 | app ID、設定 version、選択 provider | 短期・一回限りの検証 transaction |
| 有効化 | 現版の検証成功と必要な本番条件 | `enabled`。未検証・古い版は 409 |
| 無効化 | 管理権限、対象 app、確認 | 新規認証と code/token 交換を拒否。既発行 token の失効条件も表示 |

redirect URI は登録済み値との完全一致。wildcard、fragment、userinfo、危険な scheme を拒否する。
本番は HTTPS のみ。開発では `localhost` / `127.0.0.1` / `[::1]` の明示登録した HTTP と port を許可し、文字列 prefix 判定は使わない。
allowed_origins は scheme・host・port の origin として検証し、path や wildcard を受け付けない。
初期 scope は `openid`、任意の `profile` / `email`。scope と claims の対応を OpenAPI と接続例に記載する。
ログには request_id、app ID、provider、設定 version、分類済み error code を残し、credential/token/code を残さない。

## 正常系

1. 起動時に鍵と依存サービスを確認する。初回管理者登録はローカル出力された短期・一回限りの bootstrap capability に限定し、登録後は入口を閉じる。公開された未認証の first-user-wins 登録は作らない。
2. 管理者がアプリを登録し provider を選ぶ。外部サービスで登録する Callback URL をコピーできるようにする。
3. 管理者が資格情報を入力し、構文・設定の整合検証を行う。保存を実接続成功と表示しない。
4. アプリが state、nonce、PKCE verifier を生成して自身の transaction に保持し、S256 challenge を付けて認証を開始する。
5. yesod-auth が client、redirect URI、scope、設定 version を検証して transaction を保存する。upstream OAuth の state/PKCE は downstream client のものと分離する。
6. 外部認証からの応答を検証する。本人識別には provider 内の不変 ID を使い、メール一致だけで既存アカウントへ自動連携しない。追加連携は既存アカウントへの再認証と明示操作を必要とする。
7. yesod-auth は登録済み redirect URI へ短期・一回限りの認可 code と元の state を返す。Access/Refresh/ID Token を URL に含めない。
8. アプリが state を検証し、token endpoint に code、元の redirect_uri、client_id、verifier を送る。confidential client は追加で client 認証を行う。
9. yesod-auth は code の期限・未使用・client・redirect・PKCE の一致を検証し、一つの原子的操作で消費する。成功応答は `Cache-Control: no-store`。
10. アプリは署名、issuer、audience、期限、nonce を検証し、ログインを成立させる。server-side Web では token をサーバーに保持し、ブラウザには HttpOnly/Secure の session cookie を渡す。
11. 検証 UI は transaction と設定 version を照合し、成功日時と対象 app/provider を記録する。成功をクエリパラメータだけで自己申告できないようにする。

code の初期 TTL は 60 秒、認証 transaction は 5 分を初期値とし、範囲検証付きの設定にする。
値は短命だから URL に秘密 token を置いてよい、という意味ではない。code 自体もログから除外する。
Web client には Authorization Code + PKCE S256 を提供し、独自 ticket と標準 OIDC の二重の公開契約を増やさない。

## OIDC の対応範囲

Authorization Code、PKCE S256、discovery、JWKS、ID Token、UserInfo を最初の相互運用対象とする。
OAuth authorization と OIDC authentication、ID Token と API Access Token を区別する。
暗号処理や検証を独自実装せず、保守状況、対応範囲、ライセンス、相互運用テストを比較して実装部品を選ぶ。
認証中の provider/鍵更新は transaction が参照する設定版を保持するか、安全に失敗させて再開を案内する。
鍵は `kid` ごとに管理し、署名鍵を client に配布しない。検証側には公開鍵のみを渡す。
logout は app session、yesod-auth session、refresh family、upstream session のどこまでを失効させたか区別する。upstream の logout 完了は保証しない。
即時失効と短命 access token の期限待ちの差を管理 UI に明示し、具体的な失効方式は M1 の token/session 設計で決定する。

## 異常系・境界条件

| ID | 条件 | 必須結果 |
|---|---|---|
| REG-01 | 他プロジェクトの app/provider を管理する | 403 または存在を隠す 404。更新なし |
| REG-02 | redirect に wildcard、fragment、userinfo、不正 scheme | 保存拒否。該当入力と修正方法を表示 |
| REG-03 | 設定が検証後に変わる / 同時更新 | 旧成功を無効化。古い version の更新・有効化は 409 |
| AUTH-01 | client 不明、無効 app、未登録 redirect | 信頼できない URL に redirect せずローカルエラー |
| AUTH-02 | state/nonce/provider 不一致、利用者が拒否 | 成功にしない。秘密値を出さず再試行導線を表示 |
| AUTH-03 | code 期限切れ・再利用・同時二重交換 | 成功は高々一回。安定した OAuth error を返す |
| AUTH-04 | verifier 不一致、client/redirect 差替え | token 発行拒否。平文 PKCE への fallback 禁止 |
| AUTH-05 | issuer/audience/署名/期限/nonce 不一致 | client がログイン成立を拒否 |
| AUTH-06 | 同メールの別 provider/別プロジェクト | 自動連携しない。既存本人確認なしに権限を引き継がない |
| OPS-01 | DB/Valkey 障害や transaction 保存失敗 | fail closed。ユーザー作成済み等の部分状態を監査し、無制限再試行しない |
| OPS-02 | provider 資格情報不正、timeout、外部拒否 | 設定段階と実接続段階を区別。再試行できる手順を表示 |
| OPS-03 | 本番で mock/debug、既知鍵、弱い管理 password | 起動または操作を拒否。診断に秘密値を含めない |
| ADM-01 | 管理者 session が不正・期限切れ・logout 済み | 操作前に再認証。URL の session 値を信用しない |

失敗は段階、安定した error code、修正対象、再試行可能性、request_id で表示する。
色だけで区別せず、入力との関連付け、キーボード操作、フォーカス復帰、スクリーンリーダーへの通知を検証する。

## 実装前・実装後のゲート

M1 開始前に、OIDC 実装部品、公開 endpoint/metadata、失効方式、鍵保管、管理者の永続 session を ADR で決める。
これらの未決定を現在の実装で解決済みとは扱わない。
M1 実装では上表の失敗を先に再現し、実 PostgreSQL/Valkey の並行性検証を追加する。
M2 では初回導入・中断再開・修正をブラウザで確認し、M3 では独立した二つの標準 OIDC client で接続する。
Mock 成功、設定保存、ドキュメント記載のいずれかだけで実 OAuth 接続完了とはしない。

## 初回管理者登録の実装契約（#803）

`GET /api/v1/admin/bootstrap` が最小登録画面、`POST` が登録 API です。
capability の発行はサーバー内の `python -m app.bootstrap` に限定し、HTTP の発行 endpoint は設けません。
256 bit の乱数をローカル TTY にだけ出力し、DB には SHA-256 digest と 15 分の期限を保持します。

`admin_bootstrap` の単一行をロックし、DB 時刻による期限確認、`administrators` の作成、capability の消費を一つの transaction で行います。
再発行も同じロックを使い、登録後は拒否します。
管理者の削除やプロセス再起動から独立した `initialized_at` を残すため、登録入口は再開しません。
password は 16 byte の salt と 600,000 回の PBKDF2-HMAC-SHA256 で保存し、OAuth 利用者の identity と分離します。
最初の管理者は既定 project を参照します。所属認可と永続 session は #806 / #804 の範囲です。

JSON body は 4,096 byte 以下、capability は URL-safe base64 の 43 文字、管理者名は英数字で始まる ASCII 3–64 文字です。
password は 16–128 Unicode 文字かつ UTF-8 512 byte 以下とし、空白だけ・管理者名と同じ値を拒否します。
余分な入力、query parameters、異なる origin からのブラウザ送信を拒否し、例外に入力を含めません。
画面は `no-store`、外部 asset 禁止、CSP、送信時・履歴移動時の秘密入力消去を使用します。
ブラウザの password manager、利用者自身の clipboard や撮影など、アプリの管理外の保存は消去保証の対象にしません。

成功は 201、登録閉鎖は 410、無効・期限切れ capability は 403、入力不正は 400、DB 利用不能は 503 です。
登録成功を管理コンソールへのログイン完了と表示しません。
