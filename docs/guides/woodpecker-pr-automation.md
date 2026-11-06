# WoodpeckerでPR自動承認・マージを運用する

テスト・lintとPR自動化を `.woodpecker.yml` に統一しています。
GitHub Actionsのランナーは使用しません。PR自動化はGitHub APIを呼ぶ処理です。

## 動作

1. PRでは `python-checks` がテスト・lintを実行します。bot用トークンは渡しません。
2. 保護されたmainの `pr-maintenance` cronが、main/master向けのopen PRを確認します。
3. ドラフトとbot自身が作成したPRを除外します。forkのPRも検査対象ですが、そのコードをcronで実行しません。
4. 現在のhead SHAで `ci/woodpecker/pr/woodpecker` が成功し、他のstatus/check-runも完了している場合に承認します。
5. 承認をhead SHAに紐付け、SHA・ドラフト状態・チェックを再確認します。
   GitHubが `mergeable=true`, `mergeable_state=clean` を返した場合だけsquashマージします。
   マージAPIにも検証したSHAを指定するため、途中でpushされた別コミットはマージしません。

同じコミットのbot承認は重複投稿しません。競合や未完了チェック、GitHub側の状態計算待ちは
次回cronで再確認します。権限エラーは成功として扱いません。
GitHubのauto-mergeキューに登録する方式ではなく、定期実行による承認・マージです。
ready-for-review直後の即時実行ではなく、次回cronまでの待ち時間があります。

レビュー前の変更はドラフトを維持してください。通常のPRにすると、条件を満たした時点で自動処理されます。
人によるコードレビューの代わりになる品質判定ではなく、既存の自動承認運用を移したものです。

## 初回設定（管理者が一度実施）

### 1. GitHubのbot権限とブランチ保護

- PR作成者とは別のbotユーザーを用意し、このリポジトリにWrite権限を与えます。
- botユーザーのfine-grained PATをこのリポジトリだけに限定し、ContentsとPull requestsをRead/write、
  Commit statusesとChecksをReadにします。MetadataはReadです。期限と更新担当者を設定してください。
- この実装は `/user` でbotの識別を行うため、botユーザーのPATを使います。GitHub App installation tokenは未対応です。
- botを管理者やブランチ保護・rulesetのbypass対象にしないでください。保護の設定は管理者が行います。
- main/masterの必須チェックを実際のPRチェック `ci/woodpecker/pr/woodpecker` に合わせます。
  旧 `auto-approve` / `enable-auto-merge` と、PRで発生しないpush用チェックを必須に残すとマージできません。
  その他のレビュー・チェック要件は維持します。今回、この管理設定は変更していません。
- squash mergeを許可します。GitHubのAllow auto-merge設定はこの方式では不要です。

### 2. Woodpeckerのrepository secret

リポジトリ `mashirou1234/yesod-auth` のSecretsに次を登録します。

| 設定 | 値 |
|---|---|
| Name | `pr_automation_token` |
| Value | 上で作成したbotユーザーのPAT |
| Events | **cronだけ** |

`pull_request`, `push`, `manual`, `deployment`, `tag` など他のイベントを許可しないでください。
YAMLのwhen条件だけでは、PRがYAMLを改変した場合のsecret保護になりません。
イベント制限はWoodpeckerのsecret設定側で行う必要があります。
このステップは通常のPythonコマンドで動くため、plugin専用のimage制限は付けません。

値をチャット・ログ・Gitに記録しないでください。CLIを使う場合はローカルの保護されたファイルから登録できます。
以下はWoodpecker CLI v3.20.1の構文です。`WOODPECKER_SERVER` / `WOODPECKER_TOKEN` には
Woodpeckerへの管理接続を事前に設定します（GitHub botのPATとは別です）。

```bash
woodpecker-cli repo secret add \
  --repository mashirou1234/yesod-auth \
  --name pr_automation_token \
  --event cron \
  --value @/secure/path/github-bot-token.txt
```

### 3. cronの作成

設定をmainへ取り込んだ後、WoodpeckerのRepository settings → Cronに登録します。

| 設定 | 値 |
|---|---|
| Name | `pr-maintenance` |
| Branch | `main` |
| Schedule | `@every 5m` |
| Enabled | true |

```bash
woodpecker-cli repo cron add \
  --repository mashirou1234/yesod-auth \
  --name pr-maintenance --branch main --schedule '@every 5m' --enabled
```

cronのrefをPRブランチへ向けないでください。cronやsecretを編集できるWoodpeckerユーザーは
信頼できるリポジトリ管理者に限定します。cronはmerge済みのmainのスクリプトだけを実行します。
既存の承認トークンをPR環境へ渡す設定や、GitHubトークン付きの共通runner設定は併用しません。

今回のドラフトPRは自動マージ対象外です。初回のmainへの取り込みは通常のレビューで行います。
cronを作る前に、既存の非ドラフトPRも対象になることを確認してください。

## 検証と切り分け

```bash
# ローカルのモックテスト。承認・マージは一切送信しない
python3 -m unittest discover -s scripts/tests -v

# 公開PRを読み取り専用で確認（デフォルトはdry-run）
python3 scripts/woodpecker_pr_automation.py --pull-request 838

# Woodpecker CLIを導入済みの場合
woodpecker-cli lint --strict .woodpecker.yml
```

`--apply` はmain/master・対象リポジトリ・cronイベント・botトークンが揃う場合だけ実行できます。
ローカルで環境変数を偽装して有効化せず、初回はcronのログとGitHub側のreview/merge履歴を確認してください。

| 状況 | 確認先 |
|---|---|
| cronが起動しない | Woodpecker管理画面のcron登録・有効化・main参照 |
| secret未設定エラー | `pr_automation_token` の名前とcronイベント許可 |
| HTTP 401/403 | bot PATの期限・対象repo・権限。GitHub App tokenは使わない |
| checks待ち | 最新SHAのPR用Woodpecker statusとcheck-runs |
| requirements待ち | GitHubのブランチ保護、旧必須チェック、レビュー、競合 |
| bot作成PRをスキップ | 自己承認は不可。別のレビュー担当者で処理する |

停止するにはWoodpeckerの `pr-maintenance` cronを無効にします。PRテストは継続します。
トークンが不要になったらsecretとGitHub側のPATを削除・失効します。

## この変更での検証範囲

PR操作はモックで検証します。ドラフト・失敗/未完了チェック・SHA変更・競合・権限エラーで
マージしないこと、成功時に検証済みSHAで承認/マージすること、ページネーション、承認の重複防止を含みます。
2026-11-06時点で、モックテスト18件（ホストおよび `python:3.12-slim`）、既存APIテスト326件、
Ruff lint/format、Woodpecker CLI v3.20.1のstrict lintが成功しています。
公開PR #838の実APIへのdry-runは、ドラフトのため操作せず終了することを確認しました。
実際の承認・マージ、bot secret登録、cron登録、ブランチ保護変更は未実施です。
現在の接続ではWoodpecker管理APIが認証を要求し、GitHubブランチ保護APIは403になるため、
管理者による上記の初回設定が必要です。
