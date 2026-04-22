#!/usr/bin/env python3
"""
Backfill compact session summaries for cases that never got one (or all cases
if --force is passed). Uses the same generate_compact_summary pipeline the
chat router calls after every turn, so results match what you'd get going
forward.

Usage:
  # Only cases where compact_summary is NULL or empty (safe default)
  python scripts/backfill_summaries.py

  # Regenerate for every case, overwriting existing summaries
  python scripts/backfill_summaries.py --force

  # Preview without writing
  python scripts/backfill_summaries.py --dry-run
"""
import argparse
import asyncio
import sys
from datetime import datetime

sys.path.insert(0, ".")

from sqlalchemy import select
from backend.database import AsyncSessionLocal
from backend.models.case import Case
from backend.models.conversation import Conversation
from backend.services.summary_service import generate_compact_summary


async def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate summaries for all cases, not just those missing one.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be regenerated without writing to the DB.",
    )
    args = parser.parse_args()

    async with AsyncSessionLocal() as db:
        cases = (await db.execute(select(Case))).scalars().all()

        touched = 0
        skipped_no_history = 0
        skipped_has_summary = 0
        failures = 0

        for case in cases:
            has_summary = bool(case.compact_summary) and case.compact_summary.strip() not in ("", "{}")
            if has_summary and not args.force:
                skipped_has_summary += 1
                continue

            history_rows = (
                await db.execute(
                    select(Conversation)
                    .where(Conversation.case_id == case.case_id)
                    .order_by(Conversation.timestamp.asc())
                )
            ).scalars().all()

            if not history_rows:
                skipped_no_history += 1
                print(f"[skip] {case.case_id[:8]}  {case.client_name:<28}  no conversation history")
                continue

            history = [
                {
                    "role": msg.role.value if hasattr(msg.role, "value") else str(msg.role),
                    "content": msg.content,
                }
                for msg in history_rows
            ]

            print(f"[gen]  {case.case_id[:8]}  {case.client_name:<28}  {len(history)} messages  ", end="", flush=True)
            try:
                summary = await generate_compact_summary(history)
            except Exception as e:
                failures += 1
                print(f"failed: {e}")
                continue

            if not summary or summary.strip() in ("", "{}"):
                failures += 1
                print("empty summary returned")
                continue

            if args.dry_run:
                print(f"OK ({len(summary)} chars, not saved)")
            else:
                case.compact_summary = summary
                await db.commit()
                touched += 1
                print(f"saved ({len(summary)} chars)")

        print(
            f"\nDone at {datetime.utcnow().isoformat()}Z. "
            f"written={touched} · skipped_existing={skipped_has_summary} · "
            f"skipped_empty={skipped_no_history} · failed={failures}"
        )


if __name__ == "__main__":
    asyncio.run(main())
