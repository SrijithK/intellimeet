from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Integer, JSON, String, Text

from app.db import Base


class JobRecord(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True)
    file_name = Column(String, nullable=False)
    status = Column(String, nullable=False, default="queued")
    meeting = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)


class MeetingRecord(Base):
    __tablename__ = "meetings"

    id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    source_name = Column(String, nullable=False)


class TurnRecord(Base):
    __tablename__ = "turns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    meeting_id = Column(String, ForeignKey("meetings.id"), nullable=False)
    speaker = Column(String, nullable=False)
    text = Column(Text, nullable=False)
    start = Column(Integer, nullable=False)
    end = Column(Integer, nullable=True)
