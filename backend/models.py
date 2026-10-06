import os
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

DSN = os.environ.get("DATABASE_URL", "postgresql://app:app@localhost:54401/tunnelconv")
engine = create_engine(DSN, pool_pre_ping=True)
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


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


class NightReminderConfig(Base):
    """夜间提醒设置，单行（id=1）。light_on 是上次评估结果，用于灭->亮边沿记履历。"""

    __tablename__ = "night_reminder_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    night_start: Mapped[str] = mapped_column(String, nullable=False, default="22:00")
    night_end: Mapped[str] = mapped_column(String, nullable=False, default="06:00")
    threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    recent_hours: Mapped[float] = mapped_column(Float, nullable=False, default=2.0)
    light_on: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_by: Mapped[str | None] = mapped_column(String, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class NightReminderEvent(Base):
    """提醒流水：灯由灭转亮时记一条，仅提示值班，从不拦截交单。"""

    __tablename__ = "night_reminder_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    night_start: Mapped[str] = mapped_column(String, nullable=False)
    night_end: Mapped[str] = mapped_column(String, nullable=False)
    threshold: Mapped[int] = mapped_column(Integer, nullable=False)
    recent_hours: Mapped[float] = mapped_column(Float, nullable=False)
    recent_count: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[str] = mapped_column(String, nullable=False)


def config_dict(cfg: NightReminderConfig) -> dict:
    return {
        "night_start": cfg.night_start,
        "night_end": cfg.night_end,
        "threshold": cfg.threshold,
        "recent_hours": cfg.recent_hours,
        "updated_by": cfg.updated_by,
        "updated_at": cfg.updated_at.isoformat() if cfg.updated_at else None,
    }


def event_dict(row: NightReminderEvent) -> dict:
    return {
        "id": row.id,
        "triggered_at": row.triggered_at.isoformat() if row.triggered_at else None,
        "night_start": row.night_start,
        "night_end": row.night_end,
        "threshold": row.threshold,
        "recent_hours": row.recent_hours,
        "recent_count": row.recent_count,
        "note": row.note,
    }
