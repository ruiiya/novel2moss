import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("flattener", ROOT / "tools/novel2moss/flatten_layout.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def layout(items, summary="Single continuous anime photograph, one scene."):
    return {"summary": {"caption": summary}, "items": items,
            "bbox_coord_space": "abs_centralized", "bbox_format": "yxyx"}


class FlattenTests(unittest.TestCase):
    def test_core_filters(self):
        prose, report = module.flatten(layout([
            {"label": "object", "caption": "bright classroom, evenly lit", "bbox": [-512, -512, 512, 512]},
            {"label": "character", "bbox": [-400, -400, 0, 0],
             "caption": "Rias, an adult woman, tight navy blazer school uniform, SET_A uniform, "
                        "seated, smiling, explicit, seated"},
            {"label": "character", "bbox": [0, 0, 400, 400],
             "caption": "Akeno, an adult woman, black hair, standing behind her, smiling"},
        ], "Bright photograph. No panels, no text, no watermark. Rias is school uniform."))
        self.assertEqual(report["status"], "PASS")
        self.assertIn("Rias", prose)
        self.assertIn("Akeno", prose)
        self.assertIn("wearing", prose)
        for bad in ("No panels", "no watermark", "explicit", "SET_A", "[-400"):
            self.assertNotIn(bad, prose)
        self.assertNotIn("uniform uniform", prose)

    def test_text_item_verbatim(self):
        prose, report = module.flatten(layout([
            {"label": "text", "text": "Xin chào\nWorld", "bbox": [0, 0, 100, 100],
             "caption": "bold white lettering"}], "A poster."))
        self.assertIn('Xin chào\nWorld', prose)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["text_items"], ["Xin chào\nWorld"])

    def test_no_character_needs_review(self):
        _, report = module.flatten(layout([{"label": "object", "caption": "a room", "bbox": [0, 0, 1, 1]}]))
        self.assertEqual(report["status"], "NEEDS_REVIEW")
        self.assertIn("NO_CHARACTER_ITEM", report["issues"])

    def test_deterministic_and_cli(self):
        data = layout([{"label": "character", "caption": "Rias, adult woman, seated", "bbox": [0, 0, 1, 1]}])
        self.assertEqual(module.flatten(json.loads(json.dumps(data))), module.flatten(data))
        with tempfile.TemporaryDirectory() as temp:
            src, out, side = Path(temp)/"l.json", Path(temp)/"n.txt", Path(temp)/"n.json"
            src.write_text(json.dumps(data), encoding="utf-8")
            result = subprocess.run([sys.executable, str(ROOT/"tools/novel2moss/flatten_layout.py"),
                                     str(src), "--output", str(out), "--sidecar", str(side)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(out.read_text(encoding="utf-8").startswith("Single continuous"))
            self.assertEqual(len(json.loads(side.read_text(encoding="utf-8"))["natural_prompt_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
