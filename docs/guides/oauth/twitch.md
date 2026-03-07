# Twitch OAuth

## 1. Twitch Developer Consoleでアプリ作成

1. [Twitch Developer Console](https://dev.twitch.tv/console/apps){:target="_blank"}にアクセス
2. 「Register Your Application」をクリック
3. 必要な情報を入力：
    - Name: アプリ名
    - OAuth Redirect URLs: `http://localhost:8000/api/v1/auth/twitch/callback`
    - Category: 適切なカテゴリを選択
4. 「Create」をクリック

## 2. クライアント認証情報の取得

1. 作成したアプリの「Manage」をクリック
2. 「Client ID」をコピー
3. 「New Secret」をクリックしてClient Secretを生成・コピー

## 3. シークレットファイルの設定

```bash
echo "your-client-id" > secrets/twitch_client_id.txt
echo "your-client-secret" > secrets/twitch_client_secret.txt
```

## 4. 追加設定の最小手順（セルフホスト向け）

1. **Callback URLを実運用値へ更新**
    - ローカル: `http://localhost:8000/api/v1/auth/twitch/callback`
    - 本番: `https://<your-domain>/api/v1/auth/twitch/callback`
2. **スコープを固定**
    - YESOD Auth の既定は `openid user:read:email`
    - Twitch側の設定変更時も、この2つを維持する
3. **APIコンテナへ secrets を渡す**
    - `docker-compose.override.yml` で `twitch_client_id` / `twitch_client_secret` を `api` と `api-ci` に追加する
4. **実OAuthモードを有効化**
    - `MOCK_OAUTH_ENABLED=0`（または未設定）を確認する

### docker-compose.override.yml の最小例

```yaml
services:
  api:
    secrets:
      - twitch_client_id
      - twitch_client_secret
  api-ci:
    secrets:
      - twitch_client_id
      - twitch_client_secret

secrets:
  twitch_client_id:
    file: ./secrets/twitch_client_id.txt
  twitch_client_secret:
    file: ./secrets/twitch_client_secret.txt
```

### 最小確認手順

```bash
# 1) API起動確認
curl -fsS http://localhost:8000/health

# 2) Twitch OAuth導線確認（302想定）
curl -fsS -o /dev/null -w '%{http_code}\n' \
  "http://localhost:8000/api/v1/auth/twitch"
```

!!! info "Helix API"
    YESOD Authは[Twitch Helix API](https://dev.twitch.tv/docs/api/){:target="_blank"}を使用します。
    `openid`と`user:read:email`スコープを要求し、
    ユーザー情報は`/helix/users`エンドポイントから取得します。

## 技術仕様

| 項目 | 値 |
|------|-----|
| 認可エンドポイント | `https://id.twitch.tv/oauth2/authorize` |
| トークンエンドポイント | `https://id.twitch.tv/oauth2/token` |
| ユーザー情報エンドポイント | `https://api.twitch.tv/helix/users` |
| スコープ | `openid user:read:email` |
| PKCE | ✅ 独自実装 |
| OpenID Connect | ❌ 非対応 |

!!! info "PKCE対応について"
    TwitchはPKCEを公式にはサポートしていません。
    YESOD Authはセキュリティ強化のため、独自にPKCE（S256）パラメータを送信しています。
    プロバイダー側でパラメータが無視される場合でも、セキュリティ上の問題はありません。
