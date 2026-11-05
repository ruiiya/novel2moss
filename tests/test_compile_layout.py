import importlib.util
import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("compiler", ROOT / "tools/novel2moss/compile_layout.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

sys.path.insert(0, str(ROOT / 'database' / 'src'))
from n2m_db import TEMPLATES


class LayoutCompilerTests(unittest.TestCase):
    def draft(self, bbox=None, label="character"):
        return {
            "width": 1024, "height": 1024, "bbox_coord_space": "abs", "bbox_format": "xyxy",
            "summary": {"meta": ["anime illustration"], "canvas": "single", "caption": "A scene."},
            "items": [{"label": label, "caption": "A person or object.", "bbox": bbox or [128, 64, 512, 960]}],
        }

    def test_exact_center_conversion(self):
        result = module.compile_layout(self.draft())
        self.assertEqual(result["items"][0]["bbox"], [-448, -384, 448, 0])
        self.assertEqual(result["bbox_coord_space"], "abs_centralized")
        self.assertEqual(result["bbox_format"], "yxyx")
        self.assertEqual(set(result), {"summary", "items", "bbox_coord_space", "bbox_format"})

    def test_non_square(self):
        data = self.draft([176, 224, 800, 864]); data["width"] = 1536
        self.assertEqual(module.compile_layout(data)["items"][0]["bbox"], [-288, -592, 352, 32])

    def test_fractional_encloses(self):
        self.assertEqual(module.compile_layout(self.draft([128.8, 64.7, 512.2, 960.1]))["items"][0]["bbox"], [-448, -384, 449, 1])

    def test_invalid_bounds(self):
        for bbox in ([-1, 0, 200, 100], [200, 100, 200, 300], [0, 0, 1025, 100], [1, math.inf, 9, 50]):
            with self.subTest(bbox=bbox), self.assertRaises(module.LayoutError):
                module.compile_layout(self.draft(bbox))

    def test_invalid_extra_fields(self):
        data = self.draft(); data["shot_id"] = "must-not-leak"
        with self.assertRaises(module.LayoutError):
            module.compile_layout(data)

    def test_text_requires_literal(self):
        with self.assertRaises(module.LayoutError):
            module.compile_layout(self.draft(label="text"))
        data = self.draft(label="text")
        data["items"][0]["text"] = "Xin chào\nWorld"
        result = module.compile_layout(data)
        self.assertEqual(result["items"][0]["text"], "Xin chào\nWorld")

    def test_invalid_resolution(self):
        data = self.draft(); data["width"] = 1025
        with self.assertRaises(module.LayoutError):
            module.compile_layout(data)

    def test_invalid_coord_system(self):
        data = self.draft(); data["bbox_coord_space"] = "abs_centralized"
        with self.assertRaises(module.LayoutError):
            module.compile_layout(data)

    def test_duplicate_key_rejected_cli(self):
        with tempfile.TemporaryDirectory() as temp:
            src, dst = Path(temp)/"source.json", Path(temp)/"prompt.json"
            src.write_text('{"width":1024,"width":1024}',encoding='utf-8')
            result = subprocess.run([sys.executable, str(ROOT/'tools/novel2moss/compile_layout.py'), str(src), '--output',str(dst)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn('Duplicate JSON key',result.stderr)
            self.assertFalse(dst.exists())

    def test_exact_example_and_deterministic(self):
        source = json.loads((ROOT/"examples/layout_draft.example.json").read_text(encoding="utf-8"))
        expected = json.loads((ROOT/"examples/layout_prompt.example.json").read_text(encoding="utf-8"))
        self.assertEqual(module.compile_layout(source), expected)
        self.assertEqual(module.compile_layout(source), module.compile_layout(source))

    def test_curated_templates_cover_one_two_and_non_square(self):
        counts = set()
        non_square = False
        for name, participant_count, draft in TEMPLATES:
            with self.subTest(template=name):
                result = module.compile_layout(draft)
                self.assertEqual(len(result['items']), participant_count)
                counts.add(participant_count)
                non_square = non_square or draft['width'] != draft['height']
                self.assertEqual(set(result), {'summary', 'items', 'bbox_coord_space', 'bbox_format'})
                self.assertNotIn('width', result)
                self.assertNotIn('height', result)
                self.assertNotIn('role_key', str(result))
                for item in result['items']:
                    y1, x1, y2, x2 = item['bbox']
                    self.assertLess(y1, y2)
                    self.assertLess(x1, x2)
                    self.assertGreaterEqual(x1, -(draft['width'] // 2))
                    self.assertLessEqual(x2, draft['width'] // 2)
                    self.assertGreaterEqual(y1, -(draft['height'] // 2))
                    self.assertLessEqual(y2, draft['height'] // 2)
        self.assertEqual(counts, {1, 2})
        self.assertTrue(non_square)


if __name__ == '__main__':
    unittest.main()
