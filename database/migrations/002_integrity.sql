-- Business integrity: role references must remain inside their own Story.
PRAGMA foreign_keys = ON;
BEGIN TRANSACTION;
CREATE TRIGGER role_event_actor_story BEFORE INSERT ON story_events
WHEN NEW.actor_role_id IS NOT NULL AND
 (SELECT r.story_id FROM story_roles r WHERE r.id=NEW.actor_role_id) <>
 (SELECT a.story_id FROM beats b JOIN acts a ON a.id=b.act_id WHERE b.id=NEW.beat_id)
BEGIN SELECT RAISE(ABORT,'event actor role belongs to another story'); END;
CREATE TRIGGER role_event_target_story BEFORE INSERT ON story_events
WHEN NEW.target_role_id IS NOT NULL AND
 (SELECT r.story_id FROM story_roles r WHERE r.id=NEW.target_role_id) <>
 (SELECT a.story_id FROM beats b JOIN acts a ON a.id=b.act_id WHERE b.id=NEW.beat_id)
BEGIN SELECT RAISE(ABORT,'event target role belongs to another story'); END;
CREATE TRIGGER role_shot_participant_story BEFORE INSERT ON shot_participants
WHEN (SELECT r.story_id FROM story_roles r WHERE r.id=NEW.story_role_id) <>
 (SELECT a.story_id FROM shots s JOIN beats b ON b.id=s.beat_id JOIN acts a ON a.id=b.act_id WHERE s.id=NEW.shot_id)
BEGIN SELECT RAISE(ABORT,'participant role belongs to another story'); END;
CREATE TRIGGER role_shot_actor_story BEFORE INSERT ON shot_interactions
WHEN (SELECT r.story_id FROM story_roles r WHERE r.id=NEW.actor_role_id) <>
 (SELECT a.story_id FROM shots s JOIN beats b ON b.id=s.beat_id JOIN acts a ON a.id=b.act_id WHERE s.id=NEW.shot_id)
BEGIN SELECT RAISE(ABORT,'interaction actor belongs to another story'); END;
CREATE TRIGGER role_shot_target_story BEFORE INSERT ON shot_interactions
WHEN NEW.target_role_id IS NOT NULL AND
 (SELECT r.story_id FROM story_roles r WHERE r.id=NEW.target_role_id) <>
 (SELECT a.story_id FROM shots s JOIN beats b ON b.id=s.beat_id JOIN acts a ON a.id=b.act_id WHERE s.id=NEW.shot_id)
BEGIN SELECT RAISE(ABORT,'interaction target belongs to another story'); END;
CREATE TRIGGER role_layout_item_story BEFORE INSERT ON shot_layout_items
WHEN NEW.story_role_id IS NOT NULL AND
 (SELECT r.story_id FROM story_roles r WHERE r.id=NEW.story_role_id) <>
 (SELECT a.story_id FROM shot_layouts l JOIN shots s ON s.id=l.shot_id
 JOIN beats b ON b.id=s.beat_id JOIN acts a ON a.id=b.act_id WHERE l.id=NEW.layout_id)
BEGIN SELECT RAISE(ABORT,'layout item role belongs to another story'); END;
CREATE TRIGGER layout_item_bounds_insert BEFORE INSERT ON shot_layout_items
WHEN NEW.x_min < 0 OR NEW.y_min < 0 OR
 NEW.x_max > (SELECT width FROM shot_layouts WHERE id=NEW.layout_id) OR
 NEW.y_max > (SELECT height FROM shot_layouts WHERE id=NEW.layout_id)
BEGIN SELECT RAISE(ABORT,'layout bbox out of canvas bounds'); END;
CREATE TRIGGER layout_item_bounds_update BEFORE UPDATE OF x_min,y_min,x_max,y_max,layout_id ON shot_layout_items
WHEN NEW.x_min < 0 OR NEW.y_min < 0 OR
 NEW.x_max > (SELECT width FROM shot_layouts WHERE id=NEW.layout_id) OR
 NEW.y_max > (SELECT height FROM shot_layouts WHERE id=NEW.layout_id)
BEGIN SELECT RAISE(ABORT,'layout bbox out of canvas bounds'); END;
INSERT INTO schema_migrations(version) VALUES('002_integrity');
COMMIT;
