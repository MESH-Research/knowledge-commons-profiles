-- Bootstrap pg_stat_statements on the IDMS test database.
--
-- Prerequisite: `pg_stat_statements` must be in `shared_preload_libraries`
-- in the RDS parameter group. Toggling that requires an instance restart.
-- See loadtest/README.md.

CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Reset before a run (do this between scenarios so the diff is clean):
-- SELECT pg_stat_statements_reset();

-- Top-N by total time:
-- SELECT query, calls, total_exec_time, mean_exec_time, rows
-- FROM pg_stat_statements
-- ORDER BY total_exec_time DESC
-- LIMIT 25;
