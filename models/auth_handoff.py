from sqlalchemy import UUID, Column, DateTime, ForeignKey, String

from models.base import Base


class AuthHandoff(Base):
    __tablename__ = "auth_handoff"

    code_hash  = Column(String(64), primary_key=True)
    user_id    = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at    = Column(DateTime(timezone=True), nullable=True)