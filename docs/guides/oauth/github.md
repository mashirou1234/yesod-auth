# GitHub OAuth

## 1. GitHub OAuth Appの作成

1. [GitHub Developer Settings](https://github.com/settings/developers){:target="_blank"}にアクセス
2. 「OAuth Apps」→「New OAuth App」をクリック
3. 必要な情報を入力：
    - Application name: アプリ名
    - Homepage URL: `http://localhost:8000`
    - Authorization callback URL: `http://localhost:8000/api/v1/auth/github/callback`
4. 「Register application」をクリック

## 1.1 Callback URL の登録値

GitHub OAuth App には、利用環境ごとに次の callback URL を登録します。
本番では `localhost` を残さず、API の公開ドメインに置き換えてください。

| 環境 | 登録する callback URL | 確認先 |
|------|------------------------|--------|
| ローカル開発 | `http://localhost:8000/api/v1/auth/github/callback` | OAuth App の `Authorization callback URL` |
| セルフホスト本番 | `https://<api-domain>/api/v1/auth/github/callback` | 本番 OAuth App の `Authorization callback URL` |

開始エンドポイントは `GET /api/v1/auth/github` です。callback URL を直接開かず、必ず開始エンドポイントから GitHub 認可画面へ遷移することを確認してください。
共通の確認順は [OAuth設定: Callback確認の共通チェックリスト](index.md#oauth-callback-checklist) を参照してください。

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

## 3.5 必要スコープの確認手順

GitHub OAuth App 設定画面には固定 scope の入力欄がないため、認可リクエストと認可後トークンの両方で確認します。

1. ローカル API を起動した状態で、認可開始 URL のリダイレクト先を確認する

```bash
curl -sSI "http://localhost:8000/api/v1/auth/github" | rg -i '^location:'
```

2. `location` ヘッダーのクエリに `scope=read:user%20user:email`（または同等のURLエンコード）が含まれることを確認する
3. 実際に GitHub で認可を完了し、アクセストークンを取得する
4. 取得したトークンに対してレスポンスヘッダーを確認し、`X-OAuth-Scopes` に `read:user, user:email` が含まれることを確認する

```bash
curl -sSI \
  -H "Authorization: Bearer <github_access_token>" \
  https://api.github.com/user | rg -i '^x-oauth-scopes:'
```

5. `user:email` が不足している場合は、GitHub 側で再認可（連携解除後の再ログイン）を実施する

### scope不足時の再同意手順

`read:user user:email` のどちらかが不足している場合、YESOD Auth 側で secret を直しても既存の認可 grant は自動更新されません。次の順で再同意してください。

1. GitHub の Authorized OAuth Apps で対象アプリの認可を取り消す
2. `GET /api/v1/auth/github` から認可を開始する
3. consent 画面で `read:user` と `user:email` が表示されることを確認する
4. callback 後に `X-OAuth-Scopes` を再確認する

```bash
curl -sSI -H "Authorization: Bearer <github_access_token>" https://api.github.com/user | rg -i '^x-oauth-scopes:'
```

## organization制限時の挙動

現在の YESOD Auth は GitHub OAuth で organization 制限を実施しません。  
つまり、`/api/v1/auth/github` と `/api/v1/auth/github/callback` は organization 所属を判定せず、認可成功後は通常どおりログイン完了します。

| 観点 | 現在の挙動 |
| --- | --- |
| 認可スコープ | `read:user user:email` のみ要求 |
| organization 所属チェック | 実施しない |
| 非所属ユーザーの扱い | organization を理由に拒否しない（通常のログイン結果になる） |

organization メンバー限定にしたい場合は、アプリ側で次を追加してください。

1. 認可スコープに `read:org` を追加
2. callback 後に GitHub API で所属 organization を検証
3. 未所属ユーザーはログイン完了前に `403` などで拒否

セルフホスト運用では、導入前に「許可 organization 名」「未所属時のエラー応答」「監査ログ項目」を先に決めておくと、運用時の問い合わせを減らせます。

共通の callback 確認手順は [OAuth設定の共通チェックリスト](index.md#oauth-callback-checklist) を先に参照してください。

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
