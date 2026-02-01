# YESOD Auth

**OAuth 2.0認証基盤** - シンプルで安全な認証をあなたのアプリケーションに

---

## 特徴

<div class="grid cards" markdown>

- :material-shield-check: **OAuth 2.0対応**

    Google、Discordに対応。PKCEによるセキュアな認証フロー

- :material-refresh: **トークンローテーション**

    リフレッシュトークンの自動ローテーションでセキュリティを強化

- :material-webhook: **Webhook連携**

    ユーザーイベントを外部サービスにリアルタイム通知

- :material-docker: **Docker対応**

    Docker Composeで簡単にデプロイ

</div>

## クイックスタート

```bash
# リポジトリをクローン
git clone https://github.com/mashirou1234/yesod-auth.git
cd yesod-auth

# シークレットファイルを作成
cp secrets/*.example secrets/
# 各ファイルを編集してOAuthクレデンシャルを設定

# 起動
docker compose --profile default up -d
```

APIドキュメントは http://localhost:8000/docs で確認できます。

## アーキテクチャ

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Client    │────▶│  YESOD Auth │────▶│   OAuth     │
│   (SPA)     │◀────│    API      │◀────│  Provider   │
└─────────────┘     └──────┬──────┘     └─────────────┘
                           │
                    ┌──────┴──────┐
                    ▼             ▼
              ┌──────────┐  ┌──────────┐
              │ PostgreSQL│  │  Valkey  │
              │   (DB)    │  │ (Cache)  │
              └──────────┘  └──────────┘
```

## 対応プロバイダー

| プロバイダー | PKCE | 状態 |
|-------------|------|------|
| Google | ✅ | 対応済み |
| Discord | ❌ | 対応済み |

## ライセンス

MIT License
