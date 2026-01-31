---
inclusion: fileMatch
fileMatchPattern: "**/tests/**/*.py,**/test_*.py,**/*_test.py"
---

# テストファイル作成ガイドライン

このガイドラインは、テストファイルを作成・編集する際に適用されます。

## 必須チェックリスト

### 1. PostgreSQL固有機能の確認
テスト対象コードが以下を使用している場合、テスト時スキップが必要:

- [ ] `audit`スキーマ（監査ログ）
- [ ] パーティションテーブル
- [ ] `pg_cron`ジョブ
- [ ] PostgreSQL固有の型（`JSONB`の特殊操作等）

### 2. スキップ実装パターン
```python
import os

def _is_testing() -> bool:
    return os.environ.get("TESTING") == "1"

# 関数の先頭でチェック
async def function_with_pg_dependency(db: AsyncSession):
    if _is_testing():
        return  # または適切なモック値を返す
```

### 3. conftest.pyの活用
- `db_session`: インメモリSQLiteセッション
- `client`: HTTPテストクライアント（Valkey/DBモック済み）
- `mock_oauth_user`: OAuthユーザーデータ

## テストDB制約

### SQLiteで使用不可
- スキーマ（`CREATE SCHEMA`）
- パーティション（`PARTITION BY`）
- `pg_cron`
- 一部のPostgreSQL関数

### 回避策
1. 該当機能を使うコードは`_is_testing()`でスキップ
2. ビジネスロジックとDB操作を分離してテスト
3. 統合テストは別途CI環境で実行

## 例: 監査ログのテスト

```python
# 監査ログ自体のテストは不要（CI環境でスキップされる）
# ビジネスロジックのテストに集中する

async def test_login_success(client, db_session):
    # 監査ログは自動的にスキップされる
    response = await client.post("/auth/login", ...)
    assert response.status_code == 200
```
