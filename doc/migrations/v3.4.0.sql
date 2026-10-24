-- Existing installations only. Take a D1 Time Travel bookmark first.
-- Run only if pragma_table_info('email') has no sender_email column.
-- This additive change is compatible with the previous Worker version.
ALTER TABLE email ADD COLUMN sender_email TEXT NOT NULL DEFAULT '';
