import uuid
from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from backend.database import Base
from backend.models.types import EncryptedString

class ClientProfile(Base):
    __tablename__ = "client_profiles"

    profile_id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id: Mapped[str] = mapped_column(String, ForeignKey("cases.case_id", ondelete="CASCADE"), unique=True, nullable=False)
    nationality: Mapped[str | None] = mapped_column(String)
    domicile: Mapped[str | None] = mapped_column(String)
    tax_residency: Mapped[str | None] = mapped_column(String)
    family_members: Mapped[str | None] = mapped_column(EncryptedString)  # encrypted
    asset_classes: Mapped[str | None] = mapped_column(Text)
    asset_jurisdictions: Mapped[str | None] = mapped_column(Text)
    existing_structures: Mapped[str | None] = mapped_column(EncryptedString)  # encrypted
    objectives: Mapped[str | None] = mapped_column(EncryptedString)  # encrypted
