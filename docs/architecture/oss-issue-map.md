# 既存 Issue 対応表

確認日: 2026-10-23 JST。GitHub の open Issue 全 121 件の本文・目的・変更範囲を取得して整理した。
これは採否と順序の台帳であり、実装完了の一覧ではない。進捗は live state と検証結果で更新する。

追跡 Issue: [#798](https://github.com/mashirou1234/yesod-auth/issues/798)。M0 は [milestone 1](https://github.com/mashirou1234/yesod-auth/milestone/1) に登録した。
#676/#693/#767 の受入条件を更新し、#677/#791 を統合による `not_planned` として close したことを API で再確認した。
#676/#678/#679/#684/#692/#693/#767 は open のまま保持する。整理後は open 120 件（追跡 Issue を 1 件追加、2 件統合）。

## 統合と依存

- #677 は #676 の本番 JWT 安全条件に統合する。同一検証処理を別々に実装しない。
- #791 は旧 URL session token の異常入力テストが対象のため、#693 の新しい server-side session の異常状態・期限切れテストへ統合する。
- #693 は「cookie 移行の準備」から「URL session の撤去と絶対期限」へ更新する。HttpOnly cookie を作ったとは扱わない。永続管理 session は M1 設計で扱う。
- #767 を CI の正本として拡張する。#705 の依存監査、#769 の実 DB smoke、#771 の文書 build は独立した受入条件を残す。
- #741/#742 の設定初期化と #775 のテスト隔離は今回必要な部分だけ取り込む。残りの受入条件を確認せず完了にはしない。
- 同じファイルを触るだけの Issue は重複とせず、関連・依存として保持する。
- 統合先に全受入条件を移してから統合元を not planned として close する。実装完了の close と区別する。
- 実装対象も merge 前には完了 close しない。PR と CI は別の証拠として扱う。

## GitHub Project の確認制約

`gh` の認証に `read:project` scope がなく、repo projectsV2 と issue projectItems の一括取得は拒否された。
Project の有無・status・priority は未確認であり、N/A と推定しない。
自動 queue の claim・priority 変更は行わず、ユーザーが直接指定した M0 を手動レーンで進める。
Project を使う自動 queue 再開前に権限のある認証で再取得する。認証 scope はこの作業で変更しない。

## 今回の実装と次の作業

今回: #676/#677、#678、#679、#684、#692、#693/#791、#767。
次の公開阻止条件: #680 の標準コード交換、#681/#682 の refresh 整合性、#683 の秘密情報保存、#694 の管理者 login 制限。
計画とアプリ登録仕様を束ねる専用 Issue がないため、追跡 Issue を一つ追加する。
具体的な実装結果、GitHub 整理結果、hosted CI の確認状況は `.agent/WORKLOG.md` に記録する。

## 全件の対応

「保持」は独立要件として残し、対象段階で具体的な受入条件を確認する意味。「関連」は統合・完了ではない。

| Issue | 目的 | 段階 | 扱い |
|---|---|---|---|
| [#676](https://github.com/mashirou1234/yesod-auth/issues/676) | [Backlog-120][SEC-01] JWT_SECRET の production default を fail-fast にする | M0 | 保持 |
| [#677](https://github.com/mashirou1234/yesod-auth/issues/677) | [Backlog-120][SEC-02] JWT_SECRET の最小長と空白混入を検証する | M0 | #676 に統合 |
| [#678](https://github.com/mashirou1234/yesod-auth/issues/678) | [Backlog-120][SEC-03] MOCK_OAUTH_ENABLED を production で明示禁止する | M0 | 保持 |
| [#679](https://github.com/mashirou1234/yesod-auth/issues/679) | [Backlog-120][SEC-04] debug-tokens endpoint を開発専用ゲートへ分離する | M0 | 保持 |
| [#680](https://github.com/mashirou1234/yesod-auth/issues/680) | [Backlog-120][SEC-05] OAuth callback の token query redirect を短期 ticket 化する境界を作る | M1 | 保持 |
| [#681](https://github.com/mashirou1234/yesod-auth/issues/681) | [Backlog-120][SEC-06] refresh token rotation を単一 transaction にする | M1 | 保持 |
| [#682](https://github.com/mashirou1234/yesod-auth/issues/682) | [Backlog-120][SEC-07] refresh token reuse 検知と同一ユーザー失効の足場を作る | M1 | 保持 |
| [#683](https://github.com/mashirou1234/yesod-auth/issues/683) | [Backlog-120][SEC-08] OAuth provider token の保存方針を暗号化前提に整理する | M1 | 保持 |
| [#684](https://github.com/mashirou1234/yesod-auth/issues/684) | [Backlog-120][SEC-09] JWT decode に issuer / audience 検証を追加する | M0 | 保持 |
| [#685](https://github.com/mashirou1234/yesod-auth/issues/685) | [Backlog-120][SEC-10] JWT kid の許可リストを設定化する | M1 | 保持 |
| [#686](https://github.com/mashirou1234/yesod-auth/issues/686) | [Backlog-120][SEC-11] CORS_ORIGINS の scheme/host validation を強化する | M1 | 保持 |
| [#687](https://github.com/mashirou1234/yesod-auth/issues/687) | [Backlog-120][SEC-12] CORS allow_methods / allow_headers の production 推奨値を設定化する | M1 | 保持 |
| [#688](https://github.com/mashirou1234/yesod-auth/issues/688) | [Backlog-120][SEC-13] Webhook endpoint URL の private network 宛てを拒否する | M1 | 保持 |
| [#689](https://github.com/mashirou1234/yesod-auth/issues/689) | [Backlog-120][SEC-14] Webhook delivery の redirect 追従方針を明示する | M4 | 保持 |
| [#690](https://github.com/mashirou1234/yesod-auth/issues/690) | [Backlog-120][SEC-15] Webhook secret の literal 値許可を production で禁止する | M1 | 保持 |
| [#691](https://github.com/mashirou1234/yesod-auth/issues/691) | [Backlog-120][SEC-16] Webhook signature timestamp skew の契約を固定する | M4 | 保持 |
| [#692](https://github.com/mashirou1234/yesod-auth/issues/692) | [Backlog-120][SEC-17] admin デフォルトパスワードを production で fail-fast にする | M0 | 保持 |
| [#693](https://github.com/mashirou1234/yesod-auth/issues/693) | [Backlog-120][SEC-18] admin session token を URL query から cookie 境界へ移す準備をする | M0 | 保持 |
| [#694](https://github.com/mashirou1234/yesod-auth/issues/694) | [Backlog-120][SEC-19] admin login 失敗に rate limit / lockout の足場を追加する | M1 | 保持 |
| [#695](https://github.com/mashirou1234/yesod-auth/issues/695) | [Backlog-120][SEC-20] admin API テスト画面の token 入力を明示消去できるようにする | M4 | 保持 |
| [#696](https://github.com/mashirou1234/yesod-auth/issues/696) | [Backlog-120][SEC-21] OAuth state store の provider/action/schema を厳格化する | M1 | 保持 |
| [#697](https://github.com/mashirou1234/yesod-auth/issues/697) | [Backlog-120][SEC-22] OAuth callback error detail に provider 由来文字列を直接出さない | M1 | 保持 |
| [#698](https://github.com/mashirou1234/yesod-auth/issues/698) | [Backlog-120][SEC-23] metrics endpoint の認証要否を運用 profile で選べるようにする | M4 | 保持 |
| [#699](https://github.com/mashirou1234/yesod-auth/issues/699) | [Backlog-120][SEC-24] 監査ログ details に token/header 値が混入しない redaction helper を追加する | M1 | 保持 |
| [#700](https://github.com/mashirou1234/yesod-auth/issues/700) | [Backlog-120][SEC-25] OAuth provider HTTP error log の secret redaction を全 provider で統一する | M1 | 保持 |
| [#701](https://github.com/mashirou1234/yesod-auth/issues/701) | [Backlog-120][SEC-26] DB 接続 URL の password を診断表示で redact する | M4 | 保持 |
| [#702](https://github.com/mashirou1234/yesod-auth/issues/702) | [Backlog-120][SEC-27] OAuth account link callback に provider 一致検証を追加する | M1 | 保持 |
| [#703](https://github.com/mashirou1234/yesod-auth/issues/703) | [Backlog-120][SEC-28] account unlink の最終認証手段ガードを race に強くする | M1 | 保持 |
| [#704](https://github.com/mashirou1234/yesod-auth/issues/704) | [Backlog-120][SEC-29] soft delete 後の access token 利用不可契約を全保護 API で固定する | M1 | 保持 |
| [#705](https://github.com/mashirou1234/yesod-auth/issues/705) | [Backlog-120][SEC-30] 依存関係の脆弱性チェックを CI/手順に追加する | M4 | #767 と関連 |
| [#706](https://github.com/mashirou1234/yesod-auth/issues/706) | [Backlog-120][PRD-01] OAuth provider 別の enable/disabled 状態を health 診断へ出す | M2 | 保持 |
| [#707](https://github.com/mashirou1234/yesod-auth/issues/707) | [Backlog-120][PRD-02] OAuth provider registry と docs の provider 一覧 drift を検出する | M2 | 保持 |
| [#708](https://github.com/mashirou1234/yesod-auth/issues/708) | [Backlog-120][PRD-03] OAuth callback URL mismatch の metric を全 provider に広げる | M2 | 保持 |
| [#709](https://github.com/mashirou1234/yesod-auth/issues/709) | [Backlog-120][PRD-04] OAuth callback missing params の分類を全 provider へ統一する | M2 | 保持 |
| [#710](https://github.com/mashirou1234/yesod-auth/issues/710) | [Backlog-120][PRD-05] refresh token retry 設定の上限/下限を検証する | M2 | 保持 |
| [#711](https://github.com/mashirou1234/yesod-auth/issues/711) | [Backlog-120][PRD-06] sessions list の total semantics を paging 向けに拡張する | M4 | 保持 |
| [#712](https://github.com/mashirou1234/yesod-auth/issues/712) | [Backlog-120][PRD-07] session revoke 応答に already_revoked を含める | M4 | 保持 |
| [#713](https://github.com/mashirou1234/yesod-auth/issues/713) | [Backlog-120][PRD-08] users sync-from-provider の provider 判定を registry へ寄せる | M3 | 保持 |
| [#714](https://github.com/mashirou1234/yesod-auth/issues/714) | [Backlog-120][PRD-09] deleted_users の purge overdue 件数を metrics に追加する | M4 | 保持 |
| [#715](https://github.com/mashirou1234/yesod-auth/issues/715) | [Backlog-120][PRD-10] Webhook queue backlog 長を metrics に追加する | M4 | 保持 |
| [#716](https://github.com/mashirou1234/yesod-auth/issues/716) | [Backlog-120][PRD-11] Webhook delivery_timeout_seconds の上限/下限を検証する | M4 | 保持 |
| [#717](https://github.com/mashirou1234/yesod-auth/issues/717) | [Backlog-120][PRD-12] Webhook delivery log に retry delay / next retry 診断情報を残す | M4 | 保持 |
| [#718](https://github.com/mashirou1234/yesod-auth/issues/718) | [Backlog-120][PRD-13] Webhook reload の成功/失敗を audit event 化する | M4 | 保持 |
| [#719](https://github.com/mashirou1234/yesod-auth/issues/719) | [Backlog-120][PRD-14] Webhook deliveries API に endpoint_id filter を追加する | M4 | 保持 |
| [#720](https://github.com/mashirou1234/yesod-auth/issues/720) | [Backlog-120][PRD-15] Webhook deliveries API に status filter を追加する | M4 | 保持 |
| [#721](https://github.com/mashirou1234/yesod-auth/issues/721) | [Backlog-120][PRD-16] Webhook delivery error_message を failure_code と raw message に分ける | M4 | 保持 |
| [#722](https://github.com/mashirou1234/yesod-auth/issues/722) | [Backlog-120][PRD-17] Valkey 接続失敗時の OAuth state 保存エラーを user-facing に分類する | M4 | 保持 |
| [#723](https://github.com/mashirou1234/yesod-auth/issues/723) | [Backlog-120][PRD-18] OAUTH_STATE_TTL を health/metrics/docs で確認できるようにする | M2 | 保持 |
| [#724](https://github.com/mashirou1234/yesod-auth/issues/724) | [Backlog-120][PRD-19] login_history と auth_events の request_id 連携を統一する | M4 | 保持 |
| [#725](https://github.com/mashirou1234/yesod-auth/issues/725) | [Backlog-120][PRD-20] audit event type を Webhook / admin 操作へ拡張する | M4 | 保持 |
| [#726](https://github.com/mashirou1234/yesod-auth/issues/726) | [Backlog-120][PRD-21] admin overview の stats 失敗分類を画面とログで分ける | M4 | 保持 |
| [#727](https://github.com/mashirou1234/yesod-auth/issues/727) | [Backlog-120][PRD-22] admin sessions 画面に active/revoked/expired summary を追加する | M4 | 保持 |
| [#728](https://github.com/mashirou1234/yesod-auth/issues/728) | [Backlog-120][PRD-23] admin ユーザー詳細に linked provider count と primary email を明示する | M4 | 保持 |
| [#729](https://github.com/mashirou1234/yesod-auth/issues/729) | [Backlog-120][PRD-24] admin Valkey reconnect 待機の現在値を診断表示する | M4 | 保持 |
| [#730](https://github.com/mashirou1234/yesod-auth/issues/730) | [Backlog-120][PRD-25] Docker compose ci profile の Valkey 依存を明示する | M4 | 保持 |
| [#731](https://github.com/mashirou1234/yesod-auth/issues/731) | [Backlog-120][PRD-26] Docker compose の sample DB password を self-host docs で警告する | M2 | 保持 |
| [#732](https://github.com/mashirou1234/yesod-auth/issues/732) | [Backlog-120][PRD-27] generated/api.d.ts の再生成差分チェックを導入する | M3 | 保持 |
| [#733](https://github.com/mashirou1234/yesod-auth/issues/733) | [Backlog-120][PRD-28] OpenAPI schema に sessions limit maximum を標準 metadata として出す | M4 | 保持 |
| [#734](https://github.com/mashirou1234/yesod-auth/issues/734) | [Backlog-120][PRD-29] OAuth provider disabled 応答に安定 code と復旧導線を追加する | M2 | 保持 |
| [#735](https://github.com/mashirou1234/yesod-auth/issues/735) | [Backlog-120][PRD-30] rate limit exceeded 応答に provider と retry-after を安定表示する | M2 | 保持 |
| [#736](https://github.com/mashirou1234/yesod-auth/issues/736) | [Backlog-120][ARC-01] api/app/auth/router.py の provider callback 共通処理を use-case helper へ抽出する | M1 | 保持 |
| [#737](https://github.com/mashirou1234/yesod-auth/issues/737) | [Backlog-120][ARC-02] OAuth provider class 群を registry factory から解決する | M1 | 保持 |
| [#738](https://github.com/mashirou1234/yesod-auth/issues/738) | [Backlog-120][ARC-03] auth callback の token response/redirect 生成を presenter 関数へ分離する | M1 | 保持 |
| [#739](https://github.com/mashirou1234/yesod-auth/issues/739) | [Backlog-120][ARC-04] _get_client_info の重複を request context helper へ集約する | M1 | 保持 |
| [#740](https://github.com/mashirou1234/yesod-auth/issues/740) | [Backlog-120][ARC-05] request_id 生成/取得を共通 boundary へ集約する | M1 | 保持 |
| [#741](https://github.com/mashirou1234/yesod-auth/issues/741) | [Backlog-120][ARC-06] API Settings の class attribute 初期化を instance 初期化へ寄せる | M0 | #676 と関連 |
| [#742](https://github.com/mashirou1234/yesod-auth/issues/742) | [Backlog-120][ARC-07] admin Settings も instance 初期化へ寄せる | M0 | #692 と関連 |
| [#743](https://github.com/mashirou1234/yesod-auth/issues/743) | [Backlog-120][ARC-08] WebhookConfigLoader の class state を repository/service 境界へ分離する | M4 | 保持 |
| [#744](https://github.com/mashirou1234/yesod-auth/issues/744) | [Backlog-120][ARC-09] Webhook retry delay 計算を pure policy object へ分離する | M4 | 保持 |
| [#745](https://github.com/mashirou1234/yesod-auth/issues/745) | [Backlog-120][ARC-10] Webhook HTTP delivery client を injectable port にする | M4 | 保持 |
| [#746](https://github.com/mashirou1234/yesod-auth/issues/746) | [Backlog-120][ARC-11] AuditLogger の SQL text を repository 関数へ分離する | M4 | 保持 |
| [#747](https://github.com/mashirou1234/yesod-auth/issues/747) | [Backlog-120][ARC-12] metrics の SQL query 群を query function へ分離する | M4 | 保持 |
| [#748](https://github.com/mashirou1234/yesod-auth/issues/748) | [Backlog-120][ARC-13] models/user.py の OAuthAccount を別 module へ分離する | M4 | 保持 |
| [#749](https://github.com/mashirou1234/yesod-auth/issues/749) | [Backlog-120][ARC-14] models/user.py の DeletedUser を別 module へ分離する | M1 | 保持 |
| [#750](https://github.com/mashirou1234/yesod-auth/issues/750) | [Backlog-120][ARC-15] users router の soft delete use case を service へ抽出する | M1 | 保持 |
| [#751](https://github.com/mashirou1234/yesod-auth/issues/751) | [Backlog-120][ARC-16] users profile update の changes diff を pure helper へ抽出する | M4 | 保持 |
| [#752](https://github.com/mashirou1234/yesod-auth/issues/752) | [Backlog-120][ARC-17] accounts router の link callback 重複を provider strategy へ分ける | M1 | 保持 |
| [#753](https://github.com/mashirou1234/yesod-auth/issues/753) | [Backlog-120][ARC-18] accounts audit actor/target builder を audit helper へ移す | M1 | 保持 |
| [#754](https://github.com/mashirou1234/yesod-auth/issues/754) | [Backlog-120][ARC-19] sessions router の revoke query を token service へ寄せる | M1 | 保持 |
| [#755](https://github.com/mashirou1234/yesod-auth/issues/755) | [Backlog-120][ARC-20] auth/tokens.py の hash/rotation/time provider を testable にする | M1 | 保持 |
| [#756](https://github.com/mashirou1234/yesod-auth/issues/756) | [Backlog-120][ARC-21] OAuth provider HTTP client base を small methods に分割する | M1 | 保持 |
| [#757](https://github.com/mashirou1234/yesod-auth/issues/757) | [Backlog-120][ARC-22] OAuth provider response normalization を provider 別 adapter へ分離する | M1 | 保持 |
| [#758](https://github.com/mashirou1234/yesod-auth/issues/758) | [Backlog-120][ARC-23] Pydantic schemas に error detail model を追加する | M1 | 保持 |
| [#759](https://github.com/mashirou1234/yesod-auth/issues/759) | [Backlog-120][ARC-24] DB session cleanup の rollback/close 契約を境界で見直す | M1 | 保持 |
| [#760](https://github.com/mashirou1234/yesod-auth/issues/760) | [Backlog-120][ARC-25] config validation error を集約して起動時に複数問題を見せる | M1 | 保持 |
| [#761](https://github.com/mashirou1234/yesod-auth/issues/761) | [Backlog-120][ARC-26] admin/db.py の SQL query を read/write repository に分ける | M1 | 保持 |
| [#762](https://github.com/mashirou1234/yesod-auth/issues/762) | [Backlog-120][ARC-27] admin i18n key の未使用/不足を検出する script を追加する | M4 | 保持 |
| [#763](https://github.com/mashirou1234/yesod-auth/issues/763) | [Backlog-120][ARC-28] webhook event model の payload serialization を schema object へ寄せる | M4 | 保持 |
| [#764](https://github.com/mashirou1234/yesod-auth/issues/764) | [Backlog-120][ARC-29] webhook signer の verify failure を typed exception にする | M4 | 保持 |
| [#765](https://github.com/mashirou1234/yesod-auth/issues/765) | [Backlog-120][ARC-30] mock OAuth 実装を auth/router.py から mock_oauth module へ寄せる | M1 | 保持 |
| [#766](https://github.com/mashirou1234/yesod-auth/issues/766) | [Backlog-120][QAT-01] pytest marker と test category を整理する | M4 | 保持 |
| [#767](https://github.com/mashirou1234/yesod-auth/issues/767) | [Backlog-120][QAT-02] ruff format/check の実行手順を repo root から統一する | M0 | 保持 |
| [#768](https://github.com/mashirou1234/yesod-auth/issues/768) | [Backlog-120][QAT-03] api tests の SQLite/Postgres 差分を明文化する | M1 | 保持 |
| [#769](https://github.com/mashirou1234/yesod-auth/issues/769) | [Backlog-120][QAT-04] Postgres integration test profile の最小 smoke を追加する | M1 | #767 と関連 |
| [#770](https://github.com/mashirou1234/yesod-auth/issues/770) | [Backlog-120][QAT-05] Alembic migration head と models metadata の drift check を追加する | M1 | 保持 |
| [#771](https://github.com/mashirou1234/yesod-auth/issues/771) | [Backlog-120][QAT-06] docs strict build を標準 verification に戻す | M4 | 保持 |
| [#772](https://github.com/mashirou1234/yesod-auth/issues/772) | [Backlog-120][QAT-07] OAuth provider fixture の respx setup を共通化する | M3 | 保持 |
| [#773](https://github.com/mashirou1234/yesod-auth/issues/773) | [Backlog-120][QAT-08] Webhook worker の timeout/request error table tests を追加する | M4 | 保持 |
| [#774](https://github.com/mashirou1234/yesod-auth/issues/774) | [Backlog-120][QAT-09] Webhook config validation の table tests を増やす | M4 | 保持 |
| [#775](https://github.com/mashirou1234/yesod-auth/issues/775) | [Backlog-120][QAT-10] admin tests の Streamlit 依存を helper で隔離する | M0 | #693 と関連 |
| [#776](https://github.com/mashirou1234/yesod-auth/issues/776) | [Backlog-120][QAT-11] scripts/github_fallback.py の issue 操作契約をテストする | 運営 | 保持 |
| [#777](https://github.com/mashirou1234/yesod-auth/issues/777) | [Backlog-120][QAT-12] queue_seed_snapshot.py の dry-run 出力を固定する | 運営 | 保持 |
| [#778](https://github.com/mashirou1234/yesod-auth/issues/778) | [Backlog-120][QAT-13] API error response examples を snapshot 的に検証する | M2 | 保持 |
| [#779](https://github.com/mashirou1234/yesod-auth/issues/779) | [Backlog-120][QAT-14] README quick start のコマンドを shellcheck 可能な形に整理する | M2 | 保持 |
| [#780](https://github.com/mashirou1234/yesod-auth/issues/780) | [Backlog-120][QAT-15] Dockerfile の dependency install cache と pin 方針を確認する | M4 | 保持 |
| [#781](https://github.com/mashirou1234/yesod-auth/issues/781) | [Backlog-120][QAT-16] OAuth docs の provider callback URL を registry から検証する | M2 | 保持 |
| [#782](https://github.com/mashirou1234/yesod-auth/issues/782) | [Backlog-120][QAT-17] admin locale の security-sensitive 文言を en/ja で揃える | M4 | 保持 |
| [#783](https://github.com/mashirou1234/yesod-auth/issues/783) | [Backlog-120][QAT-18] OAuth state mismatch の regression matrix を provider 横断にする | M1 | 保持 |
| [#784](https://github.com/mashirou1234/yesod-auth/issues/784) | [Backlog-120][QAT-19] account link callback URL normalization の tests を auth callback と揃える | M1 | 保持 |
| [#785](https://github.com/mashirou1234/yesod-auth/issues/785) | [Backlog-120][QAT-20] 大量 queue の棚卸し用 GitHub query を docs に追加する | 運営 | 保持 |
| [#786](https://github.com/mashirou1234/yesod-auth/issues/786) | [Backlog-120][QAT-21] API auth error contract の property-based 境界テストを追加する | M1 | 保持 |
| [#787](https://github.com/mashirou1234/yesod-auth/issues/787) | [Backlog-120][QAT-22] refresh token expiry の clock boundary tests を増やす | M1 | 保持 |
| [#788](https://github.com/mashirou1234/yesod-auth/issues/788) | [Backlog-120][QAT-23] CORS_ORIGINS parser の fuzz/table tests を増やす | M1 | 保持 |
| [#789](https://github.com/mashirou1234/yesod-auth/issues/789) | [Backlog-120][QAT-24] Webhook signer の cross-language example と実装を照合する | M4 | 保持 |
| [#790](https://github.com/mashirou1234/yesod-auth/issues/790) | [Backlog-120][QAT-25] metrics output の label cardinality regression test を追加する | M4 | 保持 |
| [#791](https://github.com/mashirou1234/yesod-auth/issues/791) | [Backlog-120][QAT-26] admin session token validation の malformed input tests を増やす | M0 | #693 に統合 |
| [#792](https://github.com/mashirou1234/yesod-auth/issues/792) | [Backlog-120][QAT-27] OAuth provider disabled の全 provider parametrized test を追加する | M2 | 保持 |
| [#793](https://github.com/mashirou1234/yesod-auth/issues/793) | [Backlog-120][QAT-28] soft delete と webhook emission の順序テストを追加する | M1 | 保持 |
| [#794](https://github.com/mashirou1234/yesod-auth/issues/794) | [Backlog-120][QAT-29] accounts unlink の audit details table tests を追加する | M1 | 保持 |
| [#795](https://github.com/mashirou1234/yesod-auth/issues/795) | [Backlog-120][QAT-30] weekly_git_inventory の open issue label counts を testable にする | 運営 | 保持 |
| [#796](https://github.com/mashirou1234/yesod-auth/issues/796) | 週次Git棚卸し | 運営 | 保持 |
