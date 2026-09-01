#!/usr/bin/env python3
"""
Re-chunk existing knowledge-base documents at the current chunk size.

Documents ingested under the old 800-word chunking are re-chunked at the
current CHUNK_SIZE (220 words) so they benefit from the sharper hybrid
retrieval. For each document the original text is reconstructed from its
stored (overlapping) chunks, then re-embedded and re-stored — the old chunks
are replaced in place. Vector embeddings are recomputed, so this must run on
the machine that hosts the Chroma data and can load the embedding model.

Safe to run repeatedly (idempotent — re-chunking an already-current document
reproduces the same chunks).

Usage:
  # Preview: show each document's current vs projected chunk count, no writes
  python scripts/rechunk_kb.py --dry-run

  # Re-chunk everything
  python scripts/rechunk_kb.py

  # Re-chunk a single document by its source_file
  python scripts/rechunk_kb.py --source-file "layer2_wiki_articles/uk/bpr.md"
"""
import argparse
import asyncio
import sys

sys.path.insert(0, ".")

from backend.kb.kb_manager import (  # noqa: E402
    KBManager,
    CHUNK_SIZE,
    _chunk_text,
    _reconstruct_text,
)


async def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--dry-run", action="store_true",
                        help="Show current vs projected chunk counts without writing.")
    parser.add_argument("--source-file", default=None,
                        help="Re-chunk only this one document (its source_file).")
    args = parser.parse_args()

    kb = KBManager()

    if args.dry_run:
        groups = kb._grouped_chunks()
        if args.source_file:
            groups = {k: v for k, v in groups.items() if k == args.source_file}
        if not groups:
            print("No matching documents in the knowledge base.")
            return
        print(f"Target chunk size: {CHUNK_SIZE} words\n")
        print(f"{'source_file':<60} {'now':>5} {'->':>2} {'new':>5}")
        print("-" * 78)
        total_now = total_new = 0
        for sf, items in sorted(groups.items()):
            text = _reconstruct_text([doc for _, doc, _ in items])
            projected = len(_chunk_text(text))
            total_now += len(items)
            total_new += projected
            print(f"{sf[:60]:<60} {len(items):>5} {'->':>2} {projected:>5}")
        print("-" * 78)
        print(f"{'TOTAL':<60} {total_now:>5} {'->':>2} {total_new:>5}")
        print("\n(dry run — nothing written)")
        return

    if args.source_file:
        res = await kb.rechunk_document(args.source_file)
        if res["old_chunks"] == 0:
            print(f"No document found for source_file={args.source_file!r}")
        else:
            print(f"{args.source_file}: {res['old_chunks']} -> {res['new_chunks']} chunks")
        return

    report = await kb.rechunk_all()
    if not report:
        print("Knowledge base is empty — nothing to re-chunk.")
        return
    total_old = sum(r["old_chunks"] for r in report.values())
    total_new = sum(max(r["new_chunks"], 0) for r in report.values())
    for sf, r in sorted(report.items()):
        if r.get("new_chunks") == -1:
            print(f"  FAILED  {sf}: {r.get('error')}")
        else:
            print(f"  ok      {sf}: {r['old_chunks']} -> {r['new_chunks']}")
    failed = [sf for sf, r in report.items() if r.get("new_chunks") == -1]
    print(f"\nRe-chunked {len(report) - len(failed)}/{len(report)} documents "
          f"({total_old} -> {total_new} chunks).")
    if failed:
        print(f"{len(failed)} failed: {', '.join(failed)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
