# GitHub OAuth

## 1. GitHub OAuth Appの作成

1. [GitHub Developer Settings](https://github.com/settings/developers){:target="_blank"}にアクセス
2. 「OAuth Apps」→「New OAuth App」をクリック
3. 必要な情報を入力：
    - Application name: アプリ名
    - Homepage URL: `http://localhost:8000`
    - Authorization callback URL: `http://localhost:8000/api/v1/auth/github/callback`
4. 「Register application」をクリック

## 2. クライアントシークレットの生成

1. 作成したアプリの設定ページを開く
2. 「Generate a new client secret」をクリック
3. Client IDとClient Secretをコピー

## 3. シークレットファイルの設定

```bash
echo "your-client-id" > secrets/github_client_id.txt
echo "your-client-secret" > secrets/github_client_secret.txt
```

!!! tip "スコープ"
    YESOD Authは`read:user`と`user:email`スコープを使用します。
    これにより、ユーザーの基本情報とメールアドレスを取得できます。

## 技術仕様

| 項目 | 値 |
|------|-----|
| 認可エンドポイント | `https://github.com/login/oauth/authorize` |
| トークンエンドポイント | `https://github.com/login/oauth/access_token` |
| ユーザー情報エンドポイント | `https://api.github.com/user` |
| スコープ | `read:user user:email` |
| PKCE | ✅ 対応 |
| OpenID Connect | ❌ 非対応 |
