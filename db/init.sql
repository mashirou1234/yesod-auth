-- Initialize pg_cron extension
CREATE EXTENSION IF NOT EXISTS pg_cron;

-- Grant usage to yesod_user
GRANT USAGE ON SCHEMA cron TO yesod_user;
