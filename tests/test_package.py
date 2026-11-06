import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


class PackageTests(unittest.TestCase):
    def test_all_skill_metadata(self):
        skills=list((ROOT/'skills').glob('*/SKILL.md'))
        self.assertEqual(len(skills),12)
        for file in skills:
            with self.subTest(file=file):
                text=file.read_text(encoding='utf-8')
                self.assertTrue(text.startswith('---\nname: '))
                self.assertIn(f'name: {file.parent.name}',text)
                self.assertIn('\ndescription: ',text)

    def test_links_exist(self):
        for skill in (ROOT/'skills').glob('*/SKILL.md'):
            text=skill.read_text(encoding='utf-8')
            import re
            for path in re.findall(r'(?:docs/novel2moss|examples|tools/novel2moss)/[A-Za-z0-9_.-]+',text):
                self.assertTrue((ROOT/path).exists(),f'missing {path} from {skill}')

    def test_standalone_boundary(self):
        boundary = (ROOT/'docs/novel2moss/PROJECT_BOUNDARIES.md')
        self.assertTrue(boundary.exists())
        self.assertIn('own product and codebase', boundary.read_text(encoding='utf-8'))
        # A source-project dependency must not be described as a runtime requirement.
        for file in list((ROOT/'skills').glob('*/SKILL.md')) + [ROOT/'README.md']:
            self.assertNotIn('novel2anima', file.read_text(encoding='utf-8').lower(), str(file))

    def test_installer_claude(self):
        with tempfile.TemporaryDirectory() as tmp:
            result=subprocess.run([sys.executable,str(ROOT/'install.py'),'--target',tmp,'--mode','claude'],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertTrue((Path(tmp)/'.claude/skills/novel2moss-layout-planner/SKILL.md').exists())
            self.assertTrue((Path(tmp)/'docs/novel2moss/CONTENT_FIDELITY.md').exists())
            self.assertTrue((Path(tmp)/'docs/novel2moss/PROJECT_BOUNDARIES.md').exists())
            self.assertTrue((Path(tmp)/'docs/novel2moss/CONTENT_POLICY.md').exists())
            self.assertTrue((Path(tmp)/'tools/novel2moss/compile_layout.py').exists())
            self.assertTrue((Path(tmp)/'database/collect/source_manifest.json').exists())
            self.assertFalse((Path(tmp)/'database/imports').exists())
            self.assertFalse((Path(tmp)/'database/data/novel2moss.db').exists())
            again=subprocess.run([sys.executable,str(ROOT/'install.py'),'--target',tmp,'--mode','claude'],capture_output=True,text=True)
            self.assertNotEqual(again.returncode,0)


if __name__ == '__main__':
    unittest.main()
