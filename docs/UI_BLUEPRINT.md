# UI 蓝图：Elegram 印刷版

选定 2.3A **提案 1** 的版式（报头、头条、栏目）。产品名 **Elegram**。由 **广东智云建材有限公司** 所有并运营。字段只绑定 `docs/schema.md`；没有封面图、featured 标记、检索接口——图框是 CSS 占位，不是数据。

---

## 1. 信息架构

多页路由，报头+导航在所有页面保留（含登录/注册）。无底部 Tab。管理员用户列表是站点内一页，不是独立后台套件。

| 路由 | 页面 | 鉴权 | 数据 |
| --- | --- | --- | --- |
| `/` | News（报头版式） | 公开 | `GET /api/v1/posts?page=1&page_size=20`（无 `category`，只含已发布 News） |
| `/` | News Front Page 杂志版式 | 公开 | `GET /api/v1/news/articles?topic=all|sport|dorm|scoop`，数据映射到首页既有主图、侧栏与故事版位 |
| `/news/drafts` | News 固定版位草稿 | 需 `editor` 或 `super_admin` | 保留既有分板块草稿与审核 |
| `/news/submit` | Draft | 需 `editor` 或 `super_admin` | 创建 / 编辑独立文章并保存原稿，不排版、不发布 |
| `/news/design` | Design 工作区 | 仅 `super_admin` | 选择 Original 或 API design 并预览后发布。`editor` 打开此地址回到首页 |
| `/news/review` | News 审核 | 仅 `super_admin` | 待审队列；在独立预览窗批准发布或退回 |
| `/news/articles/:id` | News 文章详情 | 公开 | `GET /api/v1/news/articles/{id}` |
| `/sports` | 旧路径 | — | 重定向到 `/` |
| `/forum` | Forum 推荐 | 公开 | `GET /api/v1/posts?category=forum&feed=recommended`。分数 `0.6 × 赞 + 0.4 × 评论`，取前 10。绑 `author.avatar` `title` `author.display_name` `excerpt` `created_at` `images[0]` `reply_count` `like_count` `liked` |
| `/forum/latest` | Forum 最新 | 公开 | `feed=latest`。按时间前 10 |
| `/forum/all` | Forum 所有 | 公开 | `feed=all`。按时间分页 |
| `/forum/mine` | Forum 我的 | 需登录 | `feed=mine`。只列当前用户已发布的 Forum 帖。未登录去 `/sign-in?next=/forum/mine`。作者可在卡片和详情删除自己的帖 |
| `/cj` | CJ 角色入口 | 需登录 | 默认入口按 `super_admin`、`teacher`、`student` 取 `roles` 里靠前的一个。已经打开某个入口时，只要 `roles` 含该入口要求的身份就留下 |
| `/cj/student` | 学生端月历 | 需 `student` | 每一行整周链到 `/cj/student/week?start=`；Period 选择存在浏览器本地 |
| `/cj/student/week` | 学生端周视图 | 需 `student` | `GET /api/v1/cj?week_start=`，周一至周五五列同时展示 Period 1–8，并单列考试安排 |
| `/cj/student/day` | 学生端旧单日页 | 需 `student` | 保留旧链接兼容，不作为月历主入口 |
| `/cj/teacher` | 老师端 | 需 `teacher` | 只读取和写入超级管理员分配给该老师的唯一学科，包括该学科 CJ 与考试；不显示其他学科。每日 CJ 可上传作业照片，`POST /api/v1/cj/recognize` 后把 IC / HW / A 写入所选日期，并标出裁切补全 |
| `/cj/admin` | CJ 完整管理端 | 仅 `super_admin` | 管理全部 CJ、考试与老师学科分配；可连接 Teams 并在预览确认后写入当周 IC / HW / A。不再使用共享口令 |
| `/cj/admin/student-preview` | 学生端只读预览 | 仅 `super_admin` | 与学生周视图读取同一份 CJ，供管理端在独立标签页验证保存结果；不放宽学生端路由权限 |
| `/cj/day` `/cj/week` | 旧路径 | 需 `student` | `/cj/week` 转到学生端周视图；`/cj/day` 保留单日兼容页 |
| `/opinion` | 栏目占位 | 公开 | **不请求** `category=opinion`（枚举外会 422）。固定空态。 |
| `/community` `/submit` | 旧路径 | — | 重定向到 `/forum` |
| `/dorm-life` `/events` `/photo` | 旧路径 | — | 重定向到 `/` |
| `/posts/:postId` | 帖子详情 | 公开 | `GET /api/v1/posts/{post_id}`；Forum 另 `GET .../comments` |
| `/me/posts` | 我的帖子 | 需登录 | `GET /api/v1/me/posts` |
| `/me/avatar` | 选/上传头像 | 需登录 | `PUT` / `POST /api/v1/me/avatar` |
| `/me/password` | 修改密码 | 需登录 | `PUT /api/v1/me/password`（`current_password` `password`） |
| `/admin/users` | 用户与角色 | 需 `roles` 含 `super_admin` | `GET /api/v1/admin/users`；`PATCH` 改 `roles` 或 `muted`；`DELETE` 删用户 |
| `/paper` | 旧路径 | — | 重定向到 `/` |
| `/system` | System 通知 | 需登录 | `GET /api/v1/me/notices`。无回复框 |
| `/sign-in` | 登录 | 访客 | `POST /api/v1/auth/login` |
| `/register` | 注册 | 访客 | `POST /api/v1/auth/email-codes`（`purpose=register`）后 `POST /api/v1/auth/register` |
| `/reset-password` | 找回密码 | 访客 | `POST /api/v1/auth/email-codes`（`purpose=reset`）后 `POST /api/v1/auth/password-reset` |
| `/about` | 静态稿。写明由广东智云建材有限公司所有，并给出联系邮箱。另有 Contributors：本网站是由 Tori zhao, Leo Gao, Ben lu, Dewey Peng 制作的 | 公开 | 无 API |
| `/contact` | 静态稿。联系方式为该超管邮箱 | 公开 | 无 API |
| `/terms` | 用户协议 | 公开 | 无 API。中英跟 System 菜单里的总开关走，本页没有单独的语言按钮。直接打开此地址是整页。站内顶栏与注册勾选不跳到本页，改为当前页浮层 |

**全局壳 `PaperShell`**

- 顶栏一行，从左到右：`SYSTEM`、登录后的 `SETTINGS`、登录后的 `MY POSTS`、`NOTICES`。`SYSTEM` 点开菜单：`ABOUT`、`TERMS`（当前页浮层，不切路由）、`CONTACT`，以及一项中英切换（当前英文时写「中文」，当前中文时写「English」）。点一下切换并收起菜单。选择记在浏览器本地 `elegram_lang`，默认英文，不进接口。字标 Elegram 不翻译。Forum 帖子的标题、正文、摘要和评论保持原文。News 稿件正文和已保存的 CJ 文字也按库存原文显示。`SETTINGS` 点开菜单：`AVATAR`（`/me/avatar`）、`PASSWORD`（`/me/password`）；`roles` 含 `super_admin` 再加 `USERS`（`/admin/users`）。`MY POSTS` 直接去 `/me/posts`。`NOTICES` 直接去 `/system`（通知页，顶栏不叫 System）。菜单点外面、按 Esc 或选中一项后收起。子项不常驻顶栏。`TERMS` 浮层可滚动，点遮罩或关闭即收起，仍停在打开前的页面。
- 顶栏右侧：本地日期 `Today: {formatted local date}`（不是 schema 字段）。`401` = 访客，日期前显示 `SIGN IN`（去 `/sign-in`），不显示 Settings 与 My Posts。`200` = 已登录，日期前显示头像（`avatar`）、`display_name`、`SIGN OUT`。启动时 `GET /api/v1/me`。登录后同一套 live refresh（约 4 秒）再拉 `/me`，超管改 `roles` / `muted` / 删号后顶栏与导航跟着变，不必整页刷新。顶栏不放 `DRAFTS`。
- 列表同步：首页 / Forum / 帖详情已 live refresh。`/admin/users`、`/news/drafts` 列表、`/system`、`/me/posts` 同样轮询，超管或其他人刚做的改动会进当前页。打开中的草稿编辑框不自动覆盖，以免冲掉未保存正文。
- 报头：左搜索框（外形保留；提交不调接口，在报头下出一条静态说明）。中：斜体衬线字标 `Elegram` 链回 `/`。右：静态「OWNED BY / 广东智云建材有限公司」。
- 标语静态：`YOUR STORIES. YOUR VOICE. YOUR PAGE.`
- 导航：`NEWS`（`/`）`FORUM` `CJ` `OPINION`。`CJ` 与 `FORUM` 同一行，链到 `/cj`。`roles` 含 `editor` 或 `super_admin` 时，在 NEWS 之后另见 `DRAFT`（`/news/submit`）。`DESIGN`（`/news/design`）只在 `roles` 含 `super_admin` 时出现。超级管理员从 Design 进入审核队列或直接发布。当前路由下划黑线。无 `SUBMIT`，无单独的 News 列表项。分板块草稿页仍是 `/news/drafts`，不放在主导航。旧 `/news` 重定向至首页。Forum 发帖在栏目页内。
- CJ 欢迎屏：`/cj` 仍只按角色跳到学生、老师或管理页。跳转之后，若这次登录还没看过欢迎屏，内容区左上角显示大号衬线 “Welcome, {display_name}”（中文 “欢迎，{display_name}”），约 1.8 秒淡入，淡入结束后再停一会儿，大约 3.2 秒后才渲染课表。标记在 `localStorage`，键带用户 `id`。重新登录或退出时清除。淡入结束前离开 CJ 不写入标记。已在 CJ 内换日期或课程不再播放。
- 会等待接口的按钮：请求从发出到返回期间，按钮文字旁显示转圈，并且不可再点。页面初次加载仍用原来的“正在读取”文案，不盖整页。
- 页脚声明（非 schema）：`Owned by 广东智云建材有限公司.`

**栏目枚举 → 导航文案（展示层，不是新字段）**

`news` → NEWS；`forum` → FORUM。

---

## 2. 设计规范

不用组件库。HTML + CSS（可用 Tailwind utility）。字体：Playfair Display（报头/标题）、Inter（导航/表单/正文 UI）。

| 角色 | Token / 值 |
| --- | --- |
| 页底 | `bg-white` `#FFFFFF` |
| 正文 | `text-neutral-900` `#111111` |
| 品牌蓝 / kicker / 链接 | `text-[#1A4FBF]` |
| 图框占位 | `bg-[#D6DEEE]` 直角矩形，无圆角无阴影 |
| 分割 | `border-black` 1px；栏目名旁 2px 黑线拉满 |
| 错误 | `text-red-700`，表单顶或字段下；不用 toast 盖报头 |
| 成功 | 发帖成功不在原页刷绿条，直接进详情 |
| 次要说明 | `text-neutral-500` 小字 |

**层级**

- 报头 `Elegram` 斜体衬线蓝
- FEATURED 主标题：衬线 48–64px
- 栏目名 `LATEST` / `FEATURES`：衬线约 28px + 黑线
- 卡片标题：衬线 20–28px
- kicker：Inter 11px 全大写蓝色 tracking
- excerpt / 表单：Inter 14–16px
- 日期：Inter 12–13px `text-neutral-500`

**形态**

- 圆角：校报 0 或最多 2px（`Publish` 按钮）。**Forum 列表卡**可用大圆角模块底（`rounded-2xl`），不悬浮、无关注/分享/关闭。
- 按钮：黑底白字，小 caps；链接按钮无填充
- 密度：印刷空白；卡片不悬浮、不 hover 抬起
- 输入：底边一条黑线或 1px 黑框，不要 iOS 大圆角
- 动效：无

**禁止绑定的幽灵字段：** `image_url`、`cover`、`featured`、`kicker`、`caption`、`photo_credit`、Spotify id、`is_activity`、`starts_at`、`location`。校报图框与 Photo of the Day / Track of the Day / Student Art 为静态壳。Forum 只绑 schema 的 `images[]`。

---

## 3. 状态

`GET /me` 的 `401` 是访客常态，**不是**错误条。

### 3.1 News `/`

| 状态 | 表现 |
| --- | --- |
| 加载 | 报头先出。图框已是 `#D6DEEE`；标题位一条 2px `bg-neutral-200` 横线。不挡报头转圈。 |
| 成功 | 将 `items` 按更新时间已排序使用（服务端降序）。槽位按下表取 **互不重复的下标**；缺槽显示该槽空态，不循环填充。停留时约每 4 秒再请求 `page=1`（页签隐藏暂停），用新的 `items` 填槽；不转圈。后台失败保持当前槽，不盖错误条。 |
| 空 | `total === 0`：版面槽位、LATEST / FEATURES 等栏目标题和右侧静态栏仍在。已登录学生链到 `/forum`，编辑链到 `/news/drafts`。 |
| 错误 | `503` / 其他：主栏顶 `ErrorBanner` ← `error.message`（如 Could not save… 类存储文案以响应为准）。不造假列表。 |

**News 槽位 ← `items[i]`（PostSummary）**

| 槽 | 下标 | 展示字段 |
| --- | --- | --- |
| FEATURED 大图+大标题 | `[0]` | `category`（kicker）、`title`、`excerpt` |
| 右上两条 | `[1]` `[2]` | 同上 |
| 右下较宽一条 | `[3]` | 同上 |
| LATEST 左大 | `[4]` | 同上 |
| LATEST 右三条 | `[5]` `[6]` `[7]` | 同上 |
| FEATURES 左三紧凑 | `[8]` `[9]` `[10]` | `category` `title` `excerpt` |
| FEATURES 右大 | `[11]` | `category` `title` `excerpt` `created_at` |
| CAMPUS LIFE 三列 | `[12]` `[13]` `[14]` | `category` `title` `excerpt` `created_at` |
| SPECIAL FEATURE | `[15]` | `category` `title` `excerpt` `created_at` |

点击任一故事 → `/posts/{id}`。没有稿件的槽保留图框与占位标题。Photo of the Day / Track of the Day / Student Art：静态标题+空图框+固定说明（无 schema）。搜索提交：报头下静态 “Search comes in a later version.”

### 3.2 栏目页 `/forum` `/opinion`

| 状态 | 表现 |
| --- | --- |
| 加载 | 栏目大标题+黑线先出；下列三行图框+横线。 |
| 成功 | 校报 `items[]` 逐行：`category` `title` `excerpt`。`total > page * page_size` 时底栏 `Older stories` 请求 `page+1`。 |
| Forum | **不用 StoryRow**。每条独立模块卡：`author.avatar`、`author.display_name`、`created_at`、`title`（链详情）、`excerpt`、有则 `images[0]`。标题和摘要按卡片宽度换行，长串不撑出灰色卡片。底栏：气泡图标 + `reply_count`（链 `/posts/{id}`）；拇指图标 + `like_count`（已登录切换赞；游客去 `/sign-in?next=/forum`）。**不**展示 `reply_preview`。 |
| 发帖 | Forum：右下角固定蓝色圆形加号。已登录点开浮层表单；未登录加号去 `/sign-in?next=/forum`。`opinion` 无发帖。News 不在本页发稿。独立投稿在导航 `DRAFT` / `DESIGN`，分板块草稿在 `/news/drafts`。 |
| 空 | `items.length === 0`：图框保留，“No stories in {栏目名} yet.” 不链独立发帖页。 |
| 栏目 | Forum 主导航下：推荐、最新、所有、我的。当前项字色 `#1A4FBF` 并带下划线。推荐与最新不显示 Older stories。我的需要登录，卡片上作者可删除该帖，确认后该卡消失。 |
| 停留 | 约每 4 秒再请求当前栏目 `page=1`（页签隐藏暂停）。最新与所有：新帖出现在列表顶部。推荐：0 赞且 0 评论的新帖不插到第一位。所有已点过的 Older 页保留。Forum 卡上的 `reply_count` / `like_count` / `liked` 随这次响应更新。不转圈；后台失败不盖错误条。首次加载失败后若拉到数据则清错误。 |
| 错误 | 栏目名下 `ErrorBanner` ← `error.message`。`opinion` 不发请求，直接空态句。 |

### 3.3 详情 `/posts/:postId`

| 状态 | 表现 |
| --- | --- |
| 加载 | 图框+标题横线。 |
| 成功 | kicker←`category`；标题←`title`；byline←`author.display_name`、`created_at`。Forum 正文←`body`。News 按 `blocks[]` 分段渲染 `heading` 与 `body`，不展示未同意板块。 |
| Forum | `category===forum` 时正文放在与列表相同的灰色卡片里，按卡片宽度换行，长串不撑出卡片。正文下有与列表相同的拇指（`like_count` / `liked`；未登录去登录），并请求 `GET /comments`。楼主与每条评论显示 `author.avatar`。有 `images[]` 则在正文下展示实图，不用校报占位图框。评论显示 `author.display_name`、`body`，同样按栏宽换行。不显示楼号，没有「新楼层」，也不能回复某一条评论。已登录显示评论框；未登录显示去登录。校报详情**不**请求评论、不加拇指，图框仍是 CSS 占位。停留时约每 4 秒再请求详情与已加载的评论页；有新评论则追加。输入框内容不丢。后台失败不盖错误条。精选表不在本页。 |
| 删帖 | `roles` 含 `admin` 或 `super_admin` 时显示 `Delete`。Forum 帖的作者在自己的详情也显示 `Delete`。确认后 `DELETE /api/v1/posts/{id}`。管理员删 News 回 `/`，删他人的 Forum 回 `/forum`；作者删自己的 Forum 回 `/forum/mine`。`403` 用 `ErrorBanner`。 |
| 撤回 News | 已发布且带 `news_categories` 的文章，`roles` 含 `admin` 或 `super_admin` 时另显示 `Withdraw`。确认后 `POST /api/v1/news/submissions/{id}/withdraw`，成功回首页。文章不再公开，原稿回到 Draft。`403` 用 `ErrorBanner`。 |
| 空 / 404 | `error.code === not_found`：衬线 “Story not found.” 无假文。 |
| 错误 | `503`/`400`：`ErrorBanner` ← `error.message`。 |

### 3.4 栏目内发帖

无独立 `/submit` 页。旧路径重定向 `/forum`。

| 状态 | 表现 |
| --- | --- |
| 入口 | Forum：右下角加号。已登录打开浮层（`title` `body` 配图，可关）；未登录去 `/sign-in?next=/forum`。News 不在栏目页发稿。 |
| 学生 / Forum | `title` `body` 与可选配图（最多 4 张，可预览、可删）。一次 `POST /posts`（有图用 multipart）。成功进 `/posts/{id}`。 |
| 编辑 / 超级管理员 | News 草稿见 3.8。Forum：同学生。 |
| 校验失败 422 | 表单顶不出现成功。`error.fields[]` 按 `field` 写到对应输入下。无 `fields` 时顶栏用 `error.message`。非法配图不落帖。 |
| 401 | 清本地登录态，去 `/sign-in?next=` 当前栏目。 |
| 503 | 表单顶 `ErrorBanner` ← `error.message`。输入保留。 |
| 成功 201 | Forum：去详情。 |

### 3.5a 修改密码 `/me/password`

| 状态 | 表现 |
| --- | --- |
| 401 | 去 `/sign-in?next=/me/password`。 |
| 首次 | 窄表：`current_password`、新 `password`。密码框不走系统 Strong Password。 |
| 422 | 字段下 ← `error.fields[]`。 |
| 503 | 表单顶 `ErrorBanner`。 |
| 成功 | 「Your password was updated.」链回 `/`。 |

### 3.5 我的帖子 `/me/posts`

| 状态 | 表现 |
| --- | --- |
| 401 | 去 `/sign-in?next=/me/posts`。 |
| 加载 | 与栏目行相同横线。 |
| 成功 | 行：`title` `excerpt` `category` `created_at`。点行 → `/posts/{id}`。 |
| 空 | `total === 0`：“You have not published yet.” 学生链 `/forum`；编辑链 `/news/drafts`。 |
| 503 | `ErrorBanner` ← `error.message`。 |

### 3.6 登录 `/sign-in` · 注册 `/register`

| 状态 | 表现 |
| --- | --- |
| 首次 | 窄表。登录：`email` `password`，表下链 `/reset-password`（Forgot password）。注册：`display_name` `email` `password`、「发送验证码」、`code`，以及勾选同意用户协议。发送按钮下始终写明：正在把验证码发到这个邮箱，验证码 2 分钟后失效。发送成功后按钮进入 60 秒倒计时且不可再点，剩余秒数记在 `sessionStorage`（按邮箱和 `purpose=register`）。改邮箱后按新邮箱重算倒计时。点 “user agreement” 在当前页打开浮层，不离开注册表。浮层内 “I agree” 勾选并关闭；点关闭或遮罩则勾选不变。未勾选不提交；勾选后 body 带 `accept_terms: true`。注册与找回密码的密码框不走系统 Strong Password / 浏览器自动生成，由用户自己输入。 |
| 422 | 字段下 ← `error.fields[]`。非 `@basischina.com` 只显示 email 错误，不进入等待验证码态。`accept_terms` 错误显示在勾选下方。 |
| 401 `invalid_credentials` | 表单上沿 ← `error.message`（Email or password is incorrect.）。 |
| 409 `email_taken` | `email` 下 ← `fields[].message` 或 `error.message`。 |
| 503 | 表单顶 ← `error.message`。 |
| 成功 | 写入本地用户（`id` `email` `display_name` `roles` `created_at`）。有 `next` 则回该路径，否则 `/`。 |

### 3.6b 找回密码 `/reset-password`

| 状态 | 表现 |
| --- | --- |
| 首次 | 窄表：`email`、「发送验证码」、`code`、新 `password`。发送按钮下始终写明正在把验证码发到这个邮箱，2 分钟后失效。发送成功后按钮 60 秒内不可再点，剩余秒数记在 `sessionStorage`（按邮箱和 `purpose=reset`）。仍保留“若该邮箱有账号，验证码已发出”，不泄露邮箱是否注册。 |
| 422 | 字段下 ← `error.fields[]`。非校内邮箱只显示 email 错误。 |
| 204 | 提示已更新，链去 `/sign-in`。不自动登录。 |
| 503 | 表单顶 ← `error.message`。 |

### 3.7 用户列表 `/admin/users`

非 `super_admin`：不渲染表，去 `/`。`401` 去 `/sign-in?next=/admin/users`。

| 状态 | 表现 |
| --- | --- |
| 成功 | 行：`display_name` `email` `roles` `muted`。不展示 `terms_accepted_at`。Role 列用约 10px 的小标签换行显示 Student / Teacher / Editor / Admin。已有的实心，没有的空心，点一下切换并 `PATCH` `roles`。有 `super_admin` 时多一个不可点的 Super admin 标签。自己和 `super_admin` 不显示 `Mute` / `Unmute` 与 `Delete user`。 |
| 禁言 | `PATCH` body `{ "muted": true }`。成功行更新。对方仍可登录；发帖时见 `account_muted`。 |
| 删除 | 确认后 `DELETE /api/v1/admin/users/{id}`。成功后该行消失。 |
| 错误 | `ErrorBanner` ← `error.message`。 |

### 3.8 News 草稿 `/news/drafts`

未登录去 `/sign-in?next=/news/drafts`。`roles` 不含 `editor` 且不含 `super_admin` 时去 `/`。

| 状态 | 表现 |
| --- | --- |
| 列表 | `GET /api/v1/news/drafts`。每行 `title`、`status`。可新建：只填 `title`，`POST /api/v1/news/drafts`。 |
| 排版 | 打开一篇后，编辑区与 `/` 的 News 报头同一套 16 槽（头条、右上两格、宽条、LATEST、FEATURES、CAMPUS LIFE、Special Feature）。槽位下标 `i` 对应 `position === i + 1`。右侧 Photo / Track / Student Art 仍是静态栏，不能点、不着色。 |
| 颜色 | 该位置没有板块：背景 `#A67C52`。`review_status` 为 `editing` 或 `pending`：背景 `#1A4FBF`，字为白色（已上线后再改、尚未再次同意也是蓝）。已同意且草稿标题、正文与 `published_heading` / `published_body` 一致：与公开 News 相同（白底、图框 `#D6DEEE`）。 |
| 进入编辑 | 点一个槽才出现标题、正文、Save、Submit。空槽保存时 `POST .../blocks` 带该槽的 `position`。已有板块保存走 `PATCH`。 |
| 提交 | `POST .../submit`。状态变为 `pending`，槽仍为蓝。 |
| 同意 / 退回 | 仅 `super_admin`，且该槽为 `pending` 时在编辑表里显示。`approve` 后若草稿与已发布一致，槽回到报头原样；`reject` 后回到 `editing`，线上不变，槽仍为蓝。 |
| 失败 | `403` / `422`：`ErrorBanner` 或字段下 `error.fields[]`。禁言写操作显示 `error.message`。 |

### 3.8a News 投稿 `/` `/news/submit` `/news/design` `/news/review`

- 首页 `/` 保留 Front Page 杂志版式，News 文章填入既有主图、侧栏和故事版位。版面内提供 `All`、`Sports`、`Dorm`、`Scoop` 四个筛选；All 是汇总，不是稿件类别。文章标题和首图均打开完整文章内容。
- `/news/submit`（导航名 Draft）仅 `editor` / `super_admin` 可进。表单含标题、正文、图片（最多 4 张）和多选分类；这里保存原稿。`editor` 可把已保存的原文送审。`super_admin` 不在这里送审。
- `/news/design`（导航名 Design）仅 `super_admin` 可见、可进。选择稿件后可切换 Original / API design。API design 由独立按钮生成预览；无 API key 时明确显示本地段落整理。超管可在此确认发布草稿，也可从审核队列审批待审稿。`editor` 没有这一栏，直接打开地址回到首页。
- `pending` 稿件不会出现在公开 Front Page；只有 `super_admin` 批准后才发布。退回后编辑可在 Draft 修改并再次送审。
- `admin` 或 `super_admin` 可在已发布文章详情撤回。撤回后首页对应分类不再显示该文，原稿仍在 Draft，可再编辑并送审。
- 所有审核权限由后端校验；路由隐藏不能代替接口权限。详情与列表只返回已发布文章。

### 3.9 System `/system`

未登录去 `/sign-in?next=/system`。

| 状态 | 表现 |
| --- | --- |
| 成功 | `GET /api/v1/me/notices` 的 `items[]`：`body`、`created_at`。没有回复框，没有发帖表。 |
| 空 | `items.length === 0`：“No messages.” |

### 3.10 CJ 管理端 Teams 导入 `/cj/admin`

仅 `super_admin` 看见。老师端不显示这组按钮。学生周视图不增加字段，仍读 `ic`、`hw`、`announcement`。

| 状态 | 表现 |
| --- | --- |
| 打开页面 | `GET /api/v1/cj/teams/status`。显示 Teams 是否已连接、DeepSeek 是否已配置。不显示令牌或 key。 |
| 未配置 Microsoft | 不跳转登录。说明需要先配置 Microsoft 应用。 |
| 连接 | `POST /api/v1/cj/teams/connect`，浏览器打开返回的 `authorize_url`。回到本页且查询为 `teams=connected` 时显示已连接；`teams=error` 显示 `error.message` 同级的失败说明。 |
| 导入 | 使用当前周次。`POST /api/v1/cj/teams/preview`，body 只有 `week_start`。列出将写入的学科、星期、IC、HW、A，以及跳过原因。此步不改变已保存的 CJ。 |
| 确认 | `POST /api/v1/cj/teams/apply`，body 为该周与预览里的 `entries`。成功后重新 `GET /api/v1/cj?week_start=`。没有可写入条目时不出现确认。 |
| 失败 | `403` 不渲染此面板（路由已挡）。`422` / `503` 用 `error.message`，不把未确认的总结写进周视图。 |

不要用断网假数据充当错误处理。

---

## 4. 组件树

叶子标注 schema 字段。`ImageWell` 无数据绑定。

- `<PaperShell>`
  - `<UtilityBar>`
    - `SYSTEM` 菜单：About / Terms / Contact / 中英切换
    - 登录后 `SETTINGS` 菜单：Avatar / Password；`roles` 含 `super_admin` 时 Users
    - 登录后 `MY POSTS` → `/me/posts`
    - `NOTICES` → `/system`
    - 右侧：访客 SIGN IN；登录后头像、`display_name` ← `GET /me`、SIGN OUT
    - `<TodayLabel>` 本地日期（非 API）
  - `<Masthead>`
    - `<SearchStub>` 静态
    - 字标 `Elegram` 链 `/`
    - 静态 Community hosted
  - `<Tagline>` 静态
  - `<SectionNav>` NEWS（`/`）/ DRAFT（`editor` 或 `super_admin`，`/news/submit`）/ DESIGN（仅 `super_admin`，`/news/design`）/ FORUM / CJ（`/cj`）/ OPINION
  - `<SearchNotice>` 仅搜索提交后显示（静态文案）
  - `<Outlet>` 下列页面之一
  - `<Disclaimer>` Owned by 广东智云建材有限公司.

- `<Page: Home>`
  - `<ErrorBanner>` ← `error.code` `error.message`（仅列表失败）
  - `<HomeGrid>` ← `GET /posts` 的 `items` `total`
    - `<FeaturedLead>` ← `items[0]`
      - `<ImageWell>`
      - `<Kicker>` ← `category`
      - `<Headline>` ← `title` 链 `/posts/{id}`
      - `<Dek>` ← `excerpt`
    - `<SecondaryPair>` ← `items[1]` `items[2]`（同 StoryTile 字段）
    - `<SecondaryWide>` ← `items[3]`
    - `<SectionRule>` 文案 LATEST
    - `<LatestLead>` ← `items[4]`（`category` `title` `excerpt` `id`）
    - `<LatestStack>` ← `items[5..7]`
    - `<SectionRule>` FEATURES
    - `<CompactColumn>` ← `items[8..10]`（`category` `title` `excerpt` `id`）
    - `<FeatureLead>` ← `items[11]`（+ `created_at`）
    - `<SectionRule>` CAMPUS LIFE
    - `<CampusTrio>` ← `items[12..14]`（`category` `title` `excerpt` `created_at` `id`）
    - `<SpecialFeature>` ← `items[15]`（`category` `title` `excerpt` `created_at` `id`）
    - 没有对应 `items[n]` 的槽和整段标题不渲染
  - 公开首页不放 Photo / Track / Student Art 静态栏

- `<Page: Category>`
  - `<SectionRule>` 栏目名
  - Forum：右下角蓝色圆形 `<ComposeFab>`；打开后浮层 `<ComposeForm>`；未登录加号去登录
  - `<ErrorBanner>` ← `error.message`
  - Forum：`<CommunityCard>` ← `items[]`：头像、名、时间、标题、excerpt、图、底栏气泡与拇指
  - 校报：`<StoryRowList>` ← `items[]`
    - `<StoryRow>`
      - `<ImageWell>`
      - `<Kicker>` ← `category`
      - `<Headline>` ← `title` → `/posts/{id}`
      - `<Dek>` ← `excerpt`
      - `<Dateline>` ← `created_at`
  - `<EmptyCategory>` `total===0` 时
  - `<Pagination>` 显示条件用 `page` `page_size` `total`；请求 Query `page`

- `<Page: PostDetail>`
  - `<ErrorBanner>` 或 `<NotFoundHed>` ← `error.code` `error.message`
  - `<Article>`
    - `<Kicker>` ← `category`
    - `<Headline>` ← `title`
    - `<Byline>` ← `author.display_name` `created_at`
    - `<ImageWell>`（仅校报）
    - Forum：`<Body>` ← `body`
    - News：`<Block>` ← `blocks[]` 的 `heading` `body` `position`
    - 不展示 `status`、`email`、`excerpt`（详情以 `body` 为准）
    - Forum 时 `<CommentThread>` ← `GET .../comments` 的 `items[]`（`floor` `body` `author` `replies`）
    - `admin` 或 `super_admin` 时 `<DeletePost>` → `DELETE /api/v1/posts/{id}`

- `<Page: NewsDrafts>`
  - `<SectionRule>` DRAFTS
  - 列表 ← `GET /news/drafts` 的 `title` `status`
  - 打开一篇后 `<DraftBoard>` 与 News 报头同一 16 槽
    - 空槽背景 `#A67C52`；`editing` / `pending` 背景 `#1A4FBF`
    - 已同意且草稿与 `published_heading` / `published_body` 一致：白底图框
    - 点槽才显示标题、正文、Save、Submit
  - `super_admin` 对 `pending` 槽：同意 / 退回

- `<Page: System>`
  - `<SectionRule>` SYSTEM
  - 行 ← `GET /me/notices` 的 `body` `created_at`
  - 无回复框

- `<Page: MyPosts>`
  - `<SectionRule>` MY POSTS
  - `<ErrorBanner>` ← `error.message`
  - `<StoryRowList>` ← `GET /me/posts` 的 `items`
  - `<EmptyMine>` `total===0`

- `<Page: SignIn>`
  - `<AuthForm>` Request `email` `password`
  - `<ErrorBanner>` ← `error.message`（`invalid_credentials` / 503）
  - `<FieldError>` ← `error.fields[]`
  - 链到 `/register`

- `<Page: Register>`
  - `<AuthForm>` Request `email` `password` `display_name`
  - `<FieldError>` ← `email_taken` / `validation_error` 的 `fields[]`
  - 链到 `/sign-in`

- `<Page: AdminUsers>`
  - `<SectionRule>` USERS
  - `<ErrorBanner>` ← `error.message`
  - 行 ← `items[]` 的 `display_name` `email` `roles` `muted`

`StoryTile` / `StoryRow` / `FeaturedLead` 共用绑定：`id` `title` `excerpt` `category` `created_at` `author.id` `author.display_name`。列表不绑 `body`。

---

## 5. 交互要点

主路径（P1-US1）：注册或登录 → 在 Forum 发布 → 详情与 Forum 列表能读到。

| 用户动作 | 请求 | 成功 | 失败 |
| --- | --- | --- | --- |
| 打开站点 | `GET /api/v1/me` | 顶栏用 `display_name` | `401`：顶栏 SIGN IN，不当错误条 |
| 打开 `/` | `GET /api/v1/posts?page=1&page_size=20` | 按槽位绑 `items` | `ErrorBanner` ← `error.message` |
| 点故事 | — | 去 `/posts/{id}` | — |
| 点 NEWS | `GET /api/v1/posts?page=1&page_size=20` | 报头槽位 | `ErrorBanner` ← `error.message` |
| 点 DRAFTS | `GET /api/v1/news/drafts` | 草稿页；仅 `roles` 含 `editor` 或 `super_admin` 时看见导航项 | 403 回 `/` |
| 点 FORUM | `GET /api/v1/posts?category=forum` | 卡片列表 | 栏目下错误条 |
| 打开详情 | `GET /api/v1/posts/{post_id}` | 绑 `PostDetail` | `404` 文案；`503` 错误条 |
| Forum 详情 | `GET /api/v1/posts/{id}/comments` | 帖子下的评论 | `422` 不在校报页出现 |
| 评论 | `POST .../comments` | 追加一条评论，不带 `parent_id` | 401 去登录；422 字段下 |
| 打开草稿 | `GET /api/v1/news/drafts` | 列出稿与板块 | 403 回 `/` |
| 提交板块 | `POST .../blocks/{id}/submit` | 该块 `pending` | 403 `account_muted` |
| 同意板块 | `POST .../approve` | 公开 News 出现该块 | 非超级管理员 403 |
| 管理员删帖 | `DELETE /api/v1/posts/{id}` | Forum 回 `/forum`，News 回 `/`；作者 System 多一条 | 403 错误条 |
| 禁言 / 解除 | `PATCH /api/v1/admin/users/{id}` body `muted` | 行上 `muted` 更新 | 403 错误条 |
| 删除用户 | `DELETE /api/v1/admin/users/{id}` | 行消失 | 403 错误条 |
| Forum 列表点气泡 | — | 去 `/posts/{id}` | — |
| Forum 列表点赞 | `POST` 或 `DELETE .../likes` | 点击后立刻改该卡 `like_count` `liked` 并播放拇指动画，请求返回后再对齐。详情同样 | 401 去登录并退回；422/503 退回点击前的数字与颜色 |
| Forum 已登录点加号 | — | 右下加号打开浮层表单 | 点关闭或遮罩收起 |
| 校报 Write | — | 本页展开锁栏目表单 | 学生在校报无按钮 |
| Sign in 提交 | `POST /api/v1/auth/login` body `email` `password` | 去 `next` 或 `/` | 表单上沿 `error.message`；字段错 `fields[]` |
| Register 提交 | `POST /api/v1/auth/register` body `email` `password` `display_name` | 同上 | `409` 写在 email 下 |
| Sign out | `POST /api/v1/auth/logout` | 顶栏变 SIGN IN；若在 `/me/posts` 则去 `/` | `401`：已当访客 |
| Forum Publish | `POST /api/v1/posts`（JSON 或 multipart `images`） | 提交后浮层播放转圈动画并写正在发布，成功前不关浮层；成功去 `/posts/{id}` | 拿掉动画。422 字段下；401 去登录；503 表单顶。**不**乐观插入首页 |
| 校报 Publish | `POST /api/v1/posts` JSON | 收起表单，新帖出现在本栏目列表顶 | 同上 |
| 打开我的帖子 | `GET /api/v1/me/posts?page=1&page_size=20` | 列表 | 401 去登录；503 错误条 |
| Older stories | 同一列表接口 `page` 递增 | 追加或换页 `items` | `bad_request` 错误条 |
| 搜索提交 | 无 | 静态说明 | — |
| 超管打开 `/cj/admin` | `GET /api/v1/cj/teams/status` | 显示连接状态 | `401` 去登录；`403` 不进此页 |
| 超管连接 Teams | `POST /api/v1/cj/teams/connect` | 转到 Microsoft 登录 | `503` 说明未配置，不跳转 |
| 超管预览本周 CJ | `POST /api/v1/cj/teams/preview` | 列出将写入与将跳过 | `503` 用 `error.message`；周视图不变 |
| 超管确认写入 | `POST /api/v1/cj/teams/apply` | 本周 CJ 更新 | `503` 不留下半截；`422` 字段错误 |
