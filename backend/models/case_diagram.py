from datetime import datetime
from sqlalchemy import String, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from backend.database import Base


class CaseDiagram(Base):
    """Advisor-edited structure diagram for a case.

    Stored in a separate table so adding/removing the feature doesn't require
    migrating the cases table. Nodes and edges are serialised as JSON strings
    because SQLite's JSON support is inconsistent across versions.
    """

    __tablename__ = "case_diagrams"

    case_id: Mapped[str] = mapped_column(
        String, ForeignKey("cases.case_id"), primary_key=True
    )
    nodes_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    edges_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    updated_by: Mapped[str | None] = mapped_column(String, nullable=True)
