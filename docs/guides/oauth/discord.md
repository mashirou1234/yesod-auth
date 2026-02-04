# Discord OAuth

## 1. Discord Developer Portalでアプリ作成

1. [Discord Developer Portal](https://discord.com/developers/applications)にアクセス
2. 「New Application」をクリック
3. アプリ名を入力して作成

## 2. OAuth2設定

1. 左メニューの「OAuth2」を選択
2. 「Redirects」に以下を追加：
    ```
    http://localhost:8000/api/v1/auth/discord/callback
    ```
3. 「Client ID」と「Client Secret」をコピー

## 3. シークレットファイルの設定

```bash
echo "your-client-id" > secrets/discord_client_id.txt
echo "your-client-secret" > secrets/discord_client_secret.txt
```

## 技術仕様

| 項目 | 値 |
|------|-----|
| 認可エンドポイント | `https://discord.com/api/oauth2/authorize` |
| トークンエンドポイント | `https://discord.com/api/oauth2/token` |
| ユーザー情報エンドポイント | `https://discord.com/api/users/@me` |
| スコープ | `identify email` |
| PKCE | ❌ 非対応 |
| OpenID Connect | ❌ 非対応 |
