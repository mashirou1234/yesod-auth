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

## organization制限時の挙動

- 現在のGitHub OAuth実装は`read:user user:email`のみを要求し、organization所属チェックは行いません。
- そのため、organization制限を有効化したい場合は、アプリ側で追加実装が必要です。
- 追加実装の例:
  - 認可スコープに`read:org`を追加
  - コールバック後にGitHub APIで所属organizationを検証
  - 未所属ユーザーはログイン完了前に拒否

## 共通チェック観点の適用例

- [x] Callback URL
  - [x] ローカル: `http://localhost:8000/api/v1/auth/github/callback`
  - [x] 本番: `https://<your-domain>/api/v1/auth/github/callback`
- [x] Scope
  - [x] 使用スコープ: `read:user user:email`
  - [x] 不足時の症状: メールアドレス取得不可で初回ログイン連携に失敗する
- [x] Secrets
  - [x] `secrets/github_client_id.txt`
  - [x] `secrets/github_client_secret.txt`
- [x] Test
  - [x] `curl -I "http://localhost:8000/api/v1/auth/github/login"` が `302` を返し、GitHub認可画面へ遷移する

## 技術仕様

| 項目 | 値 |
|------|-----|
| 認可エンドポイント | `https://github.com/login/oauth/authorize` |
| トークンエンドポイント | `https://github.com/login/oauth/access_token` |
| ユーザー情報エンドポイント | `https://api.github.com/user` |
| スコープ | `read:user user:email` |
| PKCE | ✅ 対応 |
| OpenID Connect | ❌ 非対応 |
