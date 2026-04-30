"""Generated PowerPoint deck for a case.

The curator agent (deck_curator.py) emits a JSON slide spec which is rendered
to .pptx by pptx_service.py. The .pptx (and lazily-converted .pdf) live on
disk under data/reports/{case_id}/ — only paths and the spec live in the DB
so backups stay small and compliance can audit the binaries directly.

A new row is inserted on each Generate-deck action; old versions are kept so
an advisor can compare/diff or restore. Querying by (case_id, version DESC)
gets the current deck.
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class CaseDeck(Base):
    __tablename__ = "case_decks"

    deck_id: Mapped[str] = mapped_column(String, primary_key=True)
    case_id: Mapped[str] = mapped_column(
        String, ForeignKey("cases.case_id"), index=True, nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Editorial source — JSON spec returned by the curator. Stored as text
    # because SQLite JSON support varies across the versions we ship against.
    spec_json: Mapped[str] = mapped_column(Text, nullable=False)

    # Hash of the inputs (chat history + profile + diagram) used to detect
    # whether the case has drifted since this deck was generated, surfacing
    # a "regenerate" prompt in the UI.
    spec_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    # Absolute paths to the rendered binaries. PDF is lazy — populated on
    # first /deck.pdf request after soffice converts the .pptx.
    pptx_path: Mapped[str | None] = mapped_column(String, nullable=True)
    pdf_path: Mapped[str | None] = mapped_column(String, nullable=True)

    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    generated_by: Mapped[str | None] = mapped_column(String, nullable=True)
    model_used: Mapped[str | None] = mapped_column(String, nullable=True)
