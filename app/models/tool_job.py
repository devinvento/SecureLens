from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func
from app.db.session import Base

class ToolJob(Base):
    __tablename__ = "tool_jobs"

    id = Column(Integer, primary_key=True, index=True)
    tool_name = Column(String, nullable=False)
    target = Column(String, nullable=False)
    args = Column(String, default="")
    sources = Column(String, default="")
    status = Column(String, default="pending")  # pending, running, completed, failed
    output = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
