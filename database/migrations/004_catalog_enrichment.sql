-- Catalog enrichment: assets, tag relations, captions, taxonomy, pose views.
-- Additive only. Do not edit migrations 001-003 after they were applied.
PRAGMA foreign_keys = ON;
BEGIN TRANSACTION;

ALTER TABLE catalog_tags ADD COLUMN original_name TEXT;
UPDATE catalog_tags SET original_name = name WHERE original_name IS NULL;

ALTER TABLE pose_references ADD COLUMN external_key TEXT;
ALTER TABLE pose_references ADD COLUMN caption_lang TEXT NOT NULL DEFAULT 'en';
ALTER TABLE pose_references ADD COLUMN caption_origin TEXT NOT NULL DEFAULT 'HUMAN';
ALTER TABLE pose_references ADD COLUMN caption_review TEXT NOT NULL DEFAULT 'REVIEWED';
ALTER TABLE pose_references ADD COLUMN category TEXT;
ALTER TABLE pose_references ADD COLUMN pose_code TEXT;
ALTER TABLE pose_references ADD COLUMN source_url TEXT;
CREATE UNIQUE INDEX ux_pose_reference_external ON pose_references(external_key)
  WHERE external_key IS NOT NULL;

CREATE TABLE catalog_assets (
  id TEXT PRIMARY KEY,
  source_record_id TEXT REFERENCES source_records(id),
  entity_kind TEXT NOT NULL,
  entity_id TEXT,
  asset_role TEXT NOT NULL,
  url_or_path TEXT NOT NULL,
  media_type TEXT,
  sha256 TEXT,
  license_note TEXT,
  width INTEGER,
  height INTEGER,
  metadata_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(metadata_json)),
  retrieved_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(source_record_id, asset_role, url_or_path)
);
CREATE INDEX ix_catalog_assets_entity ON catalog_assets(entity_kind, entity_id);

CREATE TABLE pose_reference_views (
  id TEXT PRIMARY KEY,
  pose_reference_id TEXT NOT NULL REFERENCES pose_references(id) ON DELETE CASCADE,
  view_name TEXT NOT NULL,
  asset_id TEXT REFERENCES catalog_assets(id),
  depth_asset_id TEXT REFERENCES catalog_assets(id),
  annotation_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(annotation_json)),
  UNIQUE(pose_reference_id, view_name, asset_id)
);

CREATE TABLE catalog_tag_relations (
  namespace TEXT NOT NULL,
  antecedent TEXT NOT NULL,
  consequent TEXT NOT NULL,
  relation_type TEXT NOT NULL CHECK(relation_type IN ('ALIAS','IMPLIES')),
  status TEXT NOT NULL DEFAULT 'active',
  source_record_id TEXT REFERENCES source_records(id),
  PRIMARY KEY(namespace, antecedent, consequent, relation_type)
);
CREATE INDEX ix_tag_relations_consequent ON catalog_tag_relations(namespace, consequent);

CREATE TABLE catalog_entity_links (
  id TEXT PRIMARY KEY,
  left_entity_kind TEXT NOT NULL,
  left_entity_id TEXT NOT NULL,
  right_source TEXT NOT NULL,
  right_external_key TEXT NOT NULL,
  relation TEXT NOT NULL,
  confidence TEXT NOT NULL DEFAULT 'CANDIDATE' CHECK(confidence IN ('CANDIDATE','REVIEWED','VERIFIED')),
  verified_by TEXT,
  source_record_id TEXT REFERENCES source_records(id),
  UNIQUE(left_entity_kind, left_entity_id, right_source, right_external_key, relation)
);

CREATE TABLE catalog_captions (
  id TEXT PRIMARY KEY,
  entity_kind TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  lang TEXT NOT NULL,
  text TEXT NOT NULL,
  origin TEXT NOT NULL DEFAULT 'SOURCE'
    CHECK(origin IN ('SOURCE','HUMAN','AUTO','LLM','TRANSLATED','SOURCE_KEYWORDS')),
  review TEXT NOT NULL DEFAULT 'UNREVIEWED'
    CHECK(review IN ('UNREVIEWED','REVIEWED','VERIFIED')),
  source_record_id TEXT REFERENCES source_records(id),
  UNIQUE(entity_kind, entity_id, lang, text)
);

CREATE TABLE catalog_tag_taxonomy (
  namespace TEXT NOT NULL,
  category INTEGER NOT NULL,
  label TEXT NOT NULL,
  source_record_id TEXT REFERENCES source_records(id),
  PRIMARY KEY(namespace, category)
);

INSERT INTO schema_migrations(version) VALUES('004_catalog_enrichment');
COMMIT;
