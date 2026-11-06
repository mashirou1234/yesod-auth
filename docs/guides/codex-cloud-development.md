# Codexクラウドでの継続開発

## 最短セットアップ（Docker・OAuth認証情報不要）

リポジトリ直下で実行します。Python 3.11以上とvenv、初回導入時のPyPIへのHTTPS接続が必要です。
クラウドではPython 3.12で検証しています。アプリのDockerfileは3.11です。

```bash
bash scripts/cloud-setup.sh
bash scripts/cloud-test.sh
.venv/bin/ruff check api/
.venv/bin/ruff format --check api/
```

Pythonを指定する場合は `PYTHON_BIN=python3.12 bash scripts/cloud-setup.sh` を使います。
セットアップは `.venv/` に既存の `api/requirements.txt` とRuffを導入し、`pip check` を実行します。
依存は既存方針どおり下限指定であり、ロックされていません。将来の解決結果が変わった場合は、
まず `pip freeze` と変更前コミットの結果を比較してください。一括更新は不要です。

```bash
# 対象を絞る例（引数はpytestにそのまま渡る）
bash scripts/cloud-test.sh tests/test_mock_oauth.py -q
mkdir -p artifacts
.venv/bin/python -m pip freeze > artifacts/cloud-python312-freeze.txt
bash scripts/cloud-test.sh > artifacts/cloud-pytest.log 2>&1
```

`cloud-test.sh` はテスト用JWT、SQLite URL、ローカルValkey URLを設定し、
シェルから継承する8プロバイダーのClient ID/Secretを空にします。
既存のconftestはSQLiteインメモリDBとValkeyモックを使います。
OAuthのHTTP応答も既存テストのモックで検証するため、本物のOAuthアプリは不要です。
`/run/secrets/` は環境変数より優先されるので、本番シークレットをマウントした環境では実行せず、
専用の開発環境を使ってください。`artifacts/` と `.venv/` はコミットしません。

## 環境の確認とネットワーク

README、AGENTS.md、`artifacts/`（存在すれば前回結果）、CIを最初に確認してください。
この手順はPower Userの直接依頼に対応する手動レーンです。キューのIssueやラベルは変更しません。

```bash
python3 --version
docker compose version
env -u DOCKER_HOST -u DOCKER_CONTEXT -u DOCKER_TLS \
  -u DOCKER_TLS_VERIFY -u DOCKER_CERT_PATH \
  docker --host=unix:///var/run/docker.sock info
```

クラウドのネットワーク許可を伴わないサンドボックス実行では、clone時のプロキシ接続や
Dockerソケット接続に失敗する場合があります。今回の環境では、ネットワーク権限を付与した
コマンド実行で両方成功しました。プロキシを解除したりTLS検証を無効にしたりせず、
環境のネットワークポリシー・実行権限を確認してください。
Dockerが使えなくても上記のSQLiteテストは実行できます。
Docker buildで証明書が必要な環境では、環境提供のCAをBuildKit secretで渡します。
今回、アプリのDockerイメージのビルドは検証していません。

## PostgreSQLマイグレーションの追加確認（任意）

新規の使い捨てチェックアウト・DBでのみ実行してください。
Composeの `valkey` は固定コンテナ名と永続ボリュームを使うため、既存環境との共用は避けます。
テスト用DBは5433、Valkeyは6379を使用します。APIコンテナやOAuthシークレットは不要です。

```bash
docker compose --profile ci up -d --wait db-ci valkey
(
  cd api
  TESTING=1 MOCK_OAUTH_ENABLED=1 \
    JWT_SECRET=cloud-tests-only-not-for-production \
    DATABASE_URL=postgresql+asyncpg://yesod_user:yesod_password@127.0.0.1:5433/yesod \
    ../.venv/bin/python -m alembic upgrade head
)
docker compose --profile ci exec -T valkey valkey-cli ping
# 今回作ったサービスのみ停止・削除（既存データのボリューム削除は行わない）
docker compose --profile ci stop db-ci valkey
docker compose --profile ci rm -f db-ci valkey
```

SQLiteのテスト成功はPostgreSQLのスキーマ・pg_cron・本番動作の保証ではありません。
CIプロファイルのDBは `postgres:16-alpine`、通常プロファイルはpg_cron入りの `db/Dockerfile` を使います。
通常プロファイル、管理画面、外部Webhook配送、実OAuthプロバイダーへのログインは別の検証です。
実OAuthには開発専用アプリ、正しいcallback URL、ブラウザーでの同意操作が必要です。
本番の認証情報やデプロイはこの手順では使用しません。

## CIと今回の確認結果

追加した `.github/workflows/cloud-tests.yml` はPRと手動起動で、Python 3.12上の
セットアップ・Ruff・SQLite/モックテストを実行します。PRをドラフトにしてレビューし、
既存の自動マージを有効にする操作は行いません。

既存CIの注意点:

- `.github/workflows/ci.yml` は手動起動のみ。Dockerテスト用secret生成にTwitchの2ファイルがなく、
  `api-ci` が参照する全secretと一致していません。この経路は今回変更・実行していません。
- `.woodpecker.yml` はRust向けで、Cargo.tomlがないこのPythonリポジトリではスキップする設定です。
  Pythonテストを保証しません。既存の必須チェックや外部CIの運用変更は別途検討してください。
- 新しいCloud testsを必須チェックにするにはリポジトリ管理側の設定が必要です。今回設定は変更しません。

2026-11-06、ベース `e3a896f83875aee27fb9fd4152933de24dbdd711` での結果:

| 検証 | 変更前 | 変更後 |
|---|---|---|
| Python 3.12既存テスト | 326 passed | cloud-test.shで326 passed |
| Ruff lint / format | 成功 / 88ファイル整形済み | 成功 |
| pip check | 成功 | 成功 |
| Compose CI設定の構文 | 成功 | 構成変更なし |
| PostgreSQL 16 / Valkey | 未起動 | healthy / healthy |
| 空DBへのAlembic upgrade head | 未実行 | 001〜006成功 |

変更前のアプリテスト失敗はありません。初回のclone・Dockerソケットエラーは
サンドボックス実行権限によるもので、権限付き実行で解消しました。
GitHub Actions上の新規ワークフローの実行結果はPRのチェックで別途確認してください。
