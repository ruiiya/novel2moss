#!/usr/bin/env python3
"""Compile a top-left pixel xyxy Layout draft to official MOSS centered yxyx JSON.

Stdlib only; no runtime, model or service calls. Refuses unknown fields and bad geometry.
"""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path


class LayoutError(ValueError):
    pass


def _unique_pairs(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise LayoutError(f"Duplicate JSON key: {key}")
        obj[key] = value
    return obj


def _object(obj, path, allowed, required):
    if not isinstance(obj, dict):
        raise LayoutError(f"{path}: expected object")
    missing = set(required) - set(obj)
    extra = set(obj) - set(allowed)
    if missing:
        raise LayoutError(f"{path}: missing {sorted(missing)}")
    if extra:
        raise LayoutError(f"{path}: unknown fields {sorted(extra)}")


def _nonempty(s, name):
    if not isinstance(s, str) or not s.strip():
        raise LayoutError(f"{name}: must be a non-empty string")


def _strings(xs, name):
    if not isinstance(xs, list) or not all(isinstance(x, str) and x.strip() for x in xs):
        raise LayoutError(f"{name}: must be an array of non-empty strings")


def compile_layout(draft):
    _object(draft, "draft", {"width", "height", "bbox_coord_space", "bbox_format", "summary", "items"}, {"width", "height", "bbox_coord_space", "bbox_format", "summary", "items"})
    width, height = draft["width"], draft["height"]
    for k, v in (("width", width), ("height", height)):
        if type(v) is not int or v <= 0 or v % 16:
            raise LayoutError(f"{k}: must be a positive integer multiple of 16")
    if draft["bbox_coord_space"] != "abs" or draft["bbox_format"] != "xyxy":
        raise LayoutError("Draft coordinates must be abs/xyxy (top-left pixel coordinates)")

    summary = draft["summary"]
    _object(summary, "summary", {"caption", "meta", "canvas"}, {"caption"})
    _nonempty(summary["caption"], "summary.caption")
    result_summary = {}
    if "meta" in summary:
        _strings(summary["meta"], "summary.meta")
        result_summary["meta"] = summary["meta"]
    if "canvas" in summary:
        if summary["canvas"] not in {"single", "multi_panel", "collage"}:
            raise LayoutError("summary.canvas: invalid value")
        result_summary["canvas"] = summary["canvas"]
    result_summary["caption"] = summary["caption"]

    items = draft["items"]
    if not isinstance(items, list) or not items:
        raise LayoutError("items: expected nonempty array")
    result_items = []
    for i, item in enumerate(items):
        path = f"items[{i}]"
        _object(item, path, {"label", "caption", "text", "bbox"}, {"label", "caption", "bbox"})
        if item["label"] not in {"character", "object", "text"}:
            raise LayoutError(f"{path}.label: must be character/object/text")
        _nonempty(item["caption"], f"{path}.caption")
        if item["label"] == "text":
            if "text" not in item:
                raise LayoutError(f"{path}.text: required for text item")
            _nonempty(item["text"], f"{path}.text")
        elif "text" in item:
            raise LayoutError(f"{path}.text: only permitted on text item")
        bbox = item["bbox"]
        if not isinstance(bbox, list) or len(bbox) != 4:
            raise LayoutError(f"{path}.bbox: expected four coordinates")
        if any(type(n) not in (int, float) or not math.isfinite(n) for n in bbox):
            raise LayoutError(f"{path}.bbox: coordinates must be finite numbers")
        left, top, right, bottom = bbox
        if not (0 <= left < right <= width and 0 <= top < bottom <= height):
            raise LayoutError(f"{path}.bbox: must have positive area within {width}x{height}")
        left, top = math.floor(left), math.floor(top)
        right, bottom = math.ceil(right), math.ceil(bottom)
        target = {
            "label": item["label"],
            "caption": item["caption"],
        }
        if "text" in item:
            target["text"] = item["text"]
        target["bbox"] = [top - height // 2, left - width // 2, bottom - height // 2, right - width // 2]
        result_items.append(target)

    return {
        "summary": result_summary,
        "items": result_items,
        "bbox_coord_space": "abs_centralized",
        "bbox_format": "yxyx",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("draft", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, help="Optional sidecar with dimensions and SHA256")
    args = parser.parse_args(argv)
    try:
        data = json.loads(args.draft.read_text(encoding="utf-8"), object_pairs_hook=_unique_pairs)
        layout = compile_layout(data)
        # Final model prompt deliberately has no app metadata, including width/height.
        raw = json.dumps(layout, ensure_ascii=False, separators=(",", ":"))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw, encoding="utf-8")
        if args.manifest:
            manifest = {
                "width": data["width"], "height": data["height"],
                "draft": str(args.draft), "prompt_file": str(args.output),
                "prompt_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
                "compiler": "novel2moss-stdlib-v1",
            }
            args.manifest.parent.mkdir(parents=True, exist_ok=True)
            args.manifest.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"PASS: {len(layout['items'])} item(s), {data['width']}x{data['height']} -> {args.output}")
        return 0
    except (ValueError, OSError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
