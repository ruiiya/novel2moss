#!/usr/bin/env python3
"""Flatten a compiled MOSS Layout prompt into one natural-language prompt.

Stdlib only. Reads layout.prompt.json (summary/items, abs_centralized/yxyx),
strips non-visual material, then emits prose + a sidecar. Never invents facts,
never edits the source layout, never touches SQLite.
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

SET_RE = re.compile(r"\bSET_[A-Za-z0-9_]+\b")
NEG_RE = re.compile(
    r"(?i)(no panels?|no split[- ]screen|no comic grid|no extra limbs|no duplicate"
    r"|no spectators?|no crew|no captions?|no watermarks?|no text\b|no underexposure"
    r"|no low-key|no dark falloff|not a grid or (collage|rows)|overlap shoulders"
    r"|stagger head heights|heads and torsos fill|all participants are adults"
    r"|explicit adult group sex)")
LABEL_RE = re.compile(
    r"(?i)^(explicit|nsfw|adult|consensual|bdsm|d/s|tpe|yuri|straight|editorial"
    r"|professional_photoshoot|bright_lighting|rough_sex|bdsm_light)$")
CLOTHES_RE = re.compile(
    r"(?i)^(?:(?:a|an|the|his|her|their)\s+)?"
    r"(?:(?:tight|torn|ripped|navy|black|white|red|blue|dark|fitted|short|long"
    r"|school|gym|pleated|lace)\s+)*"
    r"(?:uniform|blazer|shirt|skirt|thighhighs|lingerie|jacket|bloomers|dress|bra|panties)\b")
ORPHAN_RE = re.compile(r"(?i)^(?:tight |torn |school |gym |navy )?uniform$")


def _segments(text):
    return [s.strip() for s in text.split(",") if s.strip()]


def _clean_segment(seg):
    seg = SET_RE.sub("", seg)
    seg = re.sub(r"\s{2,}", " ", seg).strip(" .;:-")
    if not seg or LABEL_RE.match(seg) or NEG_RE.search(seg) or ORPHAN_RE.match(seg):
        return ""
    return seg


def _dedupe(segs):
    seen, out = set(), []
    for seg in segs:
        key = seg.lower()
        if key not in seen:
            seen.add(key)
            out.append(seg)
    return out


def _sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def _fix_outfit_verb(seg):
    return re.sub(
        r"(?i)\b(?:is|are) ((?:a |an |the )?(?:tight |torn |ripped )?"
        r"(?:school|gym|navy)? ?uniform|blazer|shirt|skirt|thighhighs|lingerie)\b",
        r"wears \1", seg)


def _clean_sentences(text):
    cleaned = []
    for sent in _sentences(text):
        keep = [_clean_segment(s) for s in _segments(sent)]
        keep = [s for s in keep if s]
        if not keep:
            continue
        joined = ", ".join(keep)
        cleaned.append(_fix_outfit_verb(joined).rstrip(".") + ".")
    return cleaned


def _overlap(sent, captions):
    words = set(re.findall(r"[a-z]{4,}", sent.lower()))
    if not words:
        return 0.0
    best = 0.0
    for cap in captions:
        cap_words = set(re.findall(r"[a-z]{4,}", cap.lower()))
        if cap_words:
            best = max(best, len(words & cap_words) / len(words))
    return best


def _character_sentence(caption):
    segs = _dedupe([s for s in (_clean_segment(x) for x in _segments(caption)) if s])
    if not segs:
        return None
    name, rest = segs[0], segs[1:]
    split = next(
        (i for i, seg in enumerate(rest)
         if CLOTHES_RE.match(seg) and not seg.lower().startswith("wearing")),
        None)
    if split is None:
        body = ", ".join(rest)
    else:
        head = ", ".join(rest[:split])
        worn = ", ".join(rest[split:])
        body = f"{head}, wearing {worn}" if head else f"wearing {worn}"
    return f"{name}, {body}.".replace(", .", ".") if body else f"{name}."


def flatten(layout):
    summary = layout.get("summary") or {}
    items = layout.get("items") or []
    chars = [i for i in items if i.get("label") == "character"]
    captions = [i.get("caption", "") for i in chars]
    parts, dropped = [], []
    text_items = []

    scene = _clean_sentences(summary.get("caption", ""))
    for sent in scene:
        if chars and _overlap(sent, captions) >= 0.75:
            dropped.append(sent)
            continue
        parts.append(sent)

    for item in items:
        cap = item.get("caption", "")
        if item.get("label") == "object":
            for sent in _clean_sentences(cap):
                if chars and _overlap(sent, captions) >= 0.75:
                    continue
                if parts and _overlap(sent, [" ".join(parts)]) >= 0.8:
                    continue
                parts.append(sent)
        elif item.get("label") == "text":
            text_items.append(item.get("text", ""))
            parts.append(f'The image shows the text "{item.get("text", "")}".')

    for item in chars:
        sent = _character_sentence(item.get("caption", ""))
        if sent:
            parts.append(sent)

    prose = " ".join(parts)
    prose = re.sub(r"\s{2,}", " ", prose).replace("..", ".")
    prose = re.sub(r"\s+([.,;])", r"\1", prose)
    prose = re.sub(r"\ba (athletic|adult|older|eager|explicit)\b", r"an \1", prose)
    prose = re.sub(
        r"(?i)\b(blazer|shirt|skirt|dress|jacket) (?:school|gym) uniform\b", r"\1", prose)
    prose = re.sub(r"\s{2,}", " ", prose)
    prose = prose.strip()
    if prose and prose[-1] not in ".!?":
        prose += "."

    issues = []
    if not chars and not text_items:
        issues.append("NO_CHARACTER_ITEM")
    if len(text_items) != sum(1 for i in items if i.get("label") == "text"):
        issues.append("TEXT_ITEM_LOST")
    for text in text_items:
        if text and text not in prose:
            issues.append("TEXT_VERBATIM_LOST")
            break
    if re.search(r"\[\s*-?\d+\s*,\s*-?\d+", prose):
        issues.append("BBOX_IN_PROSE")

    status = "BLOCKED" if not prose.strip() else ("NEEDS_REVIEW" if issues else "PASS")
    return prose, {
        "status": status,
        "characters": [c.get("caption", "").split(",")[0].strip() for c in chars],
        "text_items": text_items,
        "dropped_summary_segments": dropped,
        "issues": sorted(set(issues)),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("layout", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sidecar", type=Path)
    args = parser.parse_args(argv)
    try:
        raw = args.layout.read_text(encoding="utf-8")
        layout = json.loads(raw)
        prose, report = flatten(layout)
        if report["status"] == "BLOCKED":
            print("BLOCKED: no convertible content", file=sys.stderr)
            return 2
        report["source_layout_sha256"] = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        report["natural_prompt_sha256"] = hashlib.sha256(prose.encode("utf-8")).hexdigest()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(prose + "\n", encoding="utf-8")
        if args.sidecar:
            args.sidecar.parent.mkdir(parents=True, exist_ok=True)
            args.sidecar.write_text(
                json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"{report['status']}: {len(report['characters'])} character(s) -> {args.output}")
        return 0
    except (ValueError, OSError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
