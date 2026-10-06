# 隧道收敛测缝台

测量员登记里程桩号与收敛毫米值。接口进程内后台线程认领待判行（不另起 worker 容器），按绝对值是否不超过 3.0 mm 给出合格或超限。页面是 Svelte。

**夜间低办结提醒**：页眉「夜间提醒」进入专页，可设夜间时段（支持跨午夜，按**服务端本地时钟**判定）、近窗分钟数与低样本阈值。当前落在夜间窗且近窗办结数低于阈值时提醒灯亮并写一条亮灯履历；条件消失（出窗或办结达标）写灭灯履历。**提醒只提醒、不拒收**——灯亮时白天或夜间交单一律放行；拱顶二衬龄期不足等场景该提醒也仍只是提醒。巡检员只读阈值与提醒履历。

## 技术栈

- 后端：Flask、Gunicorn、SQLAlchemy、进程内认领线程
- 前端：Svelte、Vite、nginx 反代 `/api`
- 数据库：PostgreSQL 16（本机无 PG 时可用 `DATABASE_URL=sqlite:///…` 验收）

## 端口

| 服务 | 地址 |
|------|------|
| 页面 | http://localhost:3201 |
| 接口 | http://localhost:8201 |
| PostgreSQL | localhost:54401（库名 `tunnelconv`） |

## 账号

| 用户 | 密码 | 权限 |
|------|------|------|
| surveyor | surv123456 | 可提交 |
| inspector | insp123456 | 只读 |

## 启动

```bash
cd projects/21-tunnel-convergence-desk
docker compose up --build
```

健康检查：`GET http://localhost:8201/api/health`

## 种子

| 桩号 | 收敛 | 结论 |
|------|------|------|
| K12+180 | 1.2 mm | 合格 |
| K18+040 | 5.6 mm | 超限 |
