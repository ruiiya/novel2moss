-- Bảo vệ revision / provenance: không sửa lịch sử đã xác nhận.
PRAGMA foreign_keys = ON;
BEGIN TRANSACTION;
CREATE TRIGGER story_revision_immutable_update BEFORE UPDATE ON story_revisions
BEGIN SELECT RAISE(ABORT,'story_revisions are append-only'); END;
CREATE TRIGGER story_revision_immutable_delete BEFORE DELETE ON story_revisions
BEGIN SELECT RAISE(ABORT,'story_revisions are append-only'); END;
CREATE TRIGGER shots_immutable_update BEFORE UPDATE ON shots
BEGIN SELECT RAISE(ABORT,'shots are append-only; create a new revision'); END;
CREATE TRIGGER shots_immutable_delete BEFORE DELETE ON shots
BEGIN SELECT RAISE(ABORT,'shots are append-only; create a new revision'); END;
CREATE TRIGGER layout_exports_immutable_update BEFORE UPDATE ON layout_exports
BEGIN SELECT RAISE(ABORT,'layout exports are immutable'); END;
CREATE TRIGGER layout_exports_immutable_delete BEFORE DELETE ON layout_exports
BEGIN SELECT RAISE(ABORT,'layout exports are immutable'); END;
CREATE TRIGGER qa_report_immutable_update BEFORE UPDATE ON qa_reports
BEGIN SELECT RAISE(ABORT,'QA reports are immutable'); END;
CREATE TRIGGER qa_report_immutable_delete BEFORE DELETE ON qa_reports
BEGIN SELECT RAISE(ABORT,'QA reports are immutable'); END;
CREATE TRIGGER source_version_immutable_update BEFORE UPDATE ON source_record_versions
BEGIN SELECT RAISE(ABORT,'source versions are immutable'); END;
CREATE TRIGGER source_version_immutable_delete BEFORE DELETE ON source_record_versions
BEGIN SELECT RAISE(ABORT,'source versions are immutable'); END;
CREATE TRIGGER story_event_actor_update BEFORE UPDATE OF actor_role_id,beat_id ON story_events
WHEN NEW.actor_role_id IS NOT NULL AND
 (SELECT r.story_id FROM story_roles r WHERE r.id=NEW.actor_role_id) <>
 (SELECT a.story_id FROM beats b JOIN acts a ON a.id=b.act_id WHERE b.id=NEW.beat_id)
BEGIN SELECT RAISE(ABORT,'event actor role belongs to another story'); END;
CREATE TRIGGER story_event_target_update BEFORE UPDATE OF target_role_id,beat_id ON story_events
WHEN NEW.target_role_id IS NOT NULL AND
 (SELECT r.story_id FROM story_roles r WHERE r.id=NEW.target_role_id) <>
 (SELECT a.story_id FROM beats b JOIN acts a ON a.id=b.act_id WHERE b.id=NEW.beat_id)
BEGIN SELECT RAISE(ABORT,'event target role belongs to another story'); END;
CREATE TRIGGER layout_items_immutable_update BEFORE UPDATE ON shot_layout_items
BEGIN SELECT RAISE(ABORT,'layout items are immutable; create a new layout revision'); END;
CREATE TRIGGER layout_items_immutable_delete BEFORE DELETE ON shot_layout_items
BEGIN SELECT RAISE(ABORT,'layout items are immutable'); END;
INSERT INTO schema_migrations(version) VALUES('003_history_guards');
COMMIT;
