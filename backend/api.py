import os
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import Flask, g, jsonify, request
from jose import JWTError, jwt
from passlib.context import CryptContext

from claimer import start as start_claimer
from models import (
    Base,
    ConvergenceLog,
    NightReminderEvent,
    SessionLocal,
    engine,
    event_dict,
    row_dict,
)
from night import evaluate, get_config, valid_hhmm

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
        get_config(db)  # 夜间提醒单行配置，不存在则按默认建
        db.commit()
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


@app.get("/api/night-reminder")
@require_login
def night_reminder_status():
    """夜间窗判定 -> 提醒灯。测量员与巡检员都可看，判定用服务端时钟。"""
    db = SessionLocal()
    try:
        state = evaluate(db)
        db.commit()
        return jsonify(state)
    finally:
        db.close()


@app.put("/api/night-reminder")
@require_login
def night_reminder_update():
    if g.user["role"] != "writer":
        return jsonify({"detail": "仅测量员可修改夜间提醒设置"}), 403
    body = request.get_json(silent=True) or {}
    night_start = (body.get("night_start") or "").strip()
    night_end = (body.get("night_end") or "").strip()
    if not valid_hhmm(night_start) or not valid_hhmm(night_end):
        return jsonify({"detail": "夜间时段格式应为 HH:MM（24 小时制）"}), 400
    try:
        threshold = int(body.get("threshold"))
    except (TypeError, ValueError):
        return jsonify({"detail": "低样本阈值应为整数"}), 400
    if not 1 <= threshold <= 999:
        return jsonify({"detail": "低样本阈值应在 1-999 之间"}), 400
    try:
        recent_hours = float(body.get("recent_hours"))
    except (TypeError, ValueError):
        return jsonify({"detail": "近窗时长应为数字"}), 400
    if not 0.1 <= recent_hours <= 72:
        return jsonify({"detail": "近窗时长应在 0.1-72 小时之间"}), 400
    db = SessionLocal()
    try:
        cfg = get_config(db)
        cfg.night_start = night_start
        cfg.night_end = night_end
        cfg.threshold = threshold
        cfg.recent_hours = recent_hours
        cfg.updated_by = g.user["username"]
        cfg.updated_at = datetime.now(timezone.utc)
        state = evaluate(db)  # 改完立即按新设置重判，亮灭边沿记履历
        db.commit()
        return jsonify(state)
    finally:
        db.close()


@app.get("/api/night-reminder/events")
@require_login
def night_reminder_events():
    """提醒流水，巡检员只读。"""
    db = SessionLocal()
    try:
        rows = (
            db.query(NightReminderEvent)
            .order_by(NightReminderEvent.id.desc())
            .limit(200)
            .all()
        )
        return jsonify([event_dict(r) for r in rows])
    finally:
        db.close()
