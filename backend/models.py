from __future__ import annotations
from datetime import UTC, datetime
from sqlalchemy import DateTime, Integer, String, Text, ForeignKey, Float, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from enum import Enum

from database import Base

class Status(Enum):
    PENDING = "pending"
    CLASSIFYING = "classifying"
    SUMMARIZING = "summarizing"
    COMPLETED = "completed"
    FAILED = "failed"

class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key = True, index = True)
    s3_file_key: Mapped[str] = mapped_column(String, unique = True, index = True, nullable = False)
    status: Mapped[Status] = mapped_column(SQLEnum(Status), nullable=False, default=Status.PENDING)
    latitude: Mapped[float] = mapped_column(Float, nullable=True)
    longitude = Mapped[float] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone = True), 
        nullable = False, 
        default=lambda: datetime.now(UTC)
        )
    result_profile: Mapped[str | None] = mapped_column(Text, nullable = True)

    classifications: Mapped[list["Bird"]] = relationship(back_populates="job", cascade="all, delete-orphan")

class Bird(Base):
    __tablename__ = "birds"

    id: Mapped[int] = mapped_column(Integer, primary_key = True, index = True)
    job_id: Mapped[int] = mapped_column(Integer, ForeignKey("jobs.id"), nullable = False, index = True)

    job: Mapped["Job"] = relationship(back_populates = "classifications")

    bird_name: Mapped[str] = mapped_column(String, nullable = False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    start_time: Mapped[float] = mapped_column(Float, nullable=False)
    end_time: Mapped[float] = mapped_column(Float, nullable=False)
