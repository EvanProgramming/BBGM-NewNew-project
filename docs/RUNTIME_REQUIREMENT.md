# Elegram 运行环境要求

依据：根目录 `.env.example`、`frontend/.env.example`、`backend/config.py`、`README.md` 本地运行。接口形状仍以 `docs/schema.md` 为准。

本文只说明**怎么把站点跑起来**：进程、端口、环境变量、本地与生产布局。不写头像、角色、字数或管理员用户列表。

密钥与真实邮箱只写在本机或服务器 `.env`，不要写进本文件、规则或源码。不要提交填好的 `.env`。

本版不绑定特定云厂商。生产一节是一种已跑通的布局，不是必须用哪家主机。

---

## 1. 栈

| 层 | 要求 |
| --- | --- |
| 前端 | React + Vite + Tailwind，代码只在 `frontend/`。Node **18+**（Vite 6）。 |
| 后端 | Python + FastAPI，代码只在 `backend/`。用 **Python 3.12** 级虚拟环境；系统自带 3.6 不够跑当前 FastAPI。依赖见 `backend/requirements.txt`。 |
| 存储 | 两个库：新闻/分享内容库（`DATABASE_URL`）与 CJ 学生库（`CORE_DATABASE_URL`，缺省回退到 `DATABASE_URL`）。两个 URL 指向同一 SQLite 文件时，每个请求只用一个连接，并启用 WAL，避免两个连接同时写入把库锁住。本地/测试用 SQLite，生产用 MySQL（`mysql+pymysql://`）。上传文件在 `backend/uploads/`（头像与 Forum 配图）。 |
| 不换栈 | 不要改成 Next.js、Nest、微服务或指定云厂商。 |

---

## 2. 两套进程布局

### 本地（开发）

浏览器打开 `http://localhost:5173`。前端 Vite 与后端 uvicorn **分端口**；浏览器直连 8000 的 API。

| 进程 | 命令（摘要） | 端口 |
| --- | --- | --- |
| 前端 | `cd frontend && npm install && npm run dev` | 5173 |
| 后端 | `cd backend`，激活 `.venv`，`uvicorn main:app --reload --port 8000` | 8000 |

对应变量：

- `FRONTEND_ORIGIN=http://localhost:5173`
- `VITE_API_BASE=http://localhost:8000/api/v1`（缺省即此，可不建 `frontend/.env`）

Cookie 跨源：前端 `credentials: 'include'`，后端 CORS 只允许 `FRONTEND_ORIGIN` 且 `allow_credentials=True`。

### 生产（一种已跑通的布局）

浏览器只打 **80**（或之后的 HTTPS 443）。nginx 托管构建好的 `frontend/dist`，并把 API 反代到本机 uvicorn。

| 进程 | 监听 | 职责 |
| --- | --- | --- |
| nginx | `0.0.0.0:80` | 静态页；`/api/`、`/uploads/`、`/health` 反代到 127.0.0.1:8000 |
| uvicorn | `127.0.0.1:8000` | FastAPI，不直接对公网 |

对应变量：

- `FRONTEND_ORIGIN` = 用户打开站点的 origin（协议 + 主机 + 端口，无尾斜杠），须与地址栏完全一致
- 构建前端时 `VITE_API_BASE=/api/v1`（同源，Cookie `Path=/` 才能带上）

uvicorn 工作目录为 `backend/`。systemd（或等价）以非特权用户跑进程即可。

建议 nginx 对 `/api/` 允许较大 body（Forum 配图合计可超过默认 1MB）。

---

## 3. 环境变量

后端读取顺序（`backend/config.py`）：先仓库根 `.env`，再 `backend/.env`。复制模板：`cp .env.example .env`。

缺 `SESSION_SECRET` 或 `DATABASE_URL` 时进程**拒绝启动**。

| 变量 | 必填 | 模板示例 | 作用 |
| --- | --- | --- | --- |
| `DATABASE_URL` | 是 | `sqlite:///./scoop.db` | 新闻/分享内容库（posts/news_blocks/comments/post_likes/audit_events）的 SQLAlchemy 连接。从 `backend/` 启动时，相对路径落在 `backend/scoop.db`。生产填 MySQL 内容库。 |
| `CORE_DATABASE_URL` | 否 | `sqlite:///./scoop.db` | CJ 学生库（users/sessions/subjects/exams/cj_entries）的连接。缺省回退到 `DATABASE_URL`。与 `DATABASE_URL` 相同时按单库处理，每个请求一个连接。生产填 MySQL CJ 库。两库在同一 MySQL 服务器时建议加 `?charset=utf8mb4`。 |
| `SESSION_SECRET` | 是 | `dev-only-change-me` | 签发 / 校验 Cookie `scoop_session`。换密钥会使已有会话全部失效。生产必须换成高强度随机串，不要用模板值。 |
| `FRONTEND_ORIGIN` | 否 | `http://localhost:5173` | CORS 唯一允许源。缺省即本地 Vite。生产改为浏览器实际 origin。 |
| `ADMIN_EMAIL` | 否 | 空 | 小写邮箱，须为 `@basischina.com`。该地址在注册或登录时升为 `super_admin`。留空则无人被自动提拔。不要把真实地址写进仓库。 |
| `MAIL_BACKEND` | 否 | `smtp` | `smtp` 走 SMTP；`console` 只把验证码打到进程日志（仅本地/测试）。生产用 `smtp`。 |
| `SMTP_HOST` | `smtp` 时是 | 空 | 发信邮局的主机名，不是本站地址，也不是 `localhost`。代码用 STARTTLS 连接 `SMTP_PORT`。填学校或邮箱服务商给出的 SMTP 主机。跑 Elegram 的机器只有在本机已经开着同等 SMTP 时才能填它。缺主机时发码接口 `503`。 |
| `SMTP_PORT` | 否 | `587` | SMTP 端口。 |
| `SMTP_USER` | 否 | 空 | SMTP 用户名。 |
| `SMTP_PASSWORD` | 否 | 空 | SMTP 密码。只写 `.env`。 |
| `SMTP_FROM` | 否 | 空 | 发件人地址。缺省则用 `SMTP_USER`。 |
| `CJ_JOURNAL_BASE_URL` | 否 | 空 | 课表站点原点，例如 `https://myclassroomjournal.com`。有值时进程启动后拉取 `GET /public/journal`，之后每小时一次，并写到本地学科目录里对应的课。留空则不拉取。 |
| `CJ_JOURNAL_API_KEY` | 拉取时是 | 空 | 课表接口的 Bearer 密钥。只写 `.env`。缺密钥时提取接口 `503`，不改已有 CJ。 |
| `DEEPSEEK_API_KEY` | 拉取时是 | 空 | DeepSeek 密钥，只清洗已分好的 IC / HW / AN。只写 `.env`。缺密钥时提取接口 `503`。 |
| `DEEPSEEK_MODEL` | 否 | `deepseek-chat` | DeepSeek 模型名。 |

前端构建期（`frontend/.env`，改完须重新 `npm run build` / `npm run dev`）：

| 变量 | 缺省 | 作用 |
| --- | --- | --- |
| `VITE_API_BASE` | `http://localhost:8000/api/v1` | `fetch` 根路径。本地用完整 URL；生产同源反代用 `/api/v1`。 |

前端不读 `SESSION_SECRET`、`DATABASE_URL`、`ADMIN_EMAIL`。

种子脚本另有 `SEED_*`（仅本地灌数，不是运行站点所必需）。

---

## 4. 会话、路径与健康检查

| 项 | 值 |
| --- | --- |
| Cookie 名 | `scoop_session`（HttpOnly、SameSite=Lax、Path=/；schema：生产 HTTPS 应加 Secure） |
| 业务 API | `/api/v1` |
| 健康检查 | `GET /health` → `{"status":"ok"}` |
| 上传对外路径 | `/uploads/...`（后端 StaticFiles；生产由 nginx 反代） |

不要提交 `.env`、`*.db`、`backend/uploads/`。

---

## 5. 验收（只测环境）

1. 给定根目录 `.env` 缺 `SESSION_SECRET` 或 `DATABASE_URL`，当启动后端，则进程失败，不监听业务端口。
2. 给定 `FRONTEND_ORIGIN` 与浏览器打开的源不一致，当前端带 Cookie 调需鉴权接口，则 CORS 或 Cookie 失败，登录回路不通。
3. 给定本地按 README 同时开 Vite 与 uvicorn，当请求 `http://localhost:8000/health`，则返回 `{"status":"ok"}`。
4. 给定生产同源反代，当请求站点 origin 的 `/health` 与 `/api/v1/...`，则打到同一套 uvicorn，且前端包内的 API 根为 `/api/v1`。

不验收：在页面里改 `.env`、运行时热更新 `VITE_API_BASE`、发帖与头像流程。
