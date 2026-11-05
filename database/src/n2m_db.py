#!/usr/bin/env python3
"""Novel2Moss DB starter: stdlib-only SQLite migrations, curated seeds, imports, layout compiler.

No network requests are made. Fetch external data explicitly after checking source terms.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / 'data' / 'novel2moss.db'


def js(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def sha(value: bytes | str) -> str:
    if isinstance(value, str):
        value = value.encode('utf-8')
    return hashlib.sha256(value).hexdigest()


def uid(prefix: str) -> str:
    return f'{prefix}_{uuid.uuid4().hex[:18]}'


def connect(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys = ON')
    con.execute('PRAGMA journal_mode = WAL')
    con.execute('PRAGMA busy_timeout = 5000')
    return con


def _table_exists(con, name):
    return con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def _backup_render_state(con):
    """Export V1 render/QA rows to a sidecar before migration 005 drops them."""
    jobs = [dict(r) for r in con.execute('SELECT * FROM render_jobs')] if _table_exists(con, 'render_jobs') else []
    assets = [dict(r) for r in con.execute('SELECT * FROM render_assets')] if _table_exists(con, 'render_assets') else []
    qa = ([dict(r) for r in con.execute("SELECT * FROM qa_reports WHERE subject_kind='RENDER'")]
          if _table_exists(con, 'qa_reports') else [])
    if not jobs and not assets and not qa:
        return None
    db_row = con.execute('PRAGMA database_list').fetchone()
    db_path = Path(db_row[2]) if db_row and db_row[2] else (ROOT / 'data' / 'novel2moss.db')
    backup_dir = db_path.parent / 'backups'
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    target = backup_dir / f'render-export-{stamp}.json'
    payload = {
        'exported_at': datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        'database': str(db_path),
        'note': 'Renderer state removed by migration 005_db_boundary; this file is the external backup.',
        'render_jobs': jobs,
        'render_assets': assets,
        'render_qa_reports': qa,
    }
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Backed up render state before DB boundary migration: {target}')
    return target


def apply_migrations(con):
    # Existing DBs without the migrations table are supported.
    con.execute('CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT (datetime(\'now\')))')
    applied = {r[0] for r in con.execute('SELECT version FROM schema_migrations')}
    for file in sorted((ROOT / 'migrations').glob('*.sql')):
        version = file.stem
        if version in applied:
            continue
        if version == '005_db_boundary':
            _backup_render_state(con)
        con.executescript(file.read_text(encoding='utf-8'))
        if not con.execute('SELECT 1 FROM schema_migrations WHERE version=?', (version,)).fetchone():
            con.execute('INSERT INTO schema_migrations(version) VALUES (?)', (version,))
        con.commit()
        print(f'Applied migration: {version}')


def register_source(con, source_id, name, kind, homepage, license_label, license_url='', notes=''):
    con.execute('''INSERT INTO source_registry(id,name,kind,homepage_url,license_label,license_url,usage_notes)
      VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
      name=excluded.name,kind=excluded.kind,homepage_url=excluded.homepage_url,
      license_label=excluded.license_label,license_url=excluded.license_url,
      usage_notes=excluded.usage_notes''',
      (source_id, name, kind, homepage, license_label, license_url, notes))


SOURCES = [
    ('curated', 'Novel2Moss original curated examples', 'local', 'local://novel2moss', 'Original project data', '', 'Only self-authored sample metadata.'),
    ('deepghs', 'DeepGHS anime character index', 'dataset', 'https://huggingface.co/datasets/deepghs/character_index', 'MIT (dataset listing); character IP separately', 'https://huggingface.co/datasets/deepghs/character_index', 'Import names/core tags only; these are candidates, NOT verified original outfits. Check dataset and third-party rights.'),
    ('danbooru', 'Danbooru tag taxonomy API', 'api', 'https://danbooru.donmai.us/wiki_pages/api:tags', 'Check current site terms and individual content rights', 'https://danbooru.donmai.us/wiki_pages/help:api', 'Import tag metadata only; not images; rate-limit and use proper User-Agent for collecting.'),
    ('wikidata', 'Wikidata structured entities', 'api', 'https://www.wikidata.org/wiki/Wikidata:Data_access', 'CC0 for structured data', 'https://www.wikidata.org/wiki/Wikidata:Licensing', 'Prefer targeted SPARQL export, not bulk fuzzy search; verify identifiers.'),
    ('moss_official', 'OpenMOSS Layout examples', 'documentation', 'https://github.com/OpenMOSS/MOSS-Image/blob/main/USERGUIDE.md', 'Code repository rights may differ from generated images', '', 'Read official spec as reference, use original layout templates in this project.'),
    ('posescript', 'PoseScript pose descriptions', 'dataset', 'https://github.com/naver/posescript', 'CC BY-NC-SA 4.0 dataset', 'https://github.com/naver/posescript/blob/main/LICENSE', 'Optional manual import only; non-commercial/SA and AMASS dependencies.'),
    ('dbr_e621_lists', 'Danbooru tag list archive (DraconicDragon; V2 uses Danbooru namespace)', 'dataset', 'https://github.com/DraconicDragon/dbr-e621-lists-archive', 'Repository license plus upstream Danbooru terms', 'https://github.com/DraconicDragon/dbr-e621-lists-archive/blob/main/LICENSE', 'V2 imports only selected Danbooru tags; no e621 or merged list.'),
    ('ai_pose_gallery', 'AI Pose Gallery metadata', 'dataset', 'https://github.com/anhao/ai-pose-gallery-zh', 'Code MIT; image/data rights may differ per asset', 'https://github.com/anhao/ai-pose-gallery-zh', 'Import JSON metadata only. Do not download or redistribute images before checking per-asset terms.'),
    ('charadb', 'CharaDB generic outfit metadata', 'dataset', 'https://github.com/taki-ttt/charadb', 'Check CharaDB terms; metadata and images can differ', 'https://github.com/taki-ttt/charadb', 'Generic outfit metadata only; never treat it as a canon outfit for a character.'),
]

VOCAB = {
  'POSE': [
    ('standing','standing upright','đứng thẳng','The person is standing upright.'),
    ('sitting','sitting on a chair','ngồi ghế','The person is sitting on a chair.'),
    ('kneeling','kneeling on the floor','quỳ','The person is kneeling on the floor.'),
    ('crouching','crouching low','ngồi xổm','The person is crouching low.'),
    ('leaning','leaning toward another person','nghiêng người','The person leans slightly toward another.'),
    ('reclining','reclining','ngả người','The person reclines with their back supported.'),
    ('walking','walking forward','đi bộ','The person walks forward.'),
    ('arms_crossed','arms crossed','khoanh tay','The person crosses both arms over the chest.'),
    ('looking_back','looking over the shoulder','ngoảnh đầu','The person looks over one shoulder.'),
  ],
  'ACTION': [
    ('head_pat','patting a head','xoa đầu','Actor gently pats the head of the target.'),
    ('handshake','shaking hands','bắt tay','Actor and target shake hands.'),
    ('pointing','pointing toward','chỉ tay','Actor points toward a target.'),
    ('handing_object','handing an object','đưa vật','Actor hands an object to the target.'),
    ('talking','speaking to','nói chuyện','Actor speaks to target.'),
    ('walking_together','walking together','cùng đi','Two people walk side by side.'),
    ('looking_at','looking at','nhìn','Actor looks toward the target.'),
    ('hugging','hugging','ôm','Two people embrace.'),
    ('reaching','reaching toward','vươn tay','Actor extends one arm toward a target.'),
  ],
  'EXPRESSION': [
    ('smile','gentle smile','mỉm cười','A gentle, visible smile.'),
    ('surprised','surprised expression','ngạc nhiên','Eyes widened with surprise.'),
    ('neutral','neutral expression','bình thản','Neutral relaxed facial expression.'),
    ('concerned','concerned expression','lo lắng','Brows slightly knitted in concern.'),
    ('laughing','laughing','cười lớn','Laughing with an open smile.'),
  ],
  'SPATIAL': [
    ('left_of','to the left of','bên trái','Place the actor to the left of the target.'),
    ('right_of','to the right of','bên phải','Place the actor to the right of the target.'),
    ('in_front_of','in front of','phía trước','Place the actor in front of the target.'),
    ('behind','behind','phía sau','Place the actor behind the target.'),
    ('facing','facing','đối diện','Make actor face the target.'),
    ('close_to','close to','ở gần','Place the two subjects close together.'),
    ('touching','touching','chạm','Allow physical contact between two subjects.'),
  ],
  'CAMERA': [
    ('wide_shot','wide shot','toàn cảnh','Wide shot showing full environment.'),
    ('medium_shot','medium shot','trung cảnh','Medium shot framing upper body or figures.'),
    ('close_up','close-up','cận cảnh','Close-up focusing on face or an object.'),
    ('over_shoulder','over-the-shoulder shot','qua vai','Camera over one participant shoulder.'),
    ('eye_level','eye-level angle','ngang mắt','Camera positioned at eye level.'),
    ('low_angle','low angle','góc thấp','Camera looks upward from a low angle.'),
  ],
  'LIGHTING': [
    ('soft_daylight','soft daylight','ánh sáng ban ngày','Soft natural daylight.'),
    ('golden_hour','golden hour','giờ vàng','Warm golden-hour sunlight.'),
    ('moonlight','moonlight','ánh trăng','Cool blue moonlight.'),
    ('studio_softbox','soft studio light','ánh sáng studio','Soft diffused studio illumination.'),
  ],
  'LOCATION': [
    ('sunlit_room','sunlit room','phòng có nắng','A sunlit room with a window.'),
    ('garden','garden','khu vườn','A green garden with plants.'),
    ('classroom','classroom','lớp học','An empty classroom interior.'),
    ('city_street','city street','đường phố','A city street.'),
  ],
  'STYLE': [
    ('anime_illustration','anime illustration','minh họa anime','Detailed anime illustration.'),
    ('painterly','painterly illustration','tranh vẽ','Painterly illustration with soft textures.'),
    ('photorealistic','photorealistic image','ảnh chân thực','Photorealistic image.'),
  ],
}

TEMPLATES = [
    ('solo_center', 1, {'width':1024,'height':1024,'bbox_coord_space':'abs','bbox_format':'xyxy',
                       'summary':{'meta':['anime illustration'],'canvas':'single','caption':'A character in a softly lit scene.'},
                       'items':[{'label':'character','caption':'One character, full body, centered.','bbox':[260,60,764,970]}]}),
    ('duo_side_by_side', 2, {'width':1024,'height':1024,'bbox_coord_space':'abs','bbox_format':'xyxy',
                       'summary':{'meta':['anime illustration'],'canvas':'single','caption':'Two characters standing side by side.'},
                       'items':[{'label':'character','caption':'A character on the left.','bbox':[80,96,560,960]},
                                {'label':'character','caption':'A character on the right.','bbox':[470,96,950,960]}]}),
    ('duo_interaction', 2, {'width':1024,'height':1024,'bbox_coord_space':'abs','bbox_format':'xyxy',
                       'summary':{'meta':['anime illustration'],'canvas':'single','caption':'Two characters interact in a room.'},
                       'items':[{'label':'character','caption':'Actor stands on the left and reaches toward the other person.','bbox':[110,100,625,950]},
                                {'label':'character','caption':'Recipient is seated on the right.','bbox':[510,270,955,970]}]}),
    ('solo_wide_1536x1024', 1, {'width':1536,'height':1024,'bbox_coord_space':'abs','bbox_format':'xyxy',
                       'summary':{'meta':['anime illustration'],'canvas':'single','caption':'A character in a wide landscape scene.'},
                       'items':[{'label':'character','caption':'One character, full body, centered in a wide frame.','bbox':[500,70,1036,960]}]}),
    ('duo_wide_1536x1024', 2, {'width':1536,'height':1024,'bbox_coord_space':'abs','bbox_format':'xyxy',
                       'summary':{'meta':['anime illustration'],'canvas':'single','caption':'Two characters share a wide landscape frame.'},
                       'items':[{'label':'character','caption':'A character on the left side of a wide frame.','bbox':[110,90,650,970]},
                                {'label':'character','caption':'A character on the right side of a wide frame.','bbox':[820,90,1380,970]}]}),
]


def seed(con):
    for s in SOURCES:
        register_source(con, *s)
    for category, rows in VOCAB.items():
        for code, en, vi, description in rows:
            con.execute('''INSERT OR IGNORE INTO vocabulary
                (id,category,code,label_en,label_vi,description_en,source_record_id)
                VALUES(?,?,?,?,?,?,NULL)''',
                (f'vocab:{category.lower()}:{code}',category,code,en,vi,description))
    for name, count, template in TEMPLATES:
        con.execute('''INSERT OR IGNORE INTO layout_templates
          (id,name,participant_count,scene_tags_json,draft_json,verified)
          VALUES(?,?,?,?,?,1)''',
          (f'layout:{name}',name,count,js([]),js(template)))
    con.commit()
    print(f'Seeded {sum(map(len, VOCAB.values()))} vocabulary items + {len(TEMPLATES)} templates + {len(SOURCES)} sources (idempotent).')


def track_source_record(con, source_id, external_key, entity_kind, payload, run_id):
    body = js(payload)
    digest = sha(body)
    record_id = f'src:{source_id}:{sha(external_key)[:18]}'
    con.execute('''INSERT INTO source_records (id,source_id,external_key,entity_kind,content_sha256,payload_json,import_run_id)
                   VALUES (?,?,?,?,?,?,?) ON CONFLICT(source_id,external_key) DO UPDATE SET
                   content_sha256=excluded.content_sha256,payload_json=excluded.payload_json,
                   retrieved_at=datetime('now'),import_run_id=excluded.import_run_id''',
                (record_id,source_id,external_key,entity_kind,digest,body,run_id))
    con.execute('''INSERT OR IGNORE INTO source_record_versions(source_record_id,content_sha256,payload_json)
                VALUES (?,?,?)''', (record_id,digest,body))
    return record_id


def begin_import(con, source_id, details=None):
    run_id = uid('import')
    con.execute('INSERT INTO import_runs(id,source_id,status,details_json) VALUES (?,?,?,?)',
                (run_id, source_id, 'RUNNING', js(details or {})))
    # Persist the RUNNING row before the data transaction. A failed import then
    # remains visible with an error count instead of disappearing on rollback.
    con.commit()
    return run_id


def finish_import(con, run_id, imported, skipped=0, errors=0, details=None):
    if details is None:
        con.execute('''UPDATE import_runs SET status=?, imported_count=?, skipped_count=?, error_count=?,
                      finished_at=datetime('now') WHERE id=?''',
                    ('COMPLETE' if errors == 0 else 'FAILED', imported, skipped, errors, run_id))
    else:
        con.execute('''UPDATE import_runs SET status=?, imported_count=?, skipped_count=?, error_count=?,
                      details_json=?, finished_at=datetime('now') WHERE id=?''',
                    ('COMPLETE' if errors == 0 else 'FAILED', imported, skipped, errors,
                     js(details), run_id))
    con.commit()


def slugify(raw):
    value = re.sub(r'[^a-z0-9_]+','_',raw.lower().strip().replace(' ','_')).strip('_')
    return re.sub(r'_+','_',value) or 'unnamed'


def parse_deepghs(text):
    """Read the 'Character Index' Markdown table in a DeepGHS pages/<series>.md file.

    Output is source tag vocabulary, NOT verified identity/outfit information.
    """
    series = None
    within = False
    for line in text.splitlines():
        if line.startswith('# ') and series is None:
            series = line[2:].strip()
        if line.strip().lower() == '## character index':
            within = True
            continue
        if not within:
            continue
        if line.startswith('## '):
            break
        if not line.startswith('|'):
            continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if len(cells) < 6:
            continue
        first = cells[0]
        if first.lower().startswith('character') or re.fullmatch(r':?-+:?',first.replace(' ','')):
            continue
        match = re.search(r'\[([^\]]+)\]\((https?://[^)]+)\)',first)
        if not match:
            continue
        char_tag = match.group(1).strip()
        if not char_tag:
            continue
        tags_cell = cells[-1]
        tags = [v.strip() for v in tags_cell.strip('`').split(',') if v.strip()]
        count = re.search(r'\d+', cells[-2])
        yield (series or 'unknown', char_tag, match.group(2), tags, int(count.group()) if count else None)


def import_deepghs(con, path: Path):
    seed(con)
    text = path.read_text(encoding='utf-8')
    file_sha = sha(path.read_bytes())
    run_id = begin_import(con, 'deepghs', {'file': path.name, 'sha256': file_sha,
                                           'parser': 'deepghs-character-index-v1'})
    imported = skipped = rows = 0
    try:
        for series, char_tag, url, tags, count in parse_deepghs(text):
            rows += 1
            series_slug = slugify(series)
            universe_id = f'universe:{series_slug}'
            con.execute('INSERT OR IGNORE INTO universes(id,slug,display_name) VALUES (?,?,?)',
                        (universe_id,series_slug,series.replace('_',' ')))
            unique_key = f'{series}/{char_tag}'
            source_record_id = track_source_record(con, 'deepghs', unique_key, 'character_index',
                         {'series':series,'tag':char_tag,'page_url':url,'core_tags':tags,
                          'post_count':count,'source_file_sha256':file_sha},run_id)
            char_id = f'character:deepghs:{sha(unique_key)[:18]}'
            char_slug = slugify(char_tag)
            was_existing = con.execute('SELECT 1 FROM characters WHERE id=?',(char_id,)).fetchone()
            # No inferred age/origin outfit, no overwriting the curated character profile.
            con.execute('''INSERT OR IGNORE INTO characters(id,universe_id,slug,display_name,age_status,identity_json)
              VALUES (?,?,?,?,?,?)''', (char_id,universe_id,char_slug,char_tag.replace('_',' '),'UNKNOWN','{}'))
            for tag in tags:
                # Resolve by (namespace,name): a tag may already have a hash-based id
                # from a CSV import, so do not assume the slug id was inserted.
                tag_id = f'tag:danbooru:{slugify(tag)}'
                con.execute('''INSERT INTO catalog_tags(id,namespace,name,original_name)
                  VALUES(?,?,?,?) ON CONFLICT(namespace,name) DO UPDATE SET
                  original_name=excluded.original_name''', (tag_id,'danbooru',tag,tag))
                actual = con.execute('SELECT id FROM catalog_tags WHERE namespace=? AND name=?',
                                     ('danbooru', tag)).fetchone()
                con.execute('''INSERT OR IGNORE INTO character_tags(character_id,tag_id,source_record_id,tag_role)
                  VALUES(?,?,?,?)''',(char_id,actual['id'],source_record_id,'CORE_CANDIDATE'))
            imported += int(not was_existing)
            skipped += int(bool(was_existing))
        finish_import(con,run_id,imported,skipped,details={
            'file': path.name, 'sha256': file_sha, 'rows_parsed': rows,
            'new_characters': imported, 'existing_characters': skipped,
            'note': 'core tags are CORE_CANDIDATE; no age/outfit inference'})
    except Exception as exc:
        con.rollback()
        finish_import(con, run_id, imported, skipped, errors=1,
                      details={'file': path.name, 'sha256': file_sha, 'error': str(exc)})
        raise
    return imported, skipped


def import_danbooru_tags(con, path: Path):
    seed(con)
    data = json.loads(path.read_text(encoding='utf-8'))
    tags = data if isinstance(data,list) else data.get('tags', data.get('data',[]))
    if not isinstance(tags,list):
        raise ValueError('JSON must be an array or {"tags":[...]}')
    run_id = begin_import(con,'danbooru')
    imported=skipped=0
    for tag in tags:
        name = tag.get('name')
        if not name:
            skipped+=1
            continue
        cat = tag.get('category')
        if cat is not None and cat not in (0,1,3,4,5):
            skipped+=1
            continue
        key = str(tag.get('id') or name)
        rec_id = track_source_record(con,'danbooru',f'tag/{key}','tag',tag,run_id)
        tag_id = f'tag:danbooru:{slugify(name)}'
        existing = con.execute('SELECT 1 FROM catalog_tags WHERE id=?',(tag_id,)).fetchone()
        con.execute('''INSERT INTO catalog_tags
              (id,namespace,name,original_name,category,post_count,deprecated,source_record_id)
              VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(namespace,name) DO UPDATE SET
              original_name=excluded.original_name, category=excluded.category,
              post_count=excluded.post_count,deprecated=excluded.deprecated,
              source_record_id=excluded.source_record_id''',
              (tag_id,'danbooru',name,name,cat,tag.get('post_count'),int(bool(tag.get('is_deprecated',False))),rec_id))
        imported += int(not existing)
        skipped += int(bool(existing))
    finish_import(con,run_id,imported,skipped)
    return imported,skipped


def wikidata_value(binding, field):
    v = binding.get(field)
    return (v.get('value') if isinstance(v,dict) else v) or None


def import_wikidata(con,path):
    seed(con)
    payload = json.loads(path.read_text(encoding='utf-8'))
    bindings = payload.get('results',{}).get('bindings',[])
    run_id = begin_import(con,'wikidata')
    imported=skipped=0
    for b in bindings:
        url = wikidata_value(b,'item') or wikidata_value(b,'character')
        label = wikidata_value(b,'itemLabel') or wikidata_value(b,'characterLabel')
        if not url or not label:
            skipped+=1
            continue
        qid = url.rsplit('/',1)[-1]
        if not re.fullmatch(r'Q\d+',qid):
            skipped+=1
            continue
        rec_id = track_source_record(con,'wikidata',qid,'fictional_character',b,run_id)
        # Do not auto-merge with a third-party catalog by name: identity collision risk.
        universe=None
        work_url = wikidata_value(b,'work')
        work_name = wikidata_value(b,'workLabel')
        if work_url and work_name:
            wq = work_url.rsplit('/',1)[-1]
            if re.fullmatch(r'Q\d+',wq):
                universe=f'universe:wikidata:{wq}'
                con.execute('INSERT OR IGNORE INTO universes(id,slug,display_name) VALUES(?,?,?)',
                  (universe,f'wd_{wq.lower()}',work_name))
        char_id=f'character:wikidata:{qid}'
        existing=con.execute('SELECT 1 FROM characters WHERE id=?',(char_id,)).fetchone()
        con.execute('''INSERT OR IGNORE INTO characters(id,universe_id,slug,display_name,identity_json)
          VALUES(?,?,?,?,?)''', (char_id,universe,qid.lower(),label,js({'wikidata_id':qid,'source_record_id':rec_id})))
        imported += int(not existing)
        skipped += int(bool(existing))
    finish_import(con,run_id,imported,skipped)
    return imported,skipped


def create_story(con,title,mode,raw_text,labels):
    story_id=uid('story')
    source_id=uid('source')
    con.execute('INSERT INTO stories(id,title,cast_mode) VALUES(?,?,?)',(story_id,title,mode))
    con.execute('''INSERT INTO story_sources(id,story_id,source_kind,raw_text,raw_labels_json,content_sha256)
       VALUES(?,?,?,?,?,?)''',
       (source_id,story_id,'user_input',raw_text,js(labels),sha(raw_text)))
    con.commit()
    return story_id


def add_role(con,story_id,role_key,description=''):
    if not con.execute('SELECT 1 FROM stories WHERE id=?',(story_id,)).fetchone():
        raise ValueError('Story not found')
    existing = con.execute('SELECT id,role_description FROM story_roles WHERE story_id=? AND role_key=?',
                           (story_id,role_key)).fetchone()
    if existing:
        if (existing['role_description'] or '') != (description or ''):
            raise ValueError('Role already exists with different description; review before updating')
        return existing['id']
    role_id=uid('role')
    with con:
        con.execute('INSERT INTO story_roles(id,story_id,role_key,role_description) VALUES(?,?,?,?)',
                    (role_id,story_id,role_key,description))
    return role_id


def bind_role(con,story_id,role_key,character_id,outfit_id=None):
    row=con.execute('''SELECT r.id, s.current_revision FROM story_roles r
       JOIN stories s ON s.id=r.story_id WHERE r.story_id=? AND r.role_key=?''',(story_id,role_key)).fetchone()
    if row is None:
        raise ValueError(f'Role {role_key} not found in story')
    if not con.execute('SELECT 1 FROM characters WHERE id=?',(character_id,)).fetchone():
        raise ValueError(f'Character {character_id} not found')
    if outfit_id:
        outfit=con.execute('SELECT character_id FROM outfits WHERE id=?',(outfit_id,)).fetchone()
        if outfit is None or outfit[0] not in (None,character_id):
            raise ValueError('Outfit does not belong to character or does not exist')
    # Same binding is idempotent: do not create a new revision when nothing changed.
    current = con.execute('''SELECT character_id,outfit_id FROM story_castings
                       WHERE story_role_id=? AND until_revision IS NULL''',(row['id'],)).fetchone()
    if current and current['character_id'] == character_id and current['outfit_id'] == outfit_id:
        return row['current_revision']
    # Casting revision advances the shared Story revision counter.
    newrev=row['current_revision']+1
    with con:
        con.execute('UPDATE story_castings SET until_revision=? WHERE story_role_id=? AND until_revision IS NULL',
                    (newrev-1,row['id']))
        con.execute('''INSERT INTO story_castings(id,story_role_id,character_id,outfit_id,from_revision)
         VALUES(?,?,?,?,?)''',(uid('casting'),row['id'],character_id,outfit_id,newrev))
        con.execute('UPDATE stories SET current_revision=?,updated_at=datetime(\'now\') WHERE id=?',
                    (newrev,story_id))
    return newrev


def compile_layout(con,layout_id):
    layout=con.execute('SELECT * FROM shot_layouts WHERE id=?',(layout_id,)).fetchone()
    if not layout:
        raise ValueError('Layout not found')
    width,height=layout['width'],layout['height']
    elements=con.execute('SELECT * FROM shot_layout_items WHERE layout_id=? ORDER BY item_order',(layout_id,)).fetchall()
    if not elements:
        raise ValueError('A MOSS layout must have at least one item')
    result={'summary':{'meta':json.loads(layout['meta_json']), 'canvas':layout['canvas'],
                       'caption':layout['summary_caption']},'items':[],
            'bbox_coord_space':'abs_centralized','bbox_format':'yxyx'}
    for item in elements:
        x1,y1,x2,y2=(item['x_min'],item['y_min'],item['x_max'],item['y_max'])
        if not (0<=x1<x2<=width and 0<=y1<y2<=height):
            raise ValueError(f'Invalid item bbox for {item["id"]}: out of canvas')
        converted=[y1-height//2,x1-width//2,y2-height//2,x2-width//2]
        obj={'label':item['label'],'caption':item['caption'],'bbox':converted}
        if item['label']=='text':
            obj['text']=item['text_content']
        result['items'].append(obj)
    body=js(result)
    digest=sha(body)
    con.execute('''INSERT OR IGNORE INTO layout_exports(id,layout_id,compiler_version,prompt_json,prompt_sha256)
                  VALUES(?,?,?,?,?)''',(uid('export'),layout_id,'n2m-layout-db-v1',body,digest))
    con.commit()
    return result,digest


def export_bundle(con, layout_id, out_dir: Path):
    """Write the V2 prompt artifact bundle; no renderer/DB dependency downstream."""
    layout = con.execute('SELECT * FROM shot_layouts WHERE id=?', (layout_id,)).fetchone()
    if not layout:
        raise ValueError('Layout not found')
    shot = con.execute('SELECT * FROM shots WHERE id=?', (layout['shot_id'],)).fetchone()
    beat = con.execute('SELECT * FROM beats WHERE id=?', (shot['beat_id'],)).fetchone() if shot else None
    act = con.execute('SELECT * FROM acts WHERE id=?', (beat['act_id'],)).fetchone() if beat else None
    prompt, digest = compile_layout(con, layout_id)
    export = con.execute('''SELECT id FROM layout_exports
                            WHERE layout_id=? AND prompt_sha256=? ORDER BY created_at DESC LIMIT 1''',
                         (layout_id, digest)).fetchone()
    qa = con.execute('''SELECT verdict,policy_ref,report_json,created_at FROM qa_reports
                        WHERE subject_kind='LAYOUT' AND subject_id=?
                        ORDER BY created_at DESC LIMIT 1''', (layout_id,)).fetchone()
    out_dir = out_dir.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = out_dir / 'layout.prompt.json'
    manifest_path = out_dir / 'prompt.manifest.json'
    fidelity_path = out_dir / 'fidelity_report.json'
    prompt_path.write_text(js(prompt), encoding='utf-8')
    manifest = {
        'export_id': export['id'] if export else None,
        'story_id': act['story_id'] if act else None,
        'shot_id': layout['shot_id'],
        'shot_key': shot['shot_key'] if shot else None,
        'shot_revision': shot['revision'] if shot else None,
        'layout_id': layout_id,
        'layout_revision': layout['revision'],
        'width': layout['width'],
        'height': layout['height'],
        'compiler_version': 'n2m-layout-db-v1',
        'prompt_sha256': digest,
        'prompt_file': 'layout.prompt.json',
        'fidelity_report_file': 'fidelity_report.json',
        'generated_at': datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n',
                             encoding='utf-8')
    if qa:
        fidelity = {'subject_kind': 'LAYOUT', 'subject_id': layout_id,
                    'verdict': qa['verdict'], 'policy_ref': qa['policy_ref'],
                    'report': json.loads(qa['report_json']),
                    'created_at': qa['created_at']}
    else:
        fidelity = {'subject_kind': 'LAYOUT', 'subject_id': layout_id,
                    'verdict': 'SKIP',
                    'reason': 'No pre-export layout QA recorded'}
    fidelity_path.write_text(json.dumps(fidelity, ensure_ascii=False, indent=2) + '\n',
                             encoding='utf-8')
    return {'out_dir': str(out_dir), 'prompt': str(prompt_path),
            'manifest': str(manifest_path), 'fidelity_report': str(fidelity_path),
            'prompt_sha256': digest}


def stats(con):
    names=['source_registry','source_records','source_record_versions','import_runs','universes','characters',
           'character_traits','outfits','outfit_parts','catalog_tags','character_tags',
           'catalog_assets','catalog_tag_relations','catalog_tag_taxonomy','catalog_entity_links',
           'catalog_captions','pose_references','pose_reference_views','layout_templates',
           'stories','story_roles','story_castings','acts','beats','story_events','shots',
           'shot_layouts','layout_exports','qa_reports']
    return {name:con.execute(f'SELECT count(*) FROM {name}').fetchone()[0] for name in names}


def stats_detailed(con):
    """Counts by namespace/kind plus the flat table counts used by earlier versions."""
    result = {'tables': stats(con)}
    result['tags_by_namespace'] = {
        row['namespace']: row['n'] for row in con.execute(
            'SELECT namespace,count(*) AS n FROM catalog_tags GROUP BY namespace ORDER BY namespace')}
    result['outfits_by_kind'] = {
        row['outfit_kind']: row['n'] for row in con.execute(
            'SELECT outfit_kind,count(*) AS n FROM outfits GROUP BY outfit_kind ORDER BY outfit_kind')}
    result['poses_by_source'] = {
        row['source_id']: row['n'] for row in con.execute(
            '''SELECT s.source_id,count(*) AS n FROM pose_references p
               JOIN source_records s ON s.id=p.source_record_id
               GROUP BY s.source_id ORDER BY s.source_id''')}
    result['assets_by_role'] = {
        row['asset_role']: row['n'] for row in con.execute(
            'SELECT asset_role,count(*) AS n FROM catalog_assets GROUP BY asset_role ORDER BY asset_role')}
    result['import_runs'] = [
        {'source_id': row['source_id'], 'status': row['status'],
         'imported': row['imported_count'], 'skipped': row['skipped_count'],
         'errors': row['error_count'], 'started_at': row['started_at']}
        for row in con.execute('''SELECT source_id,status,imported_count,skipped_count,error_count,started_at
                                  FROM import_runs ORDER BY started_at DESC LIMIT 15''')]
    return result


def search_catalog(con, kind, query, limit=20, namespace=None):
    """Simple, explicit LIKE search across catalog entities. No fuzzy auto-merge."""
    query = (query or '').strip()
    if not query:
        raise ValueError('Search query must not be empty')
    like = f'%{query}%'
    if kind == 'tag':
        sql = 'SELECT id,namespace,name,original_name,category,post_count FROM catalog_tags WHERE name LIKE ?'
        params = [like]
        if namespace:
            sql += ' AND namespace=?'
            params.append(namespace)
        sql += ' ORDER BY post_count DESC, name LIMIT ?'
        params.append(limit)
    elif kind == 'character':
        sql = '''SELECT c.id,c.display_name,c.slug,c.identity_review,
                        u.slug AS universe_slug,u.display_name AS universe
                 FROM characters c LEFT JOIN universes u ON u.id=c.universe_id
                 WHERE c.display_name LIKE ? OR c.slug LIKE ?
                 ORDER BY c.display_name LIMIT ?'''
        params = [like, like, limit]
    elif kind == 'universe':
        sql = '''SELECT id,slug,display_name FROM universes
                 WHERE display_name LIKE ? OR slug LIKE ? ORDER BY display_name LIMIT ?'''
        params = [like, like, limit]
    elif kind == 'pose':
        sql = '''SELECT p.id,p.caption_en,p.category,p.pose_code,p.source_url,
                        (SELECT v.view_name FROM pose_reference_views v
                         WHERE v.pose_reference_id=p.id LIMIT 1) AS view_name
                 FROM pose_references p
                 WHERE p.caption_en LIKE ? OR p.category LIKE ? OR p.pose_code LIKE ?
                 ORDER BY p.id LIMIT ?'''
        params = [like, like, like, limit]
    elif kind == 'outfit':
        sql = '''SELECT DISTINCT o.id,o.name,o.slug,o.outfit_kind,o.verification,o.character_id
                 FROM outfits o
                 LEFT JOIN catalog_captions c
                   ON c.entity_kind='outfit' AND c.entity_id=o.id
                 WHERE o.name LIKE ? OR o.slug LIKE ? OR c.text LIKE ?
                 ORDER BY o.name LIMIT ?'''
        params = [like, like, like, limit]
    elif kind == 'action':
        sql = '''SELECT id,category,code,label_en,label_vi,description_en,review
                 FROM vocabulary WHERE category='ACTION'
                   AND (code LIKE ? OR label_en LIKE ? OR description_en LIKE ?)
                 ORDER BY code LIMIT ?'''
        params = [like, like, like, limit]
    else:
        raise ValueError('kind must be one of: tag, character, universe, pose, outfit, action')
    return [dict(row) for row in con.execute(sql, params)]


def main():
    p=argparse.ArgumentParser(description='Novel2Moss DB - local-only, standard library SQLite starter')
    p.add_argument('--db',type=Path,default=DEFAULT_DB,help='SQLite path (default: data/novel2moss.db)')
    sub=p.add_subparsers(dest='action',required=True)
    for action in ('init','seed'):
        sub.add_parser(action)
    a=sub.add_parser('stats');a.add_argument('--detailed',action='store_true')
    a=sub.add_parser('import-deepghs-md');a.add_argument('file',type=Path)
    a=sub.add_parser('import-danbooru-json');a.add_argument('file',type=Path)
    a=sub.add_parser('import-wikidata-json');a.add_argument('file',type=Path)
    a=sub.add_parser('import-tags-csv');a.add_argument('file',type=Path);a.add_argument('--namespace',required=True,choices=('danbooru','e621'));a.add_argument('--limit',type=int);a.add_argument('--no-aliases',action='store_true');a.add_argument('--source-revision');a.add_argument('--dry-run',action='store_true');a.add_argument('--from-character-core-tags',action='store_true')
    a=sub.add_parser('import-tag-relations-json');a.add_argument('file',type=Path);a.add_argument('--namespace',required=True,choices=('danbooru','e621'));a.add_argument('--kind',required=True,choices=('alias','implication'));a.add_argument('--source-revision');a.add_argument('--dry-run',action='store_true')
    a=sub.add_parser('import-pose-gallery-json');a.add_argument('file',type=Path);a.add_argument('--limit',type=int);a.add_argument('--source-revision');a.add_argument('--dry-run',action='store_true')
    a=sub.add_parser('import-costume-gallery-json');a.add_argument('file',type=Path);a.add_argument('--source-id',default='ai_pose_gallery',choices=('ai_pose_gallery','charadb'));a.add_argument('--limit',type=int);a.add_argument('--source-revision');a.add_argument('--dry-run',action='store_true')
    a=sub.add_parser('create-story');a.add_argument('--title',required=True);a.add_argument('--mode',choices=('BLIND','NON_BLIND'),required=True);a.add_argument('--text-file',type=Path,required=True);a.add_argument('--label',action='append',default=[])
    a=sub.add_parser('add-role');a.add_argument('--story-id',required=True);a.add_argument('--key',required=True);a.add_argument('--description',default='')
    a=sub.add_parser('bind-role');a.add_argument('--story-id',required=True);a.add_argument('--key',required=True);a.add_argument('--character-id',required=True);a.add_argument('--outfit-id')
    a=sub.add_parser('export-layout');a.add_argument('--layout-id',required=True);a.add_argument('--out',type=Path)
    a=sub.add_parser('export-bundle');a.add_argument('--layout-id',required=True);a.add_argument('--out-dir',type=Path,required=True)
    a=sub.add_parser('search-characters');a.add_argument('query');a.add_argument('--limit',type=int,default=10)
    a=sub.add_parser('search-catalog');a.add_argument('kind',choices=('tag','character','universe','pose','outfit','action'));a.add_argument('query');a.add_argument('--namespace',choices=('danbooru','e621'));a.add_argument('--limit',type=int,default=20)
    args=p.parse_args()
    con=connect(args.db)
    try:
        apply_migrations(con)
        if args.action=='init':print(f'Database initialized: {args.db}')
        elif args.action=='seed': seed(con)
        elif args.action=='stats':
            print(json.dumps(stats_detailed(con) if args.detailed else stats(con),indent=2,ensure_ascii=False))
        elif args.action=='import-deepghs-md': print('New, existing:',*import_deepghs(con,args.file))
        elif args.action=='import-danbooru-json': print('New, existing/skipped:',*import_danbooru_tags(con,args.file))
        elif args.action=='import-wikidata-json': print('New, existing/skipped:',*import_wikidata(con,args.file))
        elif args.action=='import-tags-csv':
            from catalog_imports import import_tags_csv
            result=import_tags_csv(con,args.file,args.namespace,limit=args.limit,
                                   with_aliases=not args.no_aliases,
                                   source_revision=args.source_revision,dry_run=args.dry_run,
                                   from_character_core_tags=args.from_character_core_tags)
            print(json.dumps(result,indent=2,ensure_ascii=False))
        elif args.action=='import-tag-relations-json':
            from catalog_imports import import_tag_relations_json
            result=import_tag_relations_json(con,args.file,args.namespace,args.kind,
                                             source_revision=args.source_revision,dry_run=args.dry_run)
            print(json.dumps(result,indent=2,ensure_ascii=False))
        elif args.action=='import-pose-gallery-json':
            from catalog_imports import import_pose_gallery
            result=import_pose_gallery(con,args.file,limit=args.limit,
                                       source_revision=args.source_revision,dry_run=args.dry_run)
            print(json.dumps(result,indent=2,ensure_ascii=False))
        elif args.action=='import-costume-gallery-json':
            from catalog_imports import import_generic_outfits
            result=import_generic_outfits(con,args.file,source_id=args.source_id,limit=args.limit,
                                          source_revision=args.source_revision,dry_run=args.dry_run)
            print(json.dumps(result,indent=2,ensure_ascii=False))
        elif args.action=='search-catalog':
            print(json.dumps(search_catalog(con,args.kind,args.query,args.limit,args.namespace),
                             indent=2,ensure_ascii=False))
        elif args.action=='create-story':
            print(create_story(con,args.title,args.mode,args.text_file.read_text(encoding='utf-8'),args.label))
        elif args.action=='add-role':print(add_role(con,args.story_id,args.key,args.description))
        elif args.action=='bind-role':print('New story revision:',bind_role(con,args.story_id,args.key,args.character_id,args.outfit_id))
        elif args.action=='export-layout':
            prompt,digest=compile_layout(con,args.layout_id)
            if args.out:
                args.out.parent.mkdir(parents=True,exist_ok=True)
                args.out.write_text(json.dumps(prompt,ensure_ascii=False,indent=2),encoding='utf-8')
                print(f'Written: {args.out}, sha256: {digest}')
            else:print(json.dumps(prompt,indent=2,ensure_ascii=False))
        elif args.action=='export-bundle':
            print(json.dumps(export_bundle(con,args.layout_id,args.out_dir),
                             indent=2,ensure_ascii=False))
        elif args.action=='search-characters':
            for row in con.execute('''SELECT c.id,c.display_name,c.slug,u.display_name AS universe
              FROM character_search f JOIN characters c ON c.rowid=f.rowid
              LEFT JOIN universes u ON u.id=c.universe_id
              WHERE character_search MATCH ? LIMIT ?''',(args.query,args.limit)):
                print(dict(row))
    finally:
        con.close()


if __name__=='__main__':
    try:main()
    except (ValueError,sqlite3.Error,FileNotFoundError) as exc:
        print(f'ERROR: {exc}',file=sys.stderr)
        sys.exit(1)
