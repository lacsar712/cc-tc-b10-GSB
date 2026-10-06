"""夜间低办结提醒判定（只提醒，绝不参与拒收）。

- 夜间窗按服务端本地墙上时钟的 HH:MM 判定，支持跨午夜（如 22:00–06:00）。
- 近窗办结数：processed_at 落在最近 window_minutes 内、状态 done 的行数。
- 亮灯条件：当前落在夜间窗 且 近窗办结数 < 低样本阈值。
- 亮灯/灭灯只在状态翻转时写一条提醒履历。
"""
from datetime import datetime, time, timedelta, timezone

from sqlalchemy import func

from models import (
    ConvergenceLog,
    NightReminder,
    NightSetting,
    SessionLocal,
    reminder_dict,
    setting_dict,
)

SETTING_ID = 1


def server_now() -> datetime:
    """服务端时钟（带时区）。"""
    return datetime.now(timezone.utc)


def get_setting(db) -> NightSetting:
    s = db.get(NightSetting, SETTING_ID)
    if s is None:
        s = NightSetting(id=SETTING_ID)
        db.add(s)
        db.commit()
        db.refresh(s)
    return s


def parse_hhmm(value: str) -> time:
    hh, mm = value.split(":")
    return time(hour=int(hh), minute=int(mm))


def in_night_window(local_now: datetime, start_s: str, end_s: str) -> bool:
    """判断本地时刻是否落在夜间窗。start==end 视为不覆盖任何时刻。"""
    if start_s == end_s:
        return False
    start = parse_hhmm(start_s)
    end = parse_hhmm(end_s)
    t = local_now.time().replace(second=0, microsecond=0)
    if start < end:
        return start <= t < end
    # 跨午夜：start 之后 或 end 之前
    return t >= start or t < end


def count_recent_done(db, now_utc: datetime, window_minutes: int) -> int:
    cutoff = now_utc - timedelta(minutes=window_minutes)
    return (
        db.query(func.count(ConvergenceLog.id))
        .filter(
            ConvergenceLog.status == "done",
            ConvergenceLog.processed_at.isnot(None),
            ConvergenceLog.processed_at >= cutoff,
        )
        .scalar()
        or 0
    )


def last_reminder(db) -> NightReminder | None:
    return (
        db.query(NightReminder)
        .order_by(NightReminder.id.desc())
        .first()
    )


def evaluate(db, now_utc: datetime | None = None) -> dict:
    """计算当前提醒状态；亮/灭翻转时写履历。返回前端需要的状态。"""
    if now_utc is None:
        now_utc = server_now()
    s = get_setting(db)
    local_now = now_utc.astimezone()  # 服务端本地时区

    in_window = in_night_window(local_now, s.night_start, s.night_end)
    recent = count_recent_done(db, now_utc, s.window_minutes)
    light_on = in_window and recent < s.low_threshold

    last = last_reminder(db)
    was_on = last is not None and last.kind == "on"
    if light_on != was_on:
        if light_on:
            reason = (
                f"夜间时段（{s.night_start}–{s.night_end}）近 {s.window_minutes} 分钟"
                f"办结 {recent} 条，低于低样本阈值 {s.low_threshold}，提醒值班关注"
            )
        else:
            if not in_window:
                reason = f"当前不在夜间时段（{s.night_start}–{s.night_end}），提醒灯熄灭"
            else:
                reason = (
                    f"近 {s.window_minutes} 分钟办结 {recent} 条，"
                    f"已达到低样本阈值 {s.low_threshold}，提醒灯熄灭"
                )
        db.add(
            NightReminder(
                kind="on" if light_on else "off",
                reason=reason,
                in_night_window=in_window,
                recent_done=recent,
                window_minutes=s.window_minutes,
                low_threshold=s.low_threshold,
                night_start=s.night_start,
                night_end=s.night_end,
                created_by="system",
                created_at=now_utc,
            )
        )
        db.commit()

    return {
        "light_on": light_on,
        "in_night_window": in_window,
        "recent_done": recent,
        "server_time": now_utc.isoformat(),
        "local_time": local_now.replace(microsecond=0).isoformat(),
        "setting": setting_dict(s),
    }


def current_state(db, now_utc: datetime | None = None) -> dict:
    return evaluate(db, now_utc=now_utc)


def list_reminders(db, limit: int = 100) -> list[dict]:
    rows = (
        db.query(NightReminder)
        .order_by(NightReminder.id.desc())
        .limit(limit)
        .all()
    )
    return [reminder_dict(r) for r in rows]
