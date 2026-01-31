-- Seed audit tables with 100k records each
-- Data spread within existing partition range (2025-11 to 2026-04)

-- Generate 100k login_history records (spread over existing partitions)
INSERT INTO audit.login_history (user_id, provider, ip_address, user_agent, success, failure_reason, created_at)
SELECT
    CASE WHEN random() > 0.1 THEN gen_random_uuid() ELSE NULL END as user_id,
    (ARRAY['google', 'discord'])[floor(random() * 2 + 1)::int] as provider,
    '192.168.' || floor(random() * 255)::int || '.' || floor(random() * 255)::int as ip_address,
    (ARRAY[
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15',
        'Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36'
    ])[floor(random() * 4 + 1)::int] as user_agent,
    random() > 0.15 as success,
    CASE WHEN random() > 0.85 THEN (ARRAY['Invalid credentials', 'Account locked', 'Rate limited', 'Invalid state'])[floor(random() * 4 + 1)::int] ELSE NULL END as failure_reason,
    -- Generate dates between 2025-11-01 and 2026-04-30 (6 months range)
    '2025-11-01'::timestamptz + (random() * INTERVAL '180 days') as created_at
FROM generate_series(1, 100000);

-- Generate 100k auth_events records (spread over existing partitions)
INSERT INTO audit.auth_events (user_id, event_type, details, ip_address, user_agent, created_at)
SELECT
    gen_random_uuid() as user_id,
    (ARRAY[
        'login_success', 'login_failed', 'logout', 'token_refresh',
        'account_linked', 'account_unlinked', 'profile_updated',
        'session_revoked', 'all_sessions_revoked'
    ])[floor(random() * 9 + 1)::int] as event_type,
    jsonb_build_object(
        'provider', (ARRAY['google', 'discord'])[floor(random() * 2 + 1)::int],
        'action_id', floor(random() * 10000)::int
    ) as details,
    '10.' || floor(random() * 255)::int || '.' || floor(random() * 255)::int || '.' || floor(random() * 255)::int as ip_address,
    (ARRAY[
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari/605.1.15',
        'Mozilla/5.0 (X11; Linux x86_64) Firefox/121.0',
        'PostmanRuntime/7.36.0'
    ])[floor(random() * 4 + 1)::int] as user_agent,
    -- Generate dates between 2025-11-01 and 2026-04-30 (6 months range)
    '2025-11-01'::timestamptz + (random() * INTERVAL '180 days') as created_at
FROM generate_series(1, 100000);

-- Show counts
SELECT 'login_history' as table_name, COUNT(*) as count FROM audit.login_history
UNION ALL
SELECT 'auth_events' as table_name, COUNT(*) as count FROM audit.auth_events;
