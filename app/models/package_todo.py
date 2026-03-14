from sqlalchemy import Column, Integer, String, Text, DateTime, Float
from sqlalchemy.sql import func
from app.db.session import Base


class PackageTodo(Base):
    __tablename__ = "package_todo"

    id = Column(Integer, primary_key=True, index=True)
    target = Column(String, nullable=False)
    package_name = Column(String, nullable=False)
    section = Column(String, nullable=True)  # e.g., "information-gathering", "vulnerability-assessment"
    data = Column(Text, nullable=True)  # JSON data or additional info
    execution_time = Column(Float, nullable=True)  # Execution time in seconds
    status = Column(String, default="pending")  # pending, running, completed, failed
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
