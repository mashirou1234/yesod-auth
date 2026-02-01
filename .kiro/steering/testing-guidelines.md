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

## GitHub Actions CI/CD 注意事項

### CI環境の特徴
- テストDBはインメモリSQLite（PostgreSQL固有機能は使用不可）
- `TESTING=1` が設定済み
- Valkey/Redisはモック済み

### 外部APIのモック

外部API（OAuth プロバイダー等）を呼び出すコードは必ずモックが必要:

```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_oauth_exchange_code():
    """外部APIはhttpxをモックしてテスト"""
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"access_token": "test_token"}
    
    with patch("httpx.AsyncClient.post", return_value=mock_response):
        result = await SomeOAuth.exchange_code("code", "redirect_uri")
        assert result["access_token"] == "test_token"
```

### OAuthStateStore のモック

`conftest.py` で `OAuthStateStore` はモック済み。テストでは直接使用可能:

```python
async def test_oauth_callback(client, db_session):
    # OAuthStateStoreは自動的にモックされる
    response = await client.get("/auth/provider/callback?code=xxx&state=yyy")
```

### CI実行前の確認事項

1. **リント**: `ruff check api/`
2. **フォーマット**: `ruff format api/ --check`
3. **テスト**: `pytest api/tests/ -v`

### よくあるCIエラーと対処法

| エラー | 原因 | 対処法 |
|--------|------|--------|
| `no such table: audit.*` | 監査ログテーブルへのアクセス | `_is_testing()` でスキップ |
| `UNIQUE constraint failed` | テストデータの重複 | `db_session` フィクスチャを使用（自動ロールバック） |
| `httpx.ConnectError` | 外部APIへの実際の接続 | httpxをモック |
| `valkey.exceptions.*` | Valkeyへの実際の接続 | `conftest.py` のモックを確認 |
