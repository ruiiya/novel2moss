import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'database'/'src'))
from n2m_db import (connect,apply_migrations,seed,create_story,add_role,bind_role,
                    compile_layout,import_danbooru_tags,export_bundle)
from n2m_workflow import save_plan,add_act,add_beat,add_event,save_shot,save_continuity,save_layout,save_qa


class DatabaseWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=Path(self.tmp.name)/'sample.db'
        self.con=connect(self.db)
        apply_migrations(self.con)

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def new_story(self,mode):
        story=create_story(self.con,'MOSS sample',mode,'A person offers another a notebook.',['original'])
        left=add_role(self.con,story,'LEAD')
        right=add_role(self.con,story,'PARTNER_A')
        return story,left,right

    def add_sample_shot(self,story):
        plan={'story_id':story,'acts':[{'title':'Beginning'}]}
        self.assertEqual(save_plan(self.con,story,plan,expected_revision=1),1)
        act=add_act(self.con,story,1,'Beginning','A simple interaction')
        beat=add_beat(self.con,act,1,'Meet')
        event={'actor_role_key':'LEAD','target_role_key':'PARTNER_A',
               'action':'handing_object','reaction':'smiles','raw_labels':['original']}
        event_id=add_event(self.con,beat,1,event)
        shot={'participants':[{'role_key':'LEAD','spec':{'pose':'standing'}},
                              {'role_key':'PARTNER_A','spec':{'pose':'sitting'}}],
              'interactions':[{'actor_role_key':'LEAD','target_role_key':'PARTNER_A',
                               'action_text':'hands over a notebook'}]}
        shot_id,rev=save_shot(self.con,beat,'SHOT_001',shot,event_id)
        self.assertEqual(rev,1)
        self.assertEqual(add_event(self.con,beat,1,event),event_id)
        self.assertEqual(save_shot(self.con,beat,'SHOT_001',shot,event_id),(shot_id,1))
        return shot_id,shot,beat,event_id

    def add_sample_layout(self,shot_id):
        draft={'width':1024,'height':1024,'bbox_coord_space':'abs','bbox_format':'xyxy',
               'summary':{'meta':['anime illustration'],'canvas':'single',
                          'caption':'One adult person hands another person a notebook.'},
               'items':[{'label':'character','role_key':'LEAD',
                         'caption':'Person on the left holding a notebook.',
                         'bbox':[100,100,550,950]},
                        {'label':'character','role_key':'PARTNER_A',
                         'caption':'Seated person on right receiving a notebook.',
                         'bbox':[490,200,960,970]}]}
        layout_id,revision=save_layout(self.con,shot_id,draft)
        self.assertEqual(revision,1)
        self.assertEqual(save_layout(self.con,shot_id,draft),(layout_id,1))
        return layout_id,draft

    def test_migrations_idempotent_and_integrity(self):
        apply_migrations(self.con)
        self.assertEqual([r[0] for r in self.con.execute('SELECT version FROM schema_migrations ORDER BY version')],
                         ['001_init','002_integrity','003_history_guards','004_catalog_enrichment','005_db_boundary','006_qa_history_guards'])
        self.assertEqual(self.con.execute('PRAGMA integrity_check').fetchone()[0],'ok')
        self.assertEqual(list(self.con.execute('PRAGMA foreign_key_check')),[])
        self.assertEqual(self.con.execute('PRAGMA foreign_keys').fetchone()[0],1)

    def test_db_boundary_backs_up_legacy_render_state(self):
        path=Path(self.tmp.name)/'legacy.db'
        legacy=connect(path)
        legacy.execute('PRAGMA foreign_keys=OFF')
        for file in sorted((ROOT/'database'/'migrations').glob('00[1-4]_*.sql')):
            legacy.executescript(file.read_text(encoding='utf-8'))
        legacy.execute('PRAGMA foreign_keys=OFF')
        legacy.execute("INSERT INTO render_jobs(id,layout_export_id,backend) VALUES('job1','missing','legacy')")
        legacy.execute("INSERT INTO render_assets(id,render_job_id,asset_kind,file_path) VALUES('asset1','job1','image','x.png')")
        legacy.execute("""INSERT INTO qa_reports(id,subject_kind,subject_id,verdict,report_json)
                          VALUES('qa-render','RENDER','job1','PASS','{}')""")
        legacy.execute("""INSERT INTO qa_reports(id,subject_kind,subject_id,verdict,report_json)
                          VALUES('qa-layout','LAYOUT','layout1','PASS','{}')""")
        legacy.commit()
        legacy.close()
        check=connect(path)
        apply_migrations(check)
        backups=list((path.parent/'backups').glob('render-export-*.json'))
        self.assertEqual(len(backups),1)
        payload=json.loads(backups[0].read_text(encoding='utf-8'))
        self.assertEqual(payload['render_jobs'][0]['id'],'job1')
        self.assertEqual(payload['render_assets'][0]['id'],'asset1')
        self.assertEqual(payload['render_qa_reports'][0]['id'],'qa-render')
        self.assertEqual(check.execute(
            "SELECT count(*) FROM sqlite_master WHERE type='table' AND name IN ('render_jobs','render_assets')"
        ).fetchone()[0],0)
        self.assertEqual(check.execute("SELECT count(*) FROM qa_reports WHERE subject_kind='RENDER'").fetchone()[0],0)
        self.assertEqual(check.execute("SELECT count(*) FROM qa_reports WHERE id='qa-layout'").fetchone()[0],1)
        check.close()

    def test_role_and_casting_idempotent(self):
        story,lead,_=self.new_story('BLIND')
        self.assertEqual(add_role(self.con,story,'LEAD'),lead)
        with self.assertRaises(ValueError):
            add_role(self.con,story,'LEAD','different description')
        self.con.execute('INSERT INTO characters(id,slug,display_name) VALUES (?,?,?)',
                         ('char:demo','demo','Demo'))
        self.con.commit()
        self.assertEqual(bind_role(self.con,story,'LEAD','char:demo'),2)
        self.assertEqual(bind_role(self.con,story,'LEAD','char:demo'),2)
        self.assertEqual(self.con.execute('SELECT count(*) FROM story_castings').fetchone()[0],1)

    def test_blind_to_cast_then_export_keeps_story_roles(self):
        story,lead,partner=self.new_story('BLIND')
        shot_id,shot,beat,event_id=self.add_sample_shot(story)
        self.assertEqual(self.con.execute('SELECT count(*) FROM story_castings').fetchone()[0],0)
        states={'snapshots':[{'role_key':'LEAD','before':{'holding':'notebook'},
                              'delta':{'transfers':'notebook'},'after':{'holding':None}}]}
        self.assertEqual(save_continuity(self.con,shot_id,states),save_continuity(self.con,shot_id,states))
        layout_id,draft=self.add_sample_layout(shot_id)
        json_prompt,digest=compile_layout(self.con,layout_id)
        self.assertEqual(json_prompt['bbox_coord_space'],'abs_centralized')
        self.assertEqual(json_prompt['bbox_format'],'yxyx')
        self.assertEqual(json_prompt['items'][0]['bbox'],[-412,-412,438,38])
        self.assertNotIn('role_key',str(json_prompt))
        self.assertEqual(compile_layout(self.con,layout_id)[1],digest)
        self.assertEqual(self.con.execute('SELECT count(*) FROM layout_exports').fetchone()[0],1)
        self.con.execute('''INSERT INTO characters(id,slug,display_name) VALUES('char:demo','demo','Demo')''')
        self.con.commit()
        self.assertEqual(bind_role(self.con,story,'LEAD','char:demo'),2)
        event=self.con.execute('SELECT actor_role_id,target_role_id FROM story_events WHERE id=?',(event_id,)).fetchone()
        self.assertEqual(tuple(event),(lead,partner))
        self.assertEqual(self.con.execute('SELECT count(*) FROM shots').fetchone()[0],1)
        self.assertEqual(self.con.execute('SELECT count(*) FROM layout_exports').fetchone()[0],1)
        self.assertEqual(self.con.execute('SELECT count(*) FROM story_castings').fetchone()[0],1)
        qa=save_qa(self.con,'LAYOUT',layout_id,'PASS',{'check':'structure'},'N2M-CONTENT-POLICY:1.3.0')
        self.assertEqual(qa,save_qa(self.con,'LAYOUT',layout_id,'PASS',{'check':'structure'},'N2M-CONTENT-POLICY:1.3.0'))
        # V2 boundary: renderer state is not part of the Novel2Moss database.
        self.assertEqual(self.con.execute(
            "SELECT count(*) FROM sqlite_master WHERE type='table' AND name IN ('render_jobs','render_assets')"
        ).fetchone()[0],0)
        with self.assertRaises(KeyError):
            save_qa(self.con,'RENDER','not-a-db-subject','PASS',{'check':'image'})

    def test_export_bundle_is_file_only(self):
        story,_,_=self.new_story('BLIND')
        shot_id,_,_,_=self.add_sample_shot(story)
        layout_id,_=self.add_sample_layout(shot_id)
        save_qa(self.con,'LAYOUT',layout_id,'PASS',{'check':'structure'},'N2M-CONTENT-POLICY:1.3.0')
        out=Path(self.tmp.name)/'exports'
        result=export_bundle(self.con,layout_id,out)
        self.assertTrue((out/'layout.prompt.json').exists())
        self.assertTrue((out/'prompt.manifest.json').exists())
        self.assertTrue((out/'fidelity_report.json').exists())
        prompt=json.loads((out/'layout.prompt.json').read_text(encoding='utf-8'))
        self.assertEqual(set(prompt),{'summary','items','bbox_coord_space','bbox_format'})
        self.assertNotIn('role_key',str(prompt))
        self.assertNotIn('width',prompt)
        manifest=json.loads((out/'prompt.manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['story_id'],story)
        self.assertEqual(manifest['shot_id'],shot_id)
        self.assertEqual(manifest['layout_id'],layout_id)
        self.assertEqual(manifest['prompt_sha256'],result['prompt_sha256'])
        fidelity=json.loads((out/'fidelity_report.json').read_text(encoding='utf-8'))
        self.assertEqual(fidelity['verdict'],'PASS')

    def test_nonblind_casting_before_shot(self):
        story,lead,partner=self.new_story('NON_BLIND')
        self.con.execute('INSERT INTO characters(id,slug,display_name) VALUES (?,?,?)',('char:1','one','One'))
        self.con.commit()
        self.assertEqual(bind_role(self.con,story,'LEAD','char:1'),2)
        shot_id,_,_,_=self.add_sample_shot_after_cast(story)
        self.assertEqual(self.con.execute('SELECT count(*) FROM shot_participants WHERE shot_id=?',(shot_id,)).fetchone()[0],2)

    def add_sample_shot_after_cast(self,story):
        # Sau casting, expected plan revision là 2.
        rev=save_plan(self.con,story,{'title':'A story'},expected_revision=2)
        self.assertEqual(rev,2)
        act=add_act(self.con,story,1,'Beginning')
        beat=add_beat(self.con,act,1,'First beat')
        e=add_event(self.con,beat,1,{'actor_role_key':'LEAD','target_role_key':'PARTNER_A', 'action':'waving'})
        spec={'participants':[{'role_key':'LEAD'},{'role_key':'PARTNER_A'}],
              'interactions':[{'actor_role_key':'LEAD','target_role_key':'PARTNER_A','action_text':'waves'}]}
        shot,_=save_shot(self.con,beat,'S1',spec,e)
        return shot,spec,beat,e

    def test_cross_story_fk_and_atomicity(self):
        story,lead,_=self.new_story('BLIND')
        other_story,_,_=self.new_story('NON_BLIND')
        act=add_act(self.con,story,1,'Act')
        beat=add_beat(self.con,act,1,'Beat')
        with self.assertRaises(sqlite3.IntegrityError):
            self.con.execute('INSERT INTO story_events(id,beat_id,event_order,actor_role_id,action) VALUES(?,?,?,?,?)',
                             ('bad',beat,1,self.con.execute('SELECT id FROM story_roles WHERE story_id=? LIMIT 1',(other_story,)).fetchone()[0],'test'))
        self.con.rollback()
        with self.assertRaises(ValueError):
            save_shot(self.con,beat,'S1',{'participants':[{'role_key':'LEAD'}],
                        'interactions':[{'actor_role_key':'LEAD','target_role_key':'PARTNER_A','action_text':'waves'}]})
        self.assertEqual(self.con.execute('SELECT count(*) FROM shots').fetchone()[0],0)

    def test_history_guards(self):
        story,_,_=self.new_story('BLIND')
        shot,_,beat,_=self.add_sample_shot(story)
        layout,_=self.add_sample_layout(shot)
        compile_layout(self.con,layout)
        qa=save_qa(self.con,'LAYOUT',layout,'PASS',{'check':'history'})
        for sql,params in [
            ('UPDATE story_sources SET raw_text=? WHERE story_id=?',('new',story)),
            ('DELETE FROM shots WHERE id=?',(shot,)),
            ('UPDATE shot_layout_items SET x_min=0 WHERE layout_id=?',(layout,)),
            ('DELETE FROM layout_exports WHERE layout_id=?',(layout,)),
            ('UPDATE qa_reports SET verdict=? WHERE id=?',('WARN',qa)),
            ('DELETE FROM qa_reports WHERE id=?',(qa,)),
        ]:
            with self.assertRaises(sqlite3.IntegrityError):self.con.execute(sql,params)
            self.con.rollback()

    def test_plan_revision_conflict_and_shot_revision(self):
        story,_,_=self.new_story('BLIND')
        shot,content,beat,event=self.add_sample_shot(story)
        with self.assertRaises(ValueError):save_plan(self.con,story,{'new':True},expected_revision=9)
        content2={**content,'camera':'close-up'}
        new_shot,revision=save_shot(self.con,beat,'SHOT_001',content2,event)
        self.assertEqual(revision,2)
        self.assertEqual(self.con.execute('SELECT supersedes_shot_id FROM shots WHERE id=?',(new_shot,)).fetchone()[0],shot)

    def test_catalog_import_idempotent_and_source_versions(self):
        seed(self.con)
        fixture=Path(self.tmp.name)/'tags.json'
        fixture.write_text(json.dumps([{'id':100,'name':'sitting','category':0,'post_count':10}]),encoding='utf-8')
        self.assertEqual(import_danbooru_tags(self.con,fixture),(1,0))
        self.assertEqual(import_danbooru_tags(self.con,fixture),(0,1))
        new=[{'id':100,'name':'sitting','category':0,'post_count':30}]
        fixture.write_text(json.dumps(new),encoding='utf-8')
        self.assertEqual(import_danbooru_tags(self.con,fixture),(0,1))
        self.assertEqual(self.con.execute("SELECT count(*) FROM source_record_versions").fetchone()[0],2)
        self.assertEqual(self.con.execute("SELECT post_count FROM catalog_tags WHERE name='sitting'").fetchone()[0],30)


if __name__=='__main__':unittest.main()
