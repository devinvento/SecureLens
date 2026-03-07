from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.db.session import Base

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    username = Column(String, nullable=False)
    ip_address = Column(String(45), nullable=False)
    event_type = Column(String(50), nullable=False)
    message = Column(Text, nullable=False)
    status = Column(String(20), default="success")
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
