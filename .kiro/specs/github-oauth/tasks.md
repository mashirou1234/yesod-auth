# 実装計画: GitHub OAuth認証プロバイダー

## 概要

GitHub OAuth 2.0認証プロバイダーを既存のOAuth基盤に追加する。既存のGoogleOAuth、DiscordOAuthクラスと同じパターンで実装し、PKCEをサポートする。

## タスク

- [x] 1. 設定の追加
  - [x] 1.1 `api/app/config.py` にGitHub OAuth設定を追加
    - `GITHUB_CLIENT_ID` と `GITHUB_CLIENT_SECRET` を `read_secret()` で読み込む
    - _Requirements: 5.1, 5.2_

- [x] 2. GitHubOAuthクラスの実装
  - [x] 2.1 `api/app/auth/oauth.py` に `GitHubOAuth` クラスを追加
    - `AUTHORIZE_URL`, `TOKEN_URL`, `USERINFO_URL`, `EMAILS_URL` 定数を定義
    - `get_authorize_url()` メソッドを実装（PKCE対応）
    - `exchange_code()` メソッドを実装（PKCE対応）
    - `get_user_info()` メソッドを実装
    - `_get_primary_email()` プライベートメソッドを実装
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.3, 2.4, 3.1, 3.2, 3.3, 4.1, 4.2_
  
  - [ ] 2.2 GitHubOAuthクラスのプロパティテストを作成
    - **Property 1: 認可URL生成の完全性**
    - **Validates: Requirements 1.2, 1.3, 1.4**

- [x] 3. 認証ルーターの拡張
  - [x] 3.1 `api/app/auth/router.py` にGitHubエンドポイントを追加
    - `GET /auth/github` - OAuth認証フロー開始
    - `GET /auth/github/callback` - コールバック処理
    - 既存の `_find_or_create_user()` を使用
    - 監査ログとWebhook発行を含める
    - _Requirements: 1.1, 1.5, 2.1, 2.2, 2.5, 3.4, 4.3, 4.4, 4.5, 7.1, 7.2, 7.3, 7.4_
  
  - [ ] 3.2 無効なstateのプロパティテストを作成
    - **Property 2: 無効なstateの拒否**
    - **Validates: Requirements 2.2**

- [x] 4. チェックポイント - コア機能の確認
  - すべてのテストが通ることを確認し、質問があればユーザーに確認する

- [x] 5. Mock OAuthの拡張
  - [x] 5.1 `api/app/auth/mock_oauth.py` に `to_github_format()` メソッドを追加
    - `MockOAuthUser` クラスに `to_github_format()` を追加
    - GitHub APIフォーマット（id, login, name, email, avatar_url）を返す
    - _Requirements: 6.2, 6.3_
  
  - [x] 5.2 `api/app/auth/router.py` のモックログインにGitHubプロバイダーを追加
    - `mock_login` エンドポイントで `provider="github"` をサポート
    - _Requirements: 6.1_
  
  - [ ] 5.3 MockOAuthUserのプロパティテストを作成
    - **Property 5: MockOAuthUserのGitHubフォーマット**
    - **Validates: Requirements 6.3**

- [x] 6. ユニットテストの作成
  - [x] 6.1 GitHubOAuthクラスのユニットテストを作成
    - 認可URL生成のテスト
    - トークン交換のテスト（httpxモック使用）
    - ユーザー情報取得のテスト（httpxモック使用）
    - プライベートメール取得のテスト
    - _Requirements: 2.3, 2.5, 3.1, 3.3, 3.4_
  
  - [x] 6.2 GitHubコールバックエンドポイントのユニットテストを作成
    - 成功ケースのテスト
    - 無効なstateのテスト
    - トークン交換失敗のテスト
    - _Requirements: 2.1, 2.2, 2.5, 7.2_

- [x] 7. 最終チェックポイント - すべてのテストが通ることを確認
  - すべてのテストが通ることを確認し、質問があればユーザーに確認する

- [x] 8. ドキュメントの更新
  - [x] 8.1 `docs/guides/oauth.md` にGitHub OAuth設定ガイドを追加
    - GitHub OAuth Appの作成手順
    - 環境変数の設定方法
    - _Requirements: 5.1, 5.2_
  
  - [x] 8.2 `docs/api/auth.md` にGitHubエンドポイントを追加
    - `/auth/github` エンドポイントの説明
    - `/auth/github/callback` エンドポイントの説明
    - _Requirements: 1.1, 2.1_
  
  - [x] 8.3 `docs/installation.md` に環境変数を追加
    - `GITHUB_CLIENT_ID` と `GITHUB_CLIENT_SECRET` の説明
    - _Requirements: 5.1, 5.2_

## 備考

- 各タスクは特定の要件にトレースバック可能
- チェックポイントで段階的に検証を行う
- プロパティテストは普遍的な正確性を検証
- ユニットテストは特定の例とエッジケースを検証

## CI/CD (GitHub Actions) 注意事項

### テスト環境の制約

1. **テストDBはインメモリSQLite**
   - PostgreSQL固有機能（スキーマ、パーティション等）はテストでスキップ必須
   - `TESTING=1` 環境変数で判定

2. **監査ログのスキップ**
   - SQLiteは`audit`スキーマをサポートしない
   - `_is_testing()` でスキップ処理を実装済み（`api/app/audit/service.py`参照）
   - 新しいコードで監査ログを呼び出す場合、テスト環境での動作を確認

3. **Valkey/Redis操作**
   - `conftest.py` でモック済み
   - `OAuthStateStore` の操作はモックされる

4. **外部API（GitHub）のモック**
   - `httpx` を使用した外部API呼び出しはモックが必要
   - `pytest-httpx` または `respx` を使用

### テスト実装パターン

```python
import os

def _is_testing() -> bool:
    """Check if running in test environment."""
    return os.environ.get("TESTING") == "1"

# 監査ログを含むコードでの使用例
async def some_operation(db: AsyncSession):
    # 処理...
    
    # 監査ログはテスト環境でスキップ
    if not _is_testing():
        await AuditLogger.log_event(...)
```

### CI実行時の確認事項

- `ruff check api/` でリントエラーがないこと
- `ruff format api/ --check` でフォーマットが正しいこと
- `pytest api/tests/` で全テストがパスすること
