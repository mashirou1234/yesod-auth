# Yesod Auth プロジェクト規約

このドキュメントは、プロジェクト全体で一貫性を保つための開発規約を定義します。

## 環境構成

### Docker Compose Profiles
| Profile | 用途 | 起動サービス |
|---------|------|-------------|
| `default` | ローカル開発 | db, valkey, api, docs |
| `full` | 管理画面含む | db, valkey, api, admin, docs |
| `ci` | CI/CD用軽量構成 | db-ci, valkey, api-ci |

### 環境変数
| 変数名 | 説明 |
|--------|------|
| `TESTING=1` | テスト環境フラグ。監査ログなどDB依存処理をスキップ |
| `MOCK_OAUTH_ENABLED=1` | モックOAuth有効化。開発/テスト時にOAuthをスキップ |

## テスト作成ガイドライン

### pytest設定
- テストDBはインメモリSQLite (`sqlite+aiosqlite:///:memory:`)
- PostgreSQL固有機能（スキーマ、パーティション等）はテストでスキップ必須
- `conftest.py`で`TESTING=1`を設定済み

### テスト時にスキップが必要な機能
1. **監査ログ** (`audit.login_history`, `audit.auth_events`)
   - SQLiteは`audit`スキーマをサポートしない
   - `_is_testing()`でスキップ: `api/app/audit/service.py`参照

2. **Valkey/Redis操作**
   - `conftest.py`でモック済み

### スキップパターン実装例
```python
import os

def _is_testing() -> bool:
    """Check if running in test environment."""
    return os.environ.get("TESTING") == "1"

async def some_db_operation(db: AsyncSession):
    if _is_testing():
        return  # Skip in test environment
    # PostgreSQL固有の処理
```

## Alembicマイグレーション

### PostgreSQL拡張機能の扱い
CI環境では`pg_cron`等の拡張がないため、条件付きで実行する:

```python
# ❌ NG: 直接呼び出し
op.execute("SELECT cron.schedule(...)")

# ✅ OK: 拡張の存在確認後に実行
op.execute("""
    DO $$
    BEGIN
        IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron') THEN
            PERFORM cron.schedule(...);
        END IF;
    END $$;
""")
```

### パーティションテーブル
- 本番: PostgreSQLのパーティション機能を使用
- テスト: SQLiteはパーティション非対応のため、テストコードからは直接アクセスしない

## CI/CD (GitHub Actions)

### ワークフロー構成
1. **lint** - ruffでコード品質チェック
2. **test** - pytestでユニットテスト
3. **generate-types** - OpenAPIからTypeScript型生成

### CI用サービス
- `db-ci`: 軽量PostgreSQL（pg_cron等の拡張なし）、ポート5433
- `api-ci`: テスト用APIコンテナ、ポート8001

### CIテスト実行ルール（必須）

**CIテスト実行後は必ずコンテナを停止すること。**

```bash
# テスト実行
docker compose --profile ci build api-ci
docker compose --profile ci run --rm api-ci pytest

# テスト完了後、必ず実行
docker compose --profile ci down
```

CI環境は開発環境と異なるポートを使用するため同時起動可能だが、テスト完了後は必ず停止してリソースを解放すること。

## コード品質

### Ruff設定
- 設定ファイル: `api/pyproject.toml`
- リント: `ruff check api/`
- フォーマット: `ruff format api/`

### 実装ルール（必須）

Pythonコードを作成・編集する際は、以下を必ず実行すること：

1. **コミット前にruffフォーマットを適用**
   ```bash
   python3 -m ruff format api/
   ```

2. **リントエラーがないことを確認**
   ```bash
   python3 -m ruff check api/
   ```

3. **import文の順序**
   - 標準ライブラリ → サードパーティ → ローカルの順
   - ruffが自動で整理するため、`ruff format`を実行すれば解決

CIでは`ruff check`と`ruff format --check`が実行され、違反があるとビルドが失敗する。
