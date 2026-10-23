# 初回管理者登録の検証記録

Issue #803 の受入対象は、ローカル capability の発行、一回限りの DB 管理者作成、最小登録画面です。
既存 Streamlit へのログイン、永続管理 session、管理 API 認可は対象外です。

## 受入条件と証拠

| 条件 | 検証 |
|---|---|
| 未初期化時だけ短期・一回限りの capability を使用できる | 実 PostgreSQL で未発行、不正、期限切れ、再発行前の値、成功後の再使用を拒否。登録後の再発行、再起動、管理者削除後も閉鎖 |
| 期限切れ、再使用、同時登録を拒否し、成功は高々一回 | 8 HTTP request の並行登録で成功 1 件。独立した Python process 2 個でも成功 1 件。hash 計算中の期限切れは commit 前に拒否 |
| 作成と消費が原子的 | 消費 marker 更新を拒否するテスト専用 DB 制約を用い、管理者作成と capability 消費が両方 rollback されることを確認 |
| capability/password を残さない | TTY 専用出力、通常 stdout/stderr 非出力、DB digest/password hash、API 正常・異常レスポンスとログの非反映、Brave の URL・DOM・storage・保存画面確認 |
| 既存データ保持 | migration 006 → head の既存 oracle を現候補で実行。全 9 対象 table の全旧列、active/revoked token、削除済み subject の audit 履歴を保持 |

## 実行結果

2026-10-24、隔離 clone と専用 PostgreSQL 16 / Valkey 8 で実行しました。

- Red：新 module が存在しない段階で focused unit 2 collection errors を確認。
- Green：入力・API・CLI 22 件、API 全体 415 件、admin 68 件。
- 実 DB：bootstrap 12 件を含む integration 42 件。
- CI と同じ Ruff 0.14.2 で lint / format、Python compile、admin asset build、OpenAPI export、bootstrap JS syntax を確認。
- API / admin の Docker image を build。
- 分離 Brave で 375 / 768 / 1024 / 1440 px、キーボード focus、履歴から戻った際の消去、実 DB の期限切れ、登録成功後の form 撤去、再読み込み時の 410 を確認。
- ブラウザの console / page error とサーバーの実行エラーは 0。保存した画像は入力前の空画面のみ。テストで発行した capability/password は証拠へ保存していません。

```bash
# CI と同じ lint tool を用いる
python -m pip install ruff==0.14.2
bash scripts/verify-foundation.sh lint
bash scripts/verify-foundation.sh build
bash scripts/verify-foundation.sh unit
# 専用の使い捨て DB/Valkey URL を設定して実行
bash scripts/verify-foundation.sh integration
node --check api/app/static/admin-bootstrap.js
```

新 UI は素の HTML / CSS / JavaScript のため TypeScript の typecheck 対象はありません。
JS 構文検証、実ブラウザ動作、console/server ログ、Python の既存 gate を確認しました。
常駐 watcher は使用していません。

## 再発防止と未確認事項

Ruff の最新バージョンでは admin に新しい既定 rule が適用されました。
無関係な source を直さず、CI で固定する 0.14.2 を使用して検証環境を一致させました。

ブラウザ検証の文字列 eval は CSP に拒否されました。
CSP を緩めず、検証側を locator assertion に変えて再実行しました。
検証エラー時も、今回の専用 profile と記録した PID だけを cleanup します。

migration 版を固定した既存 integration assertion は、追加 migration に合わせて 007 から 008 に更新しました。

この記録はローカル検証の結果です。
GitHub / Woodpecker の現 head の結果、独立セキュリティ確認、3 観点レビュー、最終評価は別の証跡として扱います。
本番の reverse proxy による request body 記録、運用端末の録画、外部 OAuth、production migration / deploy は検証していません。

## 限定修正後の追加検証

初回候補 `912ade39` の記録と証拠は保持したうえで、独立レビューの CB-001、ES-803-001、ES-803-002 に限定して修正しました。

- CB-001：修正前の実 Brave で、65 astral 文字を入力すると HTML `maxlength` により 64 codepoint へ切り詰められることを確認しました。HTML の UTF-16 長制限を外し、JavaScript の `Array.from(value).length` と custom validity で API と同じ codepoint 条件を検査します。BMP / astral の 16・128 文字と astral 65 文字を保持して受理し、129 文字は切り詰めず拒否する 7 ケースが通過しました。65 astral 文字の実登録と履歴・期限切れ・閉鎖も再確認しました。
- ES-803-001：application / router / service / access logger を DEBUG で明示 capture し、各 logger の INFO・DEBUG の肯定 control を確認します。成功、validation 拒否、DB 例外で秘密値がログへ出ないことを検査します。これは既存ログ非出力 oracle の補強であり、旧実装の秘密漏えいを観測したものではありません。
- ES-803-002：通常、open 失敗、非 TTY handle、発行例外で `open("/dev/tty", "w", encoding="utf-8")` の単一呼出しを検査します。隔離した実 PTY 子プロセスでも、通常 stdout/stderr が空のまま制御端末にだけ capability が出ることを確認します。旧 CLI の出力先不具合を観測したものではありません。

初回 Red は module 未存在による collection error 2 件であり、DB の挙動ごとの Red を実施したとは主張しません。
今回の UI Red は実ブラウザの入力切詰めを示す別の記録です。
修正後の API 417 件、admin 68 件、実 DB 42 件、lint/build と新候補のブラウザ検証を実行しました。
新候補の CI と image の結果は新しい candidate に結び付け、旧結果を移し替えません。

FEX-803-001 の hash 処理キャンセル時の資源使用、FEX-803-002 の TTY 書込み失敗後に既発行 capability が残る点は、今回再設計せず follow-up に残します。
証拠の時刻は local completion、artifact creation/update、seal を分離し、追加情報の取得時刻より前に完成済みと表示しません。
