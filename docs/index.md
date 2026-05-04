# YESOD Auth

**OAuth 2.0認証基盤** - シンプルで安全な認証をあなたのアプリケーションに

---

## 特徴

| | |
|---|---|
| :material-shield-check: **OAuth 2.0対応** | :material-refresh: **トークンローテーション** |
| OAuthガイドで扱う8プロバイダー（Google、GitHub、X (Twitter)、LinkedIn、Facebook、Discord、Slack、Twitch）の設定手順を提供。PKCEによるセキュアな認証フロー | リフレッシュトークンの自動ローテーションでセキュリティを強化 |
| :material-webhook: **Webhook連携** | :material-docker: **Docker対応** |
| ユーザーイベントを外部サービスにリアルタイム通知 | Docker Composeで簡単にデプロイ |

> 対応プロバイダー表記の参照元（正）は `docs/guides/oauth/index.md` です。
> 機能説明の参照元（正）は `docs/index.md` とし、`README.md` は本項目へ同期します。

## 導入者向け最短導線（3ステップ）

初回導入時は、次の順序で確認すると最短で環境を立ち上げられます。

1. [インストール](installation.md): 必要要件、`default` / `full` / `ci` の profile 選択、`valkey` 前提を確認
2. [クイックスタート](getting-started.md): 選択した profile でシークレット作成から起動・ヘルスチェックまで実施
3. [OAuth設定ガイド](guides/oauth/index.md): 使用するプロバイダーだけを有効化

## 運用者向け最短導線

セルフホスト運用では、入口を次の 3 文書に固定すると初動確認と障害切り分けがぶれにくくなります。

| 目的 | 最初に見る文書 | 確認すること |
|---|---|---|
| 導入前提を固める | [インストール](installation.md) | 必要要件、profile 選択、OAuth secret 配置 |
| 起動後の異常を切り分ける | [トラブルシューティング](help/troubleshooting.md) | callback / state mismatch / secret 不備の初動 |
| 運用中のよくある確認を引く | [FAQ](help/faq.md) | token、provider、再起動、Webhook の横断確認 |

`README.md` はリポジトリ概要と最短起動手順、`docs/index.md` は上記 3 文書への入口として扱います。

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
セルフホスト運用時の秘密情報配置は
[インストールガイドの配置例](installation.md#セルフホスト向け秘密情報配置例)を参照してください。

主要ドキュメント:

- [Quick Start](getting-started.md)
- [インストール](installation.md)
- [トラブルシューティング](help/troubleshooting.md)
- [FAQ](help/faq.md)
- [OAuth設定ガイド](guides/oauth/index.md)

起動直後の最小確認は [インストール手順の「docker compose利用時の最小確認手順」](installation.md#docker-compose利用時の最小確認手順) を参照してください。

## 表記統一サマリー（レビュー用）

`docs/index.md` と [OAuth設定ガイド](guides/oauth/index.md) の対応表記を、次のルールで同期しています。

| 項目 | 統一表記 |
|---|---|
| provider 並び順 | Google → GitHub → X (Twitter) → LinkedIn → Facebook → Discord → Slack → Twitch |
| provider 名称 | `X (Twitter)` を含め、各ページで同一の表記を使用 |
| 主要導線 | Quick Start は `docs/getting-started.md`、OAuth Guide は `docs/guides/oauth/index.md` を案内 |

## API認証トラブル時の参照順

1. [インストール](installation.md#oauth認証情報)で OAuth シークレットと profile 設定を確認
2. [クイックスタート](getting-started.md#4-動作確認)で `/health` と `/docs` を確認
3. [トラブルシューティング](help/troubleshooting.md#state-mismatch-flow)で原因を切り分け

## 学習順ガイド（導入→API→運用）

「まず動かす」「API仕様を確認する」「運用手順を固める」の順に進めると、オンボーディングと本番準備を並行しやすくなります。

1. 導入
   - [導入者向け最短導線（3ステップ）](#導入者向け最短導線3ステップ)を先に実施
   - 詳細が必要な場合のみ、各ドキュメント内の補足手順へ進む
2. API
   - [認証API](api/auth.md): login / callback / refresh / logout の入出力を確認
   - [ユーザーAPI](api/users.md): `/api/v1/users` 系の取得・更新フローを確認
   - [Webhook API](api/webhooks.md): 署名検証と再送時の扱いを確認
3. 運用
   - [デプロイガイド](guides/deployment.md): デプロイと secrets ローテーション手順を確認
   - [トラブルシューティング](help/troubleshooting.md): callback / state mismatch などの切り分け手順を確認
   - [FAQ](help/faq.md): 導入後によくある確認事項を横断で参照

API 導線の同期確認は次の 3 点を正本にします。

| 領域 | 正本 | 確認する用語 |
| --- | --- | --- |
| 認証 | [認証API](api/auth.md) | `refresh` / `logout` / `state mismatch` |
| ユーザー | [ユーザーAPI](api/users.md) | `sync-from-provider` / provider 連携 |
| Webhook | [Webhook API](api/webhooks.md) | `delivery_id` / retry / 署名検証 |

```bash
rg -n "refresh|logout|sync-from-provider|delivery_id|retry" docs/index.md docs/api/*.md docs/help/troubleshooting.md
```

## 運用導線の同期チェック

トップページの導線を更新したときは、次の 3 文書へのリンクと記述の整合をあわせて確認してください。

- [インストール](installation.md): 導入前提と profile / secret の説明が最新か
- [トラブルシューティング](help/troubleshooting.md): 障害切り分け導線が最新か
- [FAQ](help/faq.md): 運用中によくある確認事項への導線が残っているか

チェック手順:

1. `docs/index.md` から上記 3 文書へ到達できることを確認する
2. 3 文書の見出し・用語・導線がトップページの説明と矛盾しないことを確認する
3. 三点同期チェックの結果を、更新を行った Issue または PR コメントへ日付付きで残す

記録例:

- [ ] installation を確認
- [ ] troubleshooting を確認
- [ ] faq を確認
- 記録先: Issue / PR コメント

リフレッシュトークン運用時の注意点は [インストールガイド](installation.md#リフレッシュトークン運用時の注意) を参照してください。

OAuth provider を追加する場合は、先に[事前チェックリスト](installation.md#oauth-provider追加時の事前チェック)を実施してください。

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

<div class="provider-icons">
  <a href="guides/oauth/google.md" title="Google">
    <img src="assets/icons/google.svg" alt="Google" width="48" height="48">
  </a>
  <a href="guides/oauth/github.md" title="GitHub">
    <img src="assets/icons/github.svg" alt="GitHub" width="48" height="48">
  </a>
  <a href="guides/oauth/x.md" title="X (Twitter)">
    <img src="assets/icons/x.svg" alt="X (Twitter)" width="48" height="48">
  </a>
  <a href="guides/oauth/linkedin.md" title="LinkedIn">
    <img src="assets/icons/linkedin.svg" alt="LinkedIn" width="48" height="48">
  </a>
  <a href="guides/oauth/facebook.md" title="Facebook">
    <img src="assets/icons/facebook.svg" alt="Facebook" width="48" height="48">
  </a>
  <a href="guides/oauth/discord.md" title="Discord">
    <img src="assets/icons/discord.svg" alt="Discord" width="48" height="48">
  </a>
  <a href="guides/oauth/slack.md" title="Slack">
    <img src="assets/icons/slack.svg" alt="Slack" width="48" height="48">
  </a>
  <a href="guides/oauth/twitch.md" title="Twitch">
    <img src="assets/icons/twitch.svg" alt="Twitch" width="48" height="48">
  </a>
</div>

各プロバイダーの対応状況（公式PKCE/独自PKCE/OpenID Connect/備考）は、[OAuth設定ガイド](guides/oauth/index.md)の一覧表を正として参照してください。

## ライセンス

MIT License
