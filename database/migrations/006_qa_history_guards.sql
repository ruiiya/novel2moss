-- Restore QA append-only guards after 005 rebuilt qa_reports to remove RENDER.
PRAGMA foreign_keys = ON;
BEGIN TRANSACTION;

DROP TRIGGER IF EXISTS qa_report_immutable_update;
DROP TRIGGER IF EXISTS qa_report_immutable_delete;
CREATE TRIGGER qa_report_immutable_update BEFORE UPDATE ON qa_reports
BEGIN SELECT RAISE(ABORT,'QA reports are immutable'); END;
CREATE TRIGGER qa_report_immutable_delete BEFORE DELETE ON qa_reports
BEGIN SELECT RAISE(ABORT,'QA reports are immutable'); END;

INSERT INTO schema_migrations(version) VALUES('006_qa_history_guards');
COMMIT;
