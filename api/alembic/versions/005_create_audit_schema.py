"""Create audit schema with partitioned tables.

- audit.login_history: Login attempts (success/failure)
- audit.auth_events: All authentication events
- Monthly partitions with 36-month retention
- pg_cron jobs for partition management

Revision ID: 005
Revises: 004
Create Date: 2026-01-31
"""

from datetime import datetime, timedelta

from alembic import op

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None

# Retention period in months
RETENTION_MONTHS = 36


def upgrade() -> None:
    # Create audit schema
    op.execute("CREATE SCHEMA IF NOT EXISTS audit")

    # Create login_history partitioned table
    op.execute("""
        CREATE TABLE audit.login_history (
            id UUID DEFAULT gen_random_uuid(),
            user_id UUID,
            provider VARCHAR(50) NOT NULL,
            ip_address VARCHAR(45),
            user_agent VARCHAR(500),
            success BOOLEAN NOT NULL,
            failure_reason VARCHAR(255),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (id, created_at)
        ) PARTITION BY RANGE (created_at)
    """)

    # Create auth_events partitioned table
    op.execute("""
        CREATE TABLE audit.auth_events (
            id UUID DEFAULT gen_random_uuid(),
            user_id UUID,
            event_type VARCHAR(50) NOT NULL,
            details JSONB,
            ip_address VARCHAR(45),
            user_agent VARCHAR(500),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (id, created_at)
        ) PARTITION BY RANGE (created_at)
    """)

    # Create indexes
    op.execute("CREATE INDEX idx_login_history_user_id ON audit.login_history (user_id)")
    op.execute("CREATE INDEX idx_login_history_created_at ON audit.login_history (created_at)")
    op.execute("CREATE INDEX idx_auth_events_user_id ON audit.auth_events (user_id)")
    op.execute("CREATE INDEX idx_auth_events_event_type ON audit.auth_events (event_type)")
    op.execute("CREATE INDEX idx_auth_events_created_at ON audit.auth_events (created_at)")

    # Create initial partitions (current month + 3 months ahead)
    now = datetime.now()
    for i in range(-1, 4):  # -1 to include previous month for safety
        month_start = datetime(now.year, now.month, 1) + timedelta(days=32 * i)
        month_start = datetime(month_start.year, month_start.month, 1)
        next_month = month_start + timedelta(days=32)
        next_month = datetime(next_month.year, next_month.month, 1)

        partition_name = month_start.strftime("%Y_%m")

        op.execute(f"""
            CREATE TABLE IF NOT EXISTS audit.login_history_{partition_name}
            PARTITION OF audit.login_history
            FOR VALUES FROM ('{month_start.strftime("%Y-%m-%d")}')
            TO ('{next_month.strftime("%Y-%m-%d")}')
        """)

        op.execute(f"""
            CREATE TABLE IF NOT EXISTS audit.auth_events_{partition_name}
            PARTITION OF audit.auth_events
            FOR VALUES FROM ('{month_start.strftime("%Y-%m-%d")}')
            TO ('{next_month.strftime("%Y-%m-%d")}')
        """)

    # Create function to manage partitions
    op.execute("""
        CREATE OR REPLACE FUNCTION audit.manage_partitions()
        RETURNS void AS $$
        DECLARE
            partition_date DATE;
            partition_name TEXT;
            start_date DATE;
            end_date DATE;
            drop_date DATE;
            table_name TEXT;
        BEGIN
            -- Create partitions for next 3 months
            FOR i IN 0..3 LOOP
                partition_date := DATE_TRUNC('month', CURRENT_DATE + (i || ' months')::INTERVAL);
                partition_name := TO_CHAR(partition_date, 'YYYY_MM');
                start_date := partition_date;
                end_date := partition_date + '1 month'::INTERVAL;

                -- login_history
                IF NOT EXISTS (
                    SELECT 1 FROM pg_tables
                    WHERE schemaname = 'audit'
                    AND tablename = 'login_history_' || partition_name
                ) THEN
                    EXECUTE format(
                        'CREATE TABLE audit.login_history_%s PARTITION OF audit.login_history FOR VALUES FROM (%L) TO (%L)',
                        partition_name, start_date, end_date
                    );
                END IF;

                -- auth_events
                IF NOT EXISTS (
                    SELECT 1 FROM pg_tables
                    WHERE schemaname = 'audit'
                    AND tablename = 'auth_events_' || partition_name
                ) THEN
                    EXECUTE format(
                        'CREATE TABLE audit.auth_events_%s PARTITION OF audit.auth_events FOR VALUES FROM (%L) TO (%L)',
                        partition_name, start_date, end_date
                    );
                END IF;
            END LOOP;

            -- Drop partitions older than retention period (36 months)
            drop_date := DATE_TRUNC('month', CURRENT_DATE - '36 months'::INTERVAL);

            FOR table_name IN
                SELECT tablename FROM pg_tables
                WHERE schemaname = 'audit'
                AND (tablename LIKE 'login_history_%' OR tablename LIKE 'auth_events_%')
            LOOP
                -- Extract date from partition name
                IF TO_DATE(SUBSTRING(table_name FROM '[0-9]{4}_[0-9]{2}$'), 'YYYY_MM') < drop_date THEN
                    EXECUTE format('DROP TABLE IF EXISTS audit.%I', table_name);
                    RAISE NOTICE 'Dropped partition: %', table_name;
                END IF;
            END LOOP;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # Schedule pg_cron job (runs daily at 2:00 AM)
    op.execute("""
        SELECT cron.schedule(
            'audit_partition_management',
            '0 2 * * *',
            'SELECT audit.manage_partitions()'
        )
    """)


def downgrade() -> None:
    # Remove pg_cron job
    op.execute("SELECT cron.unschedule('audit_partition_management')")

    # Drop function
    op.execute("DROP FUNCTION IF EXISTS audit.manage_partitions()")

    # Drop schema and all tables
    op.execute("DROP SCHEMA IF EXISTS audit CASCADE")
