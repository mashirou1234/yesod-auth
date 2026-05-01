# Codex Automation Ops テンプレート（他repo展開用）

このドキュメントは、codex-orch 運用を他リポジトリへ展開するときの共通テンプレートです。  
README / AGENTS / CI 設定を同時に揃える前提で利用してください。

## 1. プレースホルダ置換表

| Placeholder | 説明 | 例（yesod-auth） |
| --- | --- | --- |
| `<ORCH_RUN_COMMAND>` | 自動レーン実行コマンド | 実行環境ごとの orch 実コマンド |
| `<REPO_SLUG>` | `owner/repo` 形式 | `mashirou1234/yesod-auth` |
| `<BASE_BRANCH>` | 既定マージ先ブランチ | `main` |
| `<REQUIRED_CHECKS>` | branch protection 必須チェック | `ci/woodpecker/push/woodpecker`, `auto-approve`, `enable-auto-merge` など |
| `<LABEL_SET>` | codex 系ラベルセット | `codex`, `codex-automation`, `codex:priority`, `codex:queue`, `codex:claimed`, `codex:blocked`, `codex:pr-opened` |

## 2. 標準運用ルール（テンプレ文面）

### 2.1 レーン別 commit/push

- 自動レーン: commit/push は原則許可。Issue 指示やプロンプトで明示禁止がある場合のみ停止
- 手動レーン: ローカル確認後に 1 回 push を標準化
- issue 選定: `codex:blocked` を最優先し、次に `codex:priority` + `codex:queue`、最後に通常の `codex:queue` を処理
- queue 着手前: linked Project の status / priority を確認し、Project 未連携 repo は `N/A` を記録

### 2.2 Issue 状態遷移

標準遷移は以下で固定:

`queue -> claimed -> (blocked | pr-opened) -> merge確認 -> close`

- `blocked`: issue コメントと `codex:blocked` を付与
- `pr-opened`: merge 確認後に reconcile で close（自動レーン主体）

## 3. Woodpecker docs-only CI 分岐ルール

- 対象ファイル: `docs/**`, `README.md`, `AGENTS.md`
- 変更が対象のみ: 重い検証ステップをスキップ
- 対象外が 1 つでも含まれる: 通常 CI を実行
- 判定が不確実なとき: スキップせず通常 CI を実行（fail-open）

## 4. README / AGENTS 反映ポイント

### README に必ず書くこと

- レーン別 commit/push ルール
- Issue 状態遷移（6状態）
- docs-only CI 分岐の判定対象
- merge確認と close の責務（自動レーン主体）

### AGENTS に必ず書くこと

- `<ORCH_RUN_COMMAND>` の利用
- 1 run 1 issue
- `blocked` / `pr-opened` のラベル運用
- Project 未連携時の `N/A` 記録ルール

## 5. 適用チェックリスト

- [ ] `<ORCH_RUN_COMMAND>` を実在コマンドへ置換した
- [ ] `<REPO_SLUG>`, `<BASE_BRANCH>`, `<REQUIRED_CHECKS>`, `<LABEL_SET>` を置換した
- [ ] README と AGENTS の文言が矛盾していない
- [ ] CI 定義（Woodpecker）と README の docs-only 条件が一致している
- [ ] `queue -> claimed -> (blocked | pr-opened) -> merge確認 -> close` が運用文書で一致している
- [ ] `codex:priority` を含む issue 選定順が README / AGENTS / 実行プロンプトと矛盾していない
