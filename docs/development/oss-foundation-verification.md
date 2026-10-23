# OSS M0 基盤整備の検証記録

検証日: 2026-10-23 JST。追跡: [#798](https://github.com/mashirou1234/yesod-auth/issues/798)、[M0](https://github.com/mashirou1234/yesod-auth/milestone/1)。

## 対象と結果の意味

旧 API 互換を要求しない公開前の増分として、計画保存、Issue 整理、CI、設定検証、管理者セッション、アプリ登録からログインまでの仕様を扱った。
アプリ登録 API、OIDC、コード交換、新コンソールは仕様であり、この増分の実装には含まれない。
本番利用可能・正式リリースの判定は行っていない。

最終ソース候補は `oss-m0-candidate-2`。
変更対象 43 パスの SHA-256 または削除マーカーから計算した digest は次の値。

```text
sha256:799e6c6a30be80a37c301f808e9aa0818b3525e1baa06dec72b90834e3922c87
```

元のコードは `e3a896f83875aee27fb9fd4152933de24dbdd711`。
共有作業ツリーの変動を避け、対象だけを複製した隔離スナップショットで最終検証を実行した。
検証終了後にも 43 パスの hash が変わっていないことを確認した。
この報告と検証 JSON は証拠を残すための追加文書であり、上記のソース manifest には含めない。
詳細な manifest と終了コード・ログ hash の要約は [検証データ](oss-foundation-verification.json) に保存する。

## 決定論的検証

Python 3.12.15、pytest 9.1.1、Bun 1.4.4、Ruff 0.14.2、PostgreSQL 16、Valkey 8 を使用した。
各成功は subprocess の終了コード 0 とログを採取した結果である。

| 確認 | 最終結果 | 範囲 |
|---|---|---|
| 共通 verification `all` | 成功 | lint、build、unit、integration を連続実行 |
| API pytest | 393 passed | SQLite と mock による契約・回帰テスト |
| admin pytest | 59 passed | 設定、絶対期限、URL 認証拒否、logout、実 Streamlit AppTest |
| 実サービス統合 | 1 passed | migration 001→006、token lifecycle、監査 insert、実 DB を使う API、Valkey TTL/消費 |
| Ruff / format | 成功 | API/admin lint、API format 91 ファイル。無関係な admin 一括整形は対象外 |
| tour build/static | 成功 | frozen lockfile、生成元・生成物・vendor/license の一致 |
| Python/OpenAPI | 成功 | 構文コンパイルと OpenAPI 読み込み |
| Woodpecker strict lint | 成功 | Python pipeline の設定構造 |
| API/admin Docker build | 両方成功 | 最終ソースと別チャットの証明書対策を含む依存定義 |
| API image 内 pytest | 393 passed | Compose 参照テスト用に固定した Compose ファイルを読み取り専用マウント |
| MkDocs strict build | 成功 | 既存アンカーの INFO 診断は残存。新規文書の相対リンクも検査 |
| Issue 台帳 | 成功 | 初期 121 件すべて一度だけ記載し、取得した ID 集合と一致 |

API image での初回実行は、イメージ外の `/docker-compose.yml` を参照するテスト 3 件だけが失敗した（349 passed）。
固定した Compose を読み取り専用で渡して再実行し、352 件だった候補 1、その後の最終候補 393 件で成功を確認した。
テスト入力不足の修正であり、失敗した検証を成功として数えていない。

実 DB/cache は専用 Compose project に作成し、終了時にその project のコンテナー・ネットワーク・volume だけを削除した。
既存サービスや実データは変更していない。

## Red と Green の証拠

初期実装時の API 17 件・admin 9 件の失敗ログは保持したが、その当時は `pytest; tail` を含む複合 shell の終了コードだけを採取していた。
pytest 自体の終了コードは未記録であり、後から推測して補っていない。

修正前の候補 1 に対する追加 Red は、実際の pytest 終了コード 1 を直接採取した。
API は 36 failed / 5 passed、admin は 6 failed / 2 passed。
実行時の実装 SHA が候補 1 の該当 config と一致することも確認した。
コマンド、時刻、Python/pytest の版、ログ SHA を残し、修正後の重点検証は API 95 passed / admin 36 passed、さらに上記の最終通し検証を実施した。

管理者セッションについては、元コミットを別ディレクトリに展開して旧障害を再構成した。
期限切れ token と旧 `authenticated` 状態を与えると、旧コードは `db.get_stats` を呼び、保護データを読まないという assertion が失敗した（exit 1）。
同じ probe のアプリ参照先だけを最終候補に替えると成功した（exit 0）。
これは後から再構成した baseline 再現であり、初回実装前に実行した証拠とは区別する。

## レビューと修正

実装者とは別の reviewer が契約、失敗時の動作、証拠の三つの観点を確認した。
初回の候補を保持し、修正後は該当指摘と関連差分だけを確認する。
限定した再確認で契約・証拠の指摘は解消した。別の packet-only 最終評価者は `READY / PASS` と判定した。
判定対象はこの初期増分のローカル採用であり、hosted CI、マージ、リリースの完了判定ではない。

| ID | 指摘 | 対応 |
|---|---|---|
| AR-CB-001 | 予測しやすい JWT/admin 秘密値が通る | 限定した既知パターンを拒否。ランダム生成を要求し、entropy を証明する検査とは説明しない |
| AR-CB-002 | 削除した自動承認/merge の旧案内 | README と運用ガイドを現在の CI・レビュー方針へ訂正 |
| AR-CB-003 | 古い JWT 設定名と寿命 | `ACCESS_TOKEN_LIFETIME_SECONDS=900` へ訂正 |
| MGMT-001 | 空白混入の JWT 鍵が通る | file/env の先頭・途中・末尾を検査。ファイルの最後の LF/CRLF 一つだけ許容 |
| EVID-001 | 一時ログだけで候補との対応が弱い | ログを保全し hash・終了コード・候補 digest を台帳化。最終隔離候補で通し検証 |
| EVID-002 | maker の build 保留と後発の成功が不明確 | maker 後に管理担当が両イメージをビルドした順序と独立証拠を明記 |
| FE-M0-001 | 無操作タブの既表示データは期限後も残る | 観察は保持。凍結条件は次の保護操作を拒否する絶対期限であり、画面の自動消去は新しい UX 要件として後続へ。安全設定ガイドにも明記 |

Codex Security の初回差分レビューは scan `3ec365df-5f2e-4767-8603-4541b6ee2e05`、修正差分は `9fa84553-769d-4c7c-ace3-e73f6b4191e2`。
初回は source inventory 19 件と関連依存・配置 5 件、修正分は validator 2 ファイルを確認し、新たな報告対象は 0 件だった。
これは既知の未修正問題や本番配置が安全であるという意味ではない。
実装者とは別工程の plugin review であり、脅威モデル作成自体は管理担当の逐次確認で、独立した追加モデル作成者は置いていない。

Security workbench の計測（キャッシュ入力込み）は、初回 total 4,068,754 / input 4,062,607 / cached input 4,012,032 tokens、修正差分 total 1,333,450 / input 1,332,217 / cached input 1,328,256 tokens。
計測元は `codex_rollout`、各 coverage は `complete`。この値から課金額や他チャットの使用量を推定しない。

## Issue と作業の境界

#798 と M0 milestone を作成し、#676/#693/#767 の受入条件を更新した。
#677→#676、#791→#693 は統合のため `not_planned` で close し、実装完了とは扱っていない。
その他の M0 実装 Issue は merge 確認前に完了 close しない。

GitHub Project は `read:project` 権限不足で有無・status・priority を確認できなかった。
未連携を意味する N/A に置き換えず、自動 queue の claim/priority 変更は行っていない。

別チャット「リンク先の対策を先に実施」が Dockerfile、requirements、CI の CA/pip/Bun 更新を行った。
その変更を上書きせず、完成後の内容を最終スナップショットとビルドの依存として含めた。
従前からの構造図、MkDocs ナビゲーション、図の拡大機能の未コミット変更は今回の候補に含めていない。

## 残る条件

- 外部 OAuth の実ログイン、OIDC 相互運用、公開後の運用は未検証。
- #680 の URL token 返却、#681/#682 の refresh 整合性、#683 の外部 token 保管、#694 の管理者 login 制限は後続の公開阻止条件。
- リモートのブランチ保護は変更していない。ローカル成功と hosted CI の成功は分けて扱う。
- 本報告の初稿時点で hosted CI、merge、正式リリース、デプロイは未実施。後続確認は同じ報告へ追記する。
- 管理者の永続 Cookie、MFA、役割別権限、無操作時の画面自動ロックは実装済みとしない。
