"""进程内认领：同一 Flask 进程后台线程抢 pending，不另起容器。

同一线程也周期评估夜间低办结提醒灯（只写提醒履历，绝不影响交单）。
"""
import threading
import time
from datetime import datetime, timezone

import night
from models import ConvergenceLog, SessionLocal
from rules import judge

_stop = threading.Event()


def claim_once() -> bool:
    db = SessionLocal()
    try:
        row = (
            db.query(ConvergenceLog)
            .filter(ConvergenceLog.status == "pending")
            .order_by(ConvergenceLog.id)
            .with_for_update(skip_locked=True)
            .first()
        )
        if row is None:
            db.commit()
            return False
        verdict, reason = judge(float(row.delta_mm))
        row.status = "done"
        row.verdict = verdict
        row.reason = reason
        row.processed_at = datetime.now(timezone.utc)
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def evaluate_night() -> None:
    db = SessionLocal()
    try:
        night.evaluate(db)
    except Exception as exc:
        print(f"night evaluate error: {exc}", flush=True)
    finally:
        db.close()


def loop():
    tick = 0
    while not _stop.is_set():
        try:
            if claim_once():
                time.sleep(0.4)
            else:
                time.sleep(1.0)
            # 约每 10 个循环评估一次夜间提醒灯
            tick += 1
            if tick % 10 == 0:
                evaluate_night()
        except Exception as exc:
            print(f"claimer error: {exc}", flush=True)
            time.sleep(1.0)


def start():
    t = threading.Thread(target=loop, name="convergence-claimer", daemon=True)
    t.start()
