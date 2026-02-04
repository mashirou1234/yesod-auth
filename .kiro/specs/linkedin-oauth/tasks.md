# 実装計画: LinkedIn OAuth 2.0

## タスク

- [x] 1. 設定の追加
  - [x] 1.1 `api/app/config.py` にLinkedIn OAuth設定を追加

- [x] 2. LinkedInOAuthクラスの実装
  - [x] 2.1 `api/app/auth/oauth.py` に `LinkedInOAuth` クラスを追加

- [x] 3. 認証ルーターの拡張
  - [x] 3.1 `api/app/auth/router.py` にLinkedInエンドポイントを追加

- [x] 4. Mock OAuthの拡張
  - [x] 4.1 `api/app/auth/mock_oauth.py` に `to_linkedin_format()` メソッドを追加
  - [x] 4.2 `api/app/auth/router.py` のモックログインにLinkedInプロバイダーを追加

- [x] 5. ユニットテストの作成
  - [x] 5.1 `api/tests/test_linkedin_oauth.py` を作成

- [x] 6. ドキュメントの更新
  - [x] 6.1 `docs/guides/oauth.md` にLinkedIn OAuth設定ガイドを追加
  - [x] 6.2 `docs/api/auth.md` にLinkedInエンドポイントを追加
  - [x] 6.3 `docs/installation.md` に環境変数を追加
  - [x] 6.4 `docs/index.md` の対応プロバイダーを更新

- [x] 7. ruffフォーマット適用
