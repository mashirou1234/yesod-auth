# 設計ドキュメント: X (Twitter) OAuth 2.0

## 概要

X OAuth 2.0認証プロバイダーをYESOD Authに追加する。PKCEをサポートする。

## X OAuth 2.0の特徴

- PKCEが必須
- Basic認証でクライアント認証
- メールアドレスは取得不可（Elevated accessが必要）
- ユーザー名ベースの仮メールを生成

## コンポーネント

### XOAuthクラス

```python
class XOAuth:
    """X (Twitter) OAuth 2.0 implementation with PKCE."""

    AUTHORIZE_URL = "https://twitter.com/i/oauth2/authorize"
    TOKEN_URL = "https://api.twitter.com/2/oauth2/token"
    USERINFO_URL = "https://api.twitter.com/2/users/me"

    @classmethod
    def get_authorize_url(
        cls,
        redirect_uri: str,
        state: str,
        code_challenge: str,
    ) -> str:
        """Get the X OAuth authorization URL with PKCE (required)."""
        ...

    @classmethod
    async def exchange_code(
        cls,
        code: str,
        redirect_uri: str,
        code_verifier: str,
    ) -> dict | None:
        """Exchange authorization code for tokens using Basic auth."""
        ...

    @classmethod
    async def get_user_info(cls, access_token: str) -> dict | None:
        """Get user info from X."""
        ...
```

### 設定

```python
# config.py
X_CLIENT_ID: str = read_secret("x_client_id", "")
X_CLIENT_SECRET: str = read_secret("x_client_secret", "")
```

### エンドポイント

| エンドポイント | メソッド | 説明 |
|---------------|---------|------|
| `/auth/x` | GET | X OAuth認証フロー開始 |
| `/auth/x/callback` | GET | Xからのコールバック処理 |

### X APIレスポンス形式

**ユーザー情報 (`/2/users/me`)**:
```json
{
    "data": {
        "id": "12345678",
        "username": "example_user",
        "name": "Example User",
        "profile_image_url": "https://pbs.twimg.com/..."
    }
}
```

### メールアドレスの扱い

Xはメールアドレスを返さないため、以下の形式で仮メールを生成：
```
{username}@x.yesod-auth.local
```

### Mock OAuth

```python
def to_x_format(self) -> dict:
    """Convert to X userinfo format."""
    return {
        "data": {
            "id": self.id,
            "username": self.name.lower().replace(" ", "_"),
            "name": self.name,
            "profile_image_url": self.picture,
        }
    }
```
