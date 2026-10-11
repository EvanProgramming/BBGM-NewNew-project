# 任务看板

主故事：学生注册/登录 → `POST /api/v1/posts` 在 Forum 发帖 → 未登录会话在 Forum 读到同一条。依据 `docs/PRD.md`、`docs/schema.md`、`docs/UI_BLUEPRINT.md`。

不包含 PRD Won't：教务/选课、推荐与关注图谱、原生 App/直播/支付、AI 审核、向量库与微服务。不包含 Should：检索接口、改删帖、评论、找回密码、审计查询 API、下架后台。

勾选约定：做完且可测再勾。不要用静态假界面冒充联调完成。

---

## 后端

### 基建

- [x] `GET /health` 已在 `backend/main.py`，返回 `{"status":"ok"}`
- [x] 在 `backend/` 读取 `.env`：`DATABASE_URL`、`SESSION_SECRET`、`FRONTEND_ORIGIN`；缺 `SESSION_SECRET` 时启动失败（不要把密钥写进源码）
- [x] 用 `FRONTEND_ORIGIN` 配 CORS：允许该源、`allow_credentials=True`（Cookie 联调需要）
- [x] 统一错误包络：`{"error":{"code","message","fields":[{"field","message"}]}}`，与 schema 状态码表一致；成功响应不要包 `{data:...}`

### 持久化（M8，勿只写内存）

- [x] 按 `DATABASE_URL` 接入存储（SQLite 即可）；表：`users`（id、email 唯一小写、password_hash、display_name、created_at）、`sessions`（凭证、user_id、可作废）、`posts`（schema Post 字段）、`audit_events`（actor_id、action、post_id、at）
- [x] 不建业务无关表；不提交真实 `.env`

### 鉴权

- [x] Cookie 名 `scoop_session`：HttpOnly、SameSite=Lax、Path=/；登录/注册 `Set-Cookie`，退出清除
- [x] `POST /api/v1/auth/register`：校验 `email`（邮箱、小写）、`password`（8–128）、`display_name`（1–40）；`201` + UserPrivate；邮箱占用 `409 email_taken`；校验失败 `422`；写入失败 `503 storage_unavailable`
- [x] `POST /api/v1/auth/login`：body `email` `password`；成功 `200` + UserPrivate + Cookie；错误凭据 `401 invalid_credentials`（文案不区分用户不存在/密码错）；缺字段 `422`；读库失败 `503`
- [x] `POST /api/v1/auth/logout`：需会话；`204` 无 body 并清 Cookie；无会话 `401 unauthenticated`
- [x] `GET /api/v1/me`：需会话；`200` UserPrivate（`id` `email` `display_name` `created_at`）；无会话 `401`

### 帖子

- [x] `GET /api/v1/posts`：公开。Query `category?` `page`（默认 1）`page_size`（默认 20，最大 50）。无 category 按 `created_at` 降序且只含 `news` `sports`；有则只返回该枚举（含 `forum`）。`200` `{items, page, page_size, total}`；`items[]` 为 PostSummary。非法分页 `400 bad_request`；非法 category `422`；读失败 `503`
- [x] `GET /api/v1/posts/{post_id}`：公开。合法 UUID 且存在则 `200` PostDetail（含 `body`）；非 UUID `400`；不存在 `404 not_found`；读失败 `503`
- [x] `POST /api/v1/posts`：需会话。校验 `title` `body` `category`。`student` 只能发 `forum`。Forum 可 multipart 带 `images`（最多 4 张），与帖、审计同一事务。作者取当前用户。成功 `201` PostDetail，`status=published`。无会话 `401`；校验失败 `422` 且不落 `published` 行；写入失败整笔回滚 `503`
- [x] `GET /api/v1/me/posts`：需会话。当前用户的帖，分页同列表。`200` 列表；无会话 `401`；非法分页 `400`；读失败 `503`
- [x] 本版不实现 `PATCH`/`DELETE /api/v1/posts/{id}`：误调用返回 `405`（覆盖 PRD AC12：他人无法改删）
- [x] 不实现 `GET /api/v1/audit-events`

### 后端测试（契约，非全量 E2E 平台）

- [x] pytest：注册→登录→发帖→未带 Cookie 的 GET 列表/详情能看到该帖；进程内重开存储后仍能登录并读帖（AC1–7、17 的 API 侧）
- [x] pytest：错误凭据 401；未登录 POST 帖 401；空标题/非法栏目/活动缺地点 422 且库无该行；模拟存储失败 503（AC8–11、13）
- [x] pytest：公开 GET 不要求 Cookie；`/me` 与 POST 帖要求 Cookie

---

## 前端

技术：`frontend/` React + Vite + Tailwind。先 Mock 后换真实 fetch。字段只绑 schema。不要引入 `image_url` / `featured`。

### Mock 阶段（界面可点，数据来自 `docs/schema.md` 第 2 节）

- [x] 增加路由（如 React Router）：蓝图中的 `/` `/news` `/sports` `/forum` `/opinion` `/posts/:postId` `/me/posts` `/sign-in` `/register` `/about` `/contact`；旧 `/community` `/submit` 重定向 `/forum`，`/dorm-life` `/events` `/photo` 重定向 `/`
- [x] `PaperShell`：顶栏 ABOUT/CONTACT、账号区、本地 `Today:`；报头搜索壳 + `Elegram` + Community hosted；标语；导航 NEWS / SPORTS / FORUM / OPINION。字体 Playfair Display + Inter；色 `#1A4FBF`、图框 `#D6DEEE`、黑线
- [x] 搜索提交：报头下静态 “Search comes in a later version.”（不调检索 API）
- [x] 访客：`SIGN IN`。已登录 Mock：`display_name`、`MY POSTS`、`SIGN OUT`
- [x] 首页按蓝图槽位填 Mock `GET /posts` 的 `items[0]`…`[15]`，缺槽空态不循环灌数。Photo/Track/Art 静态空壳
- [x] 栏目页：`category` 请求对应枚举；行绑 `title` `excerpt` `category`；活动行加 `starts_at` `location`。空态、加载横线、错误条（用 Mock 错误 JSON）
- [x] `/opinion`：固定空态，**不请求**非法 category
- [x] 详情：`category` `title` `author.display_name` `created_at` `body`。Mock 404 显示 “Story not found.”
- [x] `/forum`：右下角加号打开浮层 `title` `body` 与配图，`Publish`。未登录加号跳 `/sign-in?next=/forum`。422 写在 `error.fields[]` 对应输入下
- [x] `/me/posts`：Mock 成功列表与 `total===0` 空态

### News 独立投稿扩展（M28）

- [ ] 保留 `/news/drafts` 固定版位编辑器，新增 `/news/submit`（Draft）独立文章投稿
- [ ] News 文章支持 Sports / Dorm / Scoop 多选、最多 4 张图片；分类筛选嵌入现有 Front Page
- [ ] Draft 只保存原稿；Design 分开选择 Original / API design 并预览
- [ ] 配置 `OPENAI_API_KEY` 时调用 AI，无密钥时明确显示本地段落整理
- [ ] Editor 从 Design 送审；仅 `super_admin` 可审核或从 Design 发布，公开 API 仅返回已发布文章
- [x] `/sign-in` `/register`：窄表；Mock `invalid_credentials` / `email_taken` 展示。`/about` `/contact` 静态稿
- [x] 加载：图框保留，标题位灰线，不挡报头转圈。错误：`error.message` 红字，不用 toast、不用断网假数据

### 真实 API 阶段

- [x] `credentials: 'include'` 调 `http://localhost:8000/api/v1`（或环境变量中的后端源）
- [x] 启动 `GET /api/v1/me`：200 用 `display_name`；401 当访客，不当错误条
- [x] 首页/栏目/详情改真实 GET；Forum 右下角加号发帖，未登录 `/sign-in?next=/forum`
- [x] 登录/注册/退出对接真实 POST；成功跟 `next` 或 `/`
- [x] Publish 对接 `POST /api/v1/posts`；201 跳 `/posts/{id}`；401 去登录；422 字段错误；503 表单顶 `error.message`，**不**乐观插入首页
- [x] 我的帖子对接 `GET /api/v1/me/posts`；401 去登录
- [x] 删除或隔离 Mock 模块，生产路径不得再读死数据

---

## 联调

- [x] 前端 dev（5173）与后端（8000）同时开；CORS + Cookie 跨源可带上 `scoop_session`
- [x] 浏览器验证：注册 Jordan 类账号 → 登录 → 在 Forum 发帖 → 无痕窗口打开 Forum 能看到标题与详情正文
- [x] 编辑可向 News / Sports 发稿；学生向校报发帖被拒；Forum 缺标题停留且库无新帖
- [x] 错误凭据无法进入发帖；未登录 POST 被拒；Forum 非法配图停留在 composer 且库无新帖
- [x] 重启 uvicorn 后原账号仍能登录、帖仍在（证明不是前端内存）
- [x] Mock 开关关闭后，清空业务数据仍能走通注册发帖，而不是只显示 schema 示例三条

---

## 验收

对照 PRD §4，在联调环境勾选（失败路径必须测）。

| AC | 内容 | 任务对应 | 结果 |
| --- | --- | --- | --- |
| 1 | 注册后可用该邮箱密码登录 | 后端 register/login + 前端注册页 | [x] |
| 2 | 登录后可在 Forum 发帖 | `GET /me` + `/forum` | [x] |
| 3 | 发帖得详情 URL，`published`，作者为当前用户 | `POST /posts` | [x] |
| 4 | 另一未登录会话在 Forum 列表/详情看到同一帖；首页不含该 Forum 帖 | 公开 GET | [x] |
| 5 | 编辑可向 News / Sports 发稿 | 校报 POST | [x] |
| 6 | 重启后帖与账号仍在 | 持久化 | [x] |
| 7 | 「我的帖子」能看到并进详情 | `GET /me/posts` | [x] |
| 8 | 错误密码不建会话 | `401 invalid_credentials` | [x] |
| 9 | 未登录发帖被拒 | `401` + 跳转登录 | [x] |
| 10 | 缺标题/正文/栏目或非法栏目不落库 | `422` | [x] |
| 11 | （已删）活动缺时间或地点 | — | 不适用 |
| 12 | 用户 B 不能改删 A 的帖 | `405` 无改删接口 | [x] |
| 13 | 存储失败不展示成功、列表无该帖 | `503` | [x] |
| 14 | 桌面 Chrome / Safari / Firefox 或 Edge 近两版走通 AC2–5 | 手工 | [x] Chrome 152 |
| 15 | 栏目列表与详情首屏（无第三方嵌入）约 3s 内可读 | 手工，本地/校园网 | [x] 列表 ~0.7s / 详情 ~50ms |
| 16 | 约 50 会话、栏目 100 帖仍能打开列表与详情 | 可插数据后手工点开，不做压测平台 | [x] 50 会话、news 102 帖 |
| 17 | 不得只靠前端内存通过 AC6 | 重启后端复测 | [x] |

自动化范围：上列后端 pytest 契约测试。不要求第一周上全量浏览器 E2E 平台。不验收推荐效果、断网伪装、假数据路演。

---

## 进行中约定

1. 范围变更先改 `docs/PRD.md` / `docs/schema.md` / `docs/UI_BLUEPRINT.md`，再改代码；不要在实现里发明第三套字段。
2. 同一任务连续失败：缩小复现步骤或人工看网络/存储日志，禁止用静态 Mock 界面勾成「已完成」。
3. 一次只打通主路径（注册-登录-发帖-被看见），再补活动字段与错误码，不要并行做 Should 功能。
4. 密钥只在 `.env`；示例在 `.env.example`。
