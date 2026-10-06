"""夜间提醒：此刻落在夜间时段且近窗办结低于阈值才亮灯并记履历。

判定一律用服务端时钟。提醒仅提示值班，绝不拦截写口（POST /api/logs 不读这里）。
"""
import re
from datetime import datetime, timedelta

from models import (
    ConvergenceLog,
    NightReminderConfig,
    NightReminderEvent,
    config_dict,
)

CONFIG_ID = 1
DEFAULTS = {"night_start": "22:00", "night_end": "06:00", "threshold": 3, "recent_hours": 2.0}

HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def valid_hhmm(value) -> bool:
    return isinstance(value, str) and HHMM.match(value) is not None


def _hhmm_to_time(value: str):
    hh, mm = int(value[:2]), int(value[3:5])
    return hh * 60 + mm


def in_night_window(now: datetime, start: str, end: str) -> bool:
    """按服务端时钟的时分判断；时段跨零点（如 22:00-06:00）也算。"""
    cur = now.hour * 60 + now.minute
    lo, hi = _hhmm_to_time(start), _hhmm_to_time(end)
    if lo <= hi:
        return lo <= cur < hi
    return cur >= lo or cur < hi


def get_config(db) -> NightReminderConfig:
    cfg = db.get(NightReminderConfig, CONFIG_ID)
    if cfg is None:
        cfg = NightReminderConfig(id=CONFIG_ID, light_on=False, **DEFAULTS)
        db.add(cfg)
        db.flush()
    return cfg


def evaluate(db) -> dict:
    """锁配置行后评估；灯由灭转亮时记一条提醒履历。调用方负责 commit。"""
    cfg = (
        db.query(NightReminderConfig)
        .filter(NightReminderConfig.id == CONFIG_ID)
        .with_for_update()
        .first()
    )
    if cfg is None:
        cfg = get_config(db)
        db.flush()

    now = datetime.now().astimezone()
    since = now - timedelta(hours=float(cfg.recent_hours))
    recent_count = (
        db.query(ConvergenceLog)
        .filter(ConvergenceLog.status == "done", ConvergenceLog.processed_at >= since)
        .count()
    )
    in_window = in_night_window(now, cfg.night_start, cfg.night_end)
    light_on = in_window and recent_count < cfg.threshold

    if light_on and not cfg.light_on:
        db.add(
            NightReminderEvent(
                triggered_at=now,
                night_start=cfg.night_start,
                night_end=cfg.night_end,
                threshold=cfg.threshold,
                recent_hours=cfg.recent_hours,
                recent_count=recent_count,
                note=(
                    f"夜间时段 {cfg.night_start}-{cfg.night_end} 内近 {cfg.recent_hours} 小时"
                    f"办结 {recent_count} 起，低于阈值 {cfg.threshold}，请提醒值班核对"
                ),
            )
        )
    cfg.light_on = light_on
    db.flush()

    return {
        "config": config_dict(cfg),
        "server_time": now.isoformat(),
        "in_night_window": in_window,
        "recent_count": recent_count,
        "light_on": light_on,
    }
