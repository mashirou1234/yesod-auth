# Slack OAuth

## 1. Slack APIでアプリ作成

1. [Slack API](https://api.slack.com/apps){:target="_blank"}にアクセス
2. 「Create New App」→「From scratch」をクリック
3. アプリ名とワークスペースを選択して作成

## 2. OAuth & Permissions設定

1. 左メニューの「OAuth & Permissions」を開く
2. 「Redirect URLs」に以下を追加：
    ```
    http://localhost:8000/api/v1/auth/slack/callback
    ```
3. 「Save URLs」をクリック

## 3. OpenID Connect設定

1. 左メニューの「OpenID Connect」を開く
2. 「Enable OpenID Connect」をオンにする

## 4. クライアント認証情報の取得

1. 左メニューの「Basic Information」を開く
2. 「App Credentials」セクションから以下をコピー：
    - Client ID
    - Client Secret

## 5. シークレットファイルの設定

```bash
echo "your-client-id" > secrets/slack_client_id.txt
echo "your-client-secret" > secrets/slack_client_secret.txt
```

!!! info "OpenID Connect"
    SlackはOpenID Connectを使用します。
    YESOD Authは`openid`、`email`、`profile`スコープを要求し、
    ユーザー情報は`/api/openid.connect.userInfo`エンドポイントから取得します。

## 技術仕様

| 項目 | 値 |
|------|-----|
| 認可エンドポイント | `https://slack.com/openid/connect/authorize` |
| トークンエンドポイント | `https://slack.com/api/openid.connect.token` |
| ユーザー情報エンドポイント | `https://slack.com/api/openid.connect.userInfo` |
| スコープ | `openid email profile` |
| PKCE | ✅ 独自実装 |
| OpenID Connect | ✅ 対応 |

!!! info "PKCE対応について"
    SlackはPKCEを公式にはサポートしていません。
    YESOD Authはセキュリティ強化のため、独自にPKCE（S256）パラメータを送信しています。
    プロバイダー側でパラメータが無視される場合でも、セキュリティ上の問題はありません。
