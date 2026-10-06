import os
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

DSN = os.environ.get(
    "DATABASE_URL", "postgresql://app:app@localhost:54401/tunnelconv"
)
# 验收/本机无 Postgres 时可用 SQLite：DATABASE_URL=sqlite:////tmp/tunnel.db
connect_args = {"check_same_thread": False} if DSN.startswith("sqlite") else {}
engine = create_engine(DSN, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


class ConvergenceLog(Base):
    __tablename__ = "convergence_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chainage: Mapped[str] = mapped_column(String, nullable=False)
    delta_mm: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    verdict: Mapped[str | None] = mapped_column(String, nullable=True)
    reason: Mapped[str | None] = mapped_column(String, nullable=True)
    created_by: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


def row_dict(row: ConvergenceLog) -> dict:
    return {
        "id": row.id,
        "chainage": row.chainage,
        "delta_mm": row.delta_mm,
        "status": row.status,
        "verdict": row.verdict,
        "reason": row.reason,
        "created_by": row.created_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "processed_at": row.processed_at.isoformat() if row.processed_at else None,
    }


class NightSetting(Base):
    """夜间提醒设置（单行，id 恒为 1）。时间为服务端本地墙上时钟的 HH:MM。"""

    __tablename__ = "night_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    night_start: Mapped[str] = mapped_column(String(5), nullable=False, default="22:00")
    night_end: Mapped[str] = mapped_column(String(5), nullable=False, default="06:00")
    window_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    low_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    updated_by: Mapped[str | None] = mapped_column(String, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


def setting_dict(s: NightSetting) -> dict:
    return {
        "night_start": s.night_start,
        "night_end": s.night_end,
        "window_minutes": s.window_minutes,
        "low_sample_threshold": s.low_threshold,
        "updated_by": s.updated_by,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }


class NightReminder(Base):
    """提醒履历（亮灯/灭灯流水）。提醒只记录，绝不拒收交单。"""

    __tablename__ = "night_reminders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(8), nullable=False)  # on=亮灯 / off=灭灯
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    in_night_window: Mapped[bool] = mapped_column(Boolean, nullable=False)
    recent_done: Mapped[int] = mapped_column(Integer, nullable=False)
    window_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    low_threshold: Mapped[int] = mapped_column(Integer, nullable=False)
    night_start: Mapped[str] = mapped_column(String(5), nullable=False)
    night_end: Mapped[str] = mapped_column(String(5), nullable=False)
    created_by: Mapped[str] = mapped_column(
        String, nullable=False, default="system"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


def reminder_dict(r: NightReminder) -> dict:
    return {
        "id": r.id,
        "kind": r.kind,
        "reason": r.reason,
        "in_night_window": r.in_night_window,
        "recent_done": r.recent_done,
        "window_minutes": r.window_minutes,
        "low_sample_threshold": r.low_threshold,
        "night_start": r.night_start,
        "night_end": r.night_end,
        "created_by": r.created_by,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }
