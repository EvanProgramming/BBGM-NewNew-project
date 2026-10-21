# Elegram

由 Tori Zhao、Jason Fang 创立。网站由 Leo Gao、Ben Lyu、Dewey Peng、Tori Zhao 搭建。校报由 Media Club 供稿。登录发帖、按栏目阅读。

> 第一版范围以 `docs/PRD.md`、`docs/schema.md`、`docs/UI_BLUEPRINT.md` 为准。

## 一句话定位

给同学一个可登录的校园站点：既能按栏目看到 News，也能自己在 Forum 发帖，把正在发生的事发出来、被看见。

## 问题

- 校园信息散落在群聊、海报和口头通知里，活动（宿舍、体育、大型活动）不容易被系统看到。
- 现有校官方渠道偏单向通知，学生很难自己发帖、跟帖，缺少「知乎式」的校园讨论入口。
- 学生媒体若只有编辑发稿、没有登录投稿，普通学生进不了内容循环。
- 活动预告和日常帖子混在一起时，读者分不清「要不要去」和「值得一看」。
- 截稿式校报能做好头条，但对即时宿舍生活、比赛结果、临时活动反应慢。

## 用户

第一版面向日常阅读和发帖的人。创始人是 Tori Zhao、Jason Fang。网站由 Leo Gao、Ben Lyu、Dewey Peng、Tori Zhao 搭建。校报由 Media Club 供稿。

- 读者：想快速知道「今天校园有什么」、宿舍和体育分别发生了什么。
- 发帖学生：有账号后能发帖，不需要先成为编辑。
- 活动组织者（学生）：需要把宿舍活动、体育赛事、大型活动放到对应栏目。
- 栏目编辑（若授予 `editor`）：按板块写 News 草稿，经超级管理员同意后才出现在 News 上。不阻塞普通同学在 Forum 发帖。

## 解决方案（第一版）

1. **登录进站**：学生用账号进入站点，发帖和投稿绑定身份。没有登录仍可浏览公开内容；没有登录则发帖回路不成立。
2. **按栏目看校园**：首页与导航分开呈现 News、Forum，而不是一个无分类信息流。
3. **学生发帖**：登录后在 Forum 发帖（标题、正文、可选配图），帖子供同学阅读。这是第一版的核心闭环，不依赖模型或推荐算法；没有大模型产品仍成立。
4. **News 审稿**：编辑按板块提交草稿，超级管理员同意后才公开。第三方嵌入（如 Track of the Day 的 Spotify）只承担「边栏点缀」。

## 范围

### 第一版包含

- 学生登录与退出
- 公开浏览首页与栏目（News、Forum）
- 登录后发帖（Forum 讨论或编辑发校报稿、查看自己的帖）
- 基础导航与检索入口（与页面稿中的 Search、栏目导航对齐）

### 明确不做（建议，待 1.2 确认）

- 不做全校官方教务 / 选课 / 成绩系统
- 第一版不做知乎级推荐算法、关注社交图谱、付费专栏
- 不做原生 App、直播、票务支付
- 不把向量库、微服务、特定云厂商写进第一版承诺
- 不默认上线未评估的 AI 写作 / 审核模型

## 技术与依赖（已知部分）

**已确定**

- 产品形态：校园 Web 站点（页面稿运行在本地浏览器中）
- 必须有的能力：账号登录、学生发帖、按栏目展示内容与活动

**开放问题**

- 1.1 / 1.2 未做：竞品对照、Must / Won't、审核责任尚未锁定
- 登录方式未定：学校邮箱、学号、校园 SSO，还是站点自建账号
- 发帖是否先审后发、谁来审核、是否允许匿名
- 「知乎式社区」与「学生媒体校报」两条形态如何并存（页面稿偏后者，需求偏前者）
- 「其他」具体包含哪些栏目（Opinion、Photo、Student Art 是否第一版就做）
- 数据存在哪里、是否必须接学校现有系统：未评估，不在此写死

## 本地运行

复制环境变量模板（不要把填好的 `.env` 提交进仓库）：

```bash
cp .env.example .env
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

浏览器打开终端提示的地址（默认 http://localhost:5173）。报头、栏目、发帖与登录已接 `http://localhost:8000/api/v1`（Cookie `credentials: 'include'`）。首页按真实列表填槽，没有帖时走空态，不读 schema 示例三条。

### 后端

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

启动前请在仓库根目录的 `.env` 里填好 `DATABASE_URL`、`SESSION_SECRET`、`FRONTEND_ORIGIN`（可先 `cp .env.example .env`）。缺 `SESSION_SECRET` 时进程会拒绝启动。

健康检查：http://localhost:8000/health 应返回 `{"status":"ok"}`。业务接口在 `/api/v1`（注册、登录、帖子列表/详情、发帖、我的帖子）。

契约测试：

```bash
cd backend
source .venv/bin/activate
pytest
```

Windows 激活虚拟环境请改用 `.venv\Scripts\activate`。

## 参考

- 运行环境（端口、`.env`、本地与生产布局）：`docs/RUNTIME_REQUIREMENT.md`
- 产品参照：知乎式发帖（学生自己发帖、按话题阅读）；栏目为 News / Forum
- 页面稿中出现、第一版不绑定的外部能力：Spotify 嵌入（Track of the Day）
- 规范文档、学校官网、正式竞品名单：尚未提供
