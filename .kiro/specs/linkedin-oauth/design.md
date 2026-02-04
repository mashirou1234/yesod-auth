# 設計: LinkedIn OAuth 2.0認証プロバイダー

## アーキテクチャ

### 認証フロー
```
1. ユーザー → GET /auth/linkedin
2. API → LinkedIn Authorization URL にリダイレクト（PKCE付き）
3. ユーザー → LinkedInでログイン・認可
4. LinkedIn → GET /auth/linkedin/callback?code=xxx&state=xxx
5. API → LinkedInトークンエンドポイントでcode交換
6. API → LinkedIn UserInfo APIでユーザー情報取得
7. API → ユーザー作成/更新、JWTトークン発行
8. API → フロントエンドにリダイレクト
```

## コンポーネント設計

### 1. LinkedInOAuthクラス (`api/app/auth/oauth.py`)
```python
class LinkedInOAuth:
    AUTHORIZE_URL = "https://www.linkedin.com/oauth/v2/authorization"
    TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
    USERINFO_URL = "https://api.linkedin.com/v2/userinfo"
    
    @classmethod
    def get_authorize_url(cls, redirect_uri, state, code_challenge) -> str
    
    @classmethod
    async def exchange_code(cls, code, redirect_uri, code_verifier) -> dict | None
    
    @classmethod
    async def get_user_info(cls, access_token) -> dict | None
```

### 2. 設定 (`api/app/config.py`)
```python
LINKEDIN_CLIENT_ID: str
LINKEDIN_CLIENT_SECRET: str
```

### 3. エンドポイント (`api/app/auth/router.py`)
- `GET /auth/linkedin` - 認証開始
- `GET /auth/linkedin/callback` - コールバック処理

### 4. MockOAuth (`api/app/auth/mock_oauth.py`)
```python
def to_linkedin_format(self) -> dict:
    # OpenID Connect形式のレスポンス
    return {
        "sub": self.id,
        "name": self.name,
        "email": self.email,
        "picture": self.picture,
    }
```

## LinkedIn API仕様

### Authorization Request
```
GET https://www.linkedin.com/oauth/v2/authorization
?client_id={client_id}
&redirect_uri={redirect_uri}
&response_type=code
&scope=openid%20profile%20email
&state={state}
&code_challenge={code_challenge}
&code_challenge_method=S256
```

### Token Exchange
```
POST https://www.linkedin.com/oauth/v2/accessToken
Content-Type: application/x-www-form-urlencoded

grant_type=authorization_code
&code={code}
&redirect_uri={redirect_uri}
&client_id={client_id}
&client_secret={client_secret}
&code_verifier={code_verifier}
```

### UserInfo Response (OpenID Connect)
```json
{
  "sub": "abc123",
  "name": "John Doe",
  "given_name": "John",
  "family_name": "Doe",
  "picture": "https://media.licdn.com/...",
  "email": "john@example.com",
  "email_verified": true
}
```

## テスト計画
- 認証URL生成テスト（PKCE含む）
- コード交換テスト（成功/失敗）
- ユーザー情報取得テスト
- MockOAuth LinkedIn形式テスト
- モックログインテスト
