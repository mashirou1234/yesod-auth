---
inclusion: fileMatch
fileMatchPattern: "**/alembic/versions/*.py"
---

# Alembicマイグレーション作成ガイドライン

このガイドラインは、マイグレーションファイルを作成・編集する際に適用されます。

## CI互換性チェックリスト

### PostgreSQL拡張機能
CI環境（db-ci）には以下の拡張がインストールされていません:

- [ ] `pg_cron` - スケジュールジョブ
- [ ] `pg_partman` - パーティション管理
- [ ] その他カスタム拡張

### 必須パターン: 拡張の条件付き使用

```python
# ❌ NG: 直接呼び出し（CI環境でエラー）
op.execute("SELECT cron.schedule('job_name', '0 2 * * *', 'SELECT ...')")

# ✅ OK: 拡張の存在確認後に実行
op.execute("""
    DO $$
    BEGIN
        IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron') THEN
            PERFORM cron.schedule(
                'job_name',
                '0 2 * * *',
                'SELECT ...'
            );
        END IF;
    END $$;
""")
```

### downgrade()も同様に

```python
def downgrade() -> None:
    # pg_cronジョブの削除も条件付き
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron') THEN
                PERFORM cron.unschedule('job_name');
            END IF;
        END $$;
    """)
```

## パーティションテーブル

パーティションテーブル自体はCI環境でも作成可能ですが、
テストコード（SQLite）からは直接アクセスできません。

```python
# パーティションテーブルの作成はOK
op.execute("""
    CREATE TABLE audit.events (
        ...
    ) PARTITION BY RANGE (created_at)
""")
```

## スキーマ作成

```python
# スキーマ作成はCI環境でも動作する
op.execute("CREATE SCHEMA IF NOT EXISTS audit")
```

## 参考: 既存マイグレーション
- `005_create_audit_schema.py` - pg_cron条件付き実行の実装例
