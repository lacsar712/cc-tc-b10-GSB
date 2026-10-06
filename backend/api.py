import os
import re
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import Flask, g, jsonify, request
from jose import JWTError, jwt
from passlib.context import CryptContext

import night
from claimer import start as start_claimer
from models import Base, ConvergenceLog, SessionLocal, engine, row_dict

HHMM_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")

SECRET = os.environ.get("JWT_SECRET", "tunnelconv-dev-secret")
pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
USERS = {
    "surveyor": {"role": "writer", "password_hash": pwd.hash("surv123456")},
    "inspector": {"role": "reader", "password_hash": pwd.hash("insp123456")},
}

app = Flask(__name__)


def seed():
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        if db.query(ConvergenceLog).count() > 0:
            return
        now = datetime.now(timezone.utc)
        for chainage, delta, expect in (("K12+180", 1.2, "合格"), ("K18+040", 5.6, "超限")):
            from rules import judge

            verdict, reason = judge(delta)
            assert verdict == expect
            db.add(
                ConvergenceLog(
                    chainage=chainage,
                    delta_mm=delta,
                    status="done",
                    verdict=verdict,
                    reason=reason,
                    created_by="surveyor",
                    created_at=now,
                    processed_at=now,
                )
            )
        db.commit()
    finally:
        db.close()


seed()
start_claimer()


def current_user():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    try:
        payload = jwt.decode(auth[7:].strip(), SECRET, algorithms=["HS256"])
    except JWTError:
        return None
    sub = payload.get("sub")
    if sub not in USERS:
        return None
    return {"username": sub, "role": payload.get("role")}


def require_login(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user()
        if user is None:
            return jsonify({"detail": "未登录"}), 401
        g.user = user
        return fn(*args, **kwargs)

    return wrapper


def require_writer(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user()
        if user is None:
            return jsonify({"detail": "未登录"}), 401
        if user["role"] != "writer":
            return jsonify({"detail": "仅测量员可提交收敛读数"}), 403
        g.user = user
        return fn(*args, **kwargs)

    return wrapper


@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "service": "tunnel-convergence-desk"})


@app.post("/api/auth/login")
def login():
    body = request.get_json(silent=True) or {}
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""
    user = USERS.get(username)
    if not user or not pwd.verify(password, user["password_hash"]):
        return jsonify({"detail": "用户名或密码错误"}), 401
    exp = datetime.now(timezone.utc) + timedelta(hours=8)
    token = jwt.encode(
        {"sub": username, "role": user["role"], "exp": exp}, SECRET, algorithm="HS256"
    )
    return jsonify({"access_token": token, "username": username, "role": user["role"]})


@app.get("/api/logs")
@require_login
def list_logs():
    db = SessionLocal()
    try:
        rows = db.query(ConvergenceLog).order_by(ConvergenceLog.id.desc()).all()
        return jsonify([row_dict(r) for r in rows])
    finally:
        db.close()


@app.post("/api/logs")
@require_writer
def create_log():
    body = request.get_json(silent=True) or {}
    chainage = (body.get("chainage") or "").strip()
    if not chainage:
        return jsonify({"detail": "桩号不能为空"}), 400
    try:
        delta_mm = float(body.get("delta_mm"))
    except (TypeError, ValueError):
        return jsonify({"detail": "收敛值必须是数字"}), 400
    db = SessionLocal()
    try:
        # 夜间低办结提醒“只提醒、不拒收”：无论提醒灯是否亮，交单一律放行。
        row = ConvergenceLog(
            chainage=chainage,
            delta_mm=delta_mm,
            status="pending",
            created_by=g.user["username"],
            created_at=datetime.now(timezone.utc),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return jsonify(row_dict(row)), 201
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 夜间低办结提醒
# ---------------------------------------------------------------------------


@app.get("/api/night/state")
@require_login
def night_state():
    """当前提醒状态。按服务端时钟实时判定，必要时补写亮/灭履历。"""
    db = SessionLocal()
    try:
        return jsonify(night.current_state(db))
    finally:
        db.close()


@app.get("/api/night/settings")
@require_login
def night_get_settings():
    db = SessionLocal()
    try:
        return jsonify(night.setting_dict(night.get_setting(db)))
    finally:
        db.close()


@app.put("/api/night/settings")
@require_login
def night_update_settings():
    # 巡检员（reader）只读阈值与履历，不能改设置。
    if g.user["role"] != "writer":
        return jsonify({"detail": "仅测量员可修改夜间提醒设置"}), 403
    body = request.get_json(silent=True) or {}

    night_start = (body.get("night_start") or "").strip()
    night_end = (body.get("night_end") or "").strip()
    if not HHMM_RE.match(night_start) or not HHMM_RE.match(night_end):
        return jsonify({"detail": "夜间时段须为 HH:MM 格式"}), 400
    try:
        window_minutes = int(body.get("window_minutes"))
        low_threshold = int(body.get("low_sample_threshold"))
    except (TypeError, ValueError):
        return jsonify({"detail": "近窗分钟与低样本阈值必须是整数"}), 400
    if not 1 <= window_minutes <= 1440:
        return jsonify({"detail": "近窗分钟须在 1–1440 之间"}), 400
    if not 0 <= low_threshold <= 100000:
        return jsonify({"detail": "低样本阈值超出允许范围"}), 400

    db = SessionLocal()
    try:
        s = night.get_setting(db)
        s.night_start = night_start
        s.night_end = night_end
        s.window_minutes = window_minutes
        s.low_threshold = low_threshold
        s.updated_by = g.user["username"]
        s.updated_at = datetime.now(timezone.utc)
        db.commit()
        # 设置改变后立即按服务端时钟重新评估并落履历。
        state = night.current_state(db)
        return jsonify(state)
    finally:
        db.close()


@app.get("/api/night/reminders")
@require_login
def night_list_reminders():
    db = SessionLocal()
    try:
        return jsonify(night.list_reminders(db))
    finally:
        db.close()


@app.post("/api/night/clear-done")
@require_login
def night_clear_done():
    """演练用：清空已办结记录（近窗办结随之归零）。仅测量员可操作。

    删除 done 行不影响交单；pending 行保留，认领线程会继续判。
    """
    if g.user["role"] != "writer":
        return jsonify({"detail": "仅测量员可清空办结记录"}), 403
    db = SessionLocal()
    try:
        deleted = (
            db.query(ConvergenceLog)
            .filter(ConvergenceLog.status == "done")
            .delete(synchronize_session=False)
        )
        db.commit()
        state = night.current_state(db)
        return jsonify({"deleted_done": deleted, **state})
    finally:
        db.close()
