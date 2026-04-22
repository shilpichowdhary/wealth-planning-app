#!/usr/bin/env python3
"""
Ingest Layer 2 wiki articles from a KB export into the wealth_planning_kb collection.

Maps each article to a jurisdiction based on its parent folder under
layer2_wiki_articles/wealth_planning/. Topic is pulled from YAML frontmatter.

Usage:
  python scripts/ingest_kb_export.py \
    --export-dir /Users/shilpi/Downloads/kb_full_export_2026-04-21 \
    --wipe

  # Preview without writing:
  python scripts/ingest_kb_export.py --export-dir <path> --dry-run
"""
import argparse
import asyncio
import sys
from pathlib import Path

import yaml

sys.path.insert(0, ".")
from backend.kb.chroma_client import KB_COLLECTION, get_chroma_client
from backend.kb.kb_manager import KBManager

# folder name under layer2_wiki_articles/wealth_planning → jurisdiction tag
JURISDICTION_FOLDERS = {
    "india": "india",
    "singapore": "singapore",
    "uae": "uae",
    "usa": "usa",
    "uk": "uk",
    "taiwan": "taiwan",
    "china": "china",
    "cross-border": "cross-border",
}


def parse_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    try:
        meta = yaml.safe_load(text[4:end]) or {}
    except yaml.YAMLError:
        meta = {}
    return (meta if isinstance(meta, dict) else {}), text[end + 5:]


def pick_topic(meta: dict) -> str:
    for key in ("topic", "category"):
        v = meta.get(key)
        if v:
            return str(v)
    return "general"


def pick_last_updated(meta: dict) -> str | None:
    for key in ("last_compiled", "data_as_of", "last_updated"):
        v = meta.get(key)
        if v:
            return str(v)
    return None


async def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--export-dir", required=True, help="KB export root")
    parser.add_argument("--wipe", action="store_true", help="Delete collection before ingest")
    parser.add_argument("--dry-run", action="store_true", help="List files, don't upload")
    args = parser.parse_args()

    export_root = Path(args.export_dir).expanduser().resolve()
    l2_wp = export_root / "layer2_wiki_articles" / "wealth_planning"
    if not l2_wp.is_dir():
        sys.exit(f"Not found: {l2_wp}")

    # Collect files: jurisdiction hub (e.g., india.md) + all files in subfolder
    plan: list[tuple[Path, str]] = []
    for folder, jurisdiction in JURISDICTION_FOLDERS.items():
        hub = l2_wp / f"{folder}.md"
        if hub.is_file():
            plan.append((hub, jurisdiction))
        subdir = l2_wp / folder
        if subdir.is_dir():
            plan.extend((f, jurisdiction) for f in sorted(subdir.rglob("*.md")))

    counts: dict[str, int] = {}
    for _, j in plan:
        counts[j] = counts.get(j, 0) + 1
    print(f"Found {len(plan)} Layer 2 wealth-planning files:")
    for j in sorted(counts):
        print(f"  {j:15s} {counts[j]:3d}")

    if args.dry_run:
        print("\nDry run — exiting without uploading.")
        return

    if args.wipe:
        client = get_chroma_client()
        try:
            client.delete_collection(KB_COLLECTION)
            print(f"\nWiped collection: {KB_COLLECTION}")
        except Exception as e:
            print(f"\n(Collection did not exist or could not be wiped: {e})")

    kb = KBManager()
    total_chunks = 0
    for i, (path, jurisdiction) in enumerate(plan, 1):
        raw = path.read_text(encoding="utf-8", errors="replace")
        meta, body = parse_frontmatter(raw)
        topic = pick_topic(meta)
        source_file = str(path.relative_to(export_root))
        chunks = await kb.upload_kb_file(
            content=(body.strip() or raw),
            source_file=source_file,
            jurisdiction=jurisdiction,
            topic=topic,
            last_updated=pick_last_updated(meta),
            source_type="kb_l2_wiki",
        )
        total_chunks += chunks
        print(f"[{i:3d}/{len(plan)}] {jurisdiction:13s} {topic:20s} +{chunks:3d}  {source_file}")

    print(f"\nDone. {len(plan)} files → {total_chunks} chunks across {len(counts)} jurisdictions.")


if __name__ == "__main__":
    asyncio.run(main())
