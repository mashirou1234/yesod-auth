# Discord OAuth

## 1. Discord Developer Portalでアプリ作成

1. [Discord Developer Portal](https://discord.com/developers/applications){:target="_blank"}にアクセス
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
| PKCE | ✅ 独自実装 |
| OpenID Connect | ❌ 非対応 |

## scope不足時の症状

Discord OAuth では `scope=identify email` が前提です。`email` が不足すると、次の症状が発生します。

| 症状 | 典型ログ/レスポンス | 主な原因 |
|------|----------------------|----------|
| コールバック失敗 | `400 Failed to get user info` | トークン交換後のユーザー情報取得で必要情報が不足 |
| サーバーエラー | `KeyError: 'email'` | `/users/@me` 応答に `email` が含まれない |

### 確認ポイント

1. 認可URLの `scope` に `identify email` が含まれるか確認する
2. Discord Developer Portal の OAuth2 設定で対象アプリを確認する
3. APIログで `Failed to get user info` や `KeyError: 'email'` を確認する

```bash
docker compose logs --tail=100 api | rg -n "discord|Failed to get user info|KeyError: 'email'|scope"
```

### 対処

- アプリ側の認可URLで `scope=identify email` を維持する
- 認証を最初からやり直して再同意を取得する

!!! info "PKCE対応について"
    DiscordはPKCEパラメータを受け入れますが、公式ドキュメントには記載されていません。
    YESOD Authはセキュリティ強化のため、独自にPKCE（S256）を実装しています。
