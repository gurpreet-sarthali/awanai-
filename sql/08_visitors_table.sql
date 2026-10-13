-- ============================================================================
-- AwanAI: visitors table migration
-- Run this SQL in the Supabase SQL Editor (Dashboard > SQL Editor)
-- ============================================================================
--
-- PURPOSE:
--   Store self-reported visitor name and email for session continuity.
--
-- SECURITY MODEL:
--   * The email in this table is NOT verified.
--   * Row Level Security (RLS) is ENABLED.
--   * Anonymous clients (anon key) have NO read or write access.
--   * Only the service-role key (held by the backend server) can insert/update.
--   * No visitor can see another visitor's record.
--
-- DO NOT:
--   * Disable RLS on this table.
--   * Give the anon role any SELECT/INSERT/UPDATE policy on this table.
--   * Store passwords, tokens, or sensitive data in this table.
-- ============================================================================

-- 1. Create the visitors table
CREATE TABLE IF NOT EXISTS public.visitors (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name         TEXT NOT NULL CHECK (char_length(trim(name)) >= 2),
    email        TEXT NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 2. Unique index on email (lowercased) — one record per email address
CREATE UNIQUE INDEX IF NOT EXISTS visitors_email_unique
    ON public.visitors (lower(email));

-- 3. Index for fast lookups by email
CREATE INDEX IF NOT EXISTS visitors_email_idx
    ON public.visitors (lower(email));

-- 4. Index for time-based queries / cleanup
CREATE INDEX IF NOT EXISTS visitors_last_seen_idx
    ON public.visitors (last_seen_at);

-- 5. Enable Row Level Security
ALTER TABLE public.visitors ENABLE ROW LEVEL SECURITY;

-- 6. Revoke all default grants from anon and authenticated roles
--    (service_role bypasses RLS automatically)
REVOKE ALL ON TABLE public.visitors FROM anon, authenticated;

-- 7. NO RLS policies for anon or authenticated — service_role handles all ops.
--    If you later need a user to view only their own record, add a policy here.

-- ============================================================================
-- Optional: automatic cleanup of stale visitor records
-- Deletes records not seen in 90 days.
-- You can run this manually or schedule it as a cron job in Supabase.
-- ============================================================================
-- DELETE FROM public.visitors
-- WHERE last_seen_at < now() - INTERVAL '90 days';

-- ============================================================================
-- Verify
-- ============================================================================
-- SELECT tablename, rowsecurity
-- FROM pg_tables
-- WHERE schemaname = 'public' AND tablename = 'visitors';
