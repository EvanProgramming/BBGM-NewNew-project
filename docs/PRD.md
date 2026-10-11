# Elegram PRD（第一版）

依据：`README.md`。仓库内无 `docs/1-2` 或独立可行性结论；Won't 与 README「明确不做」对齐。登录方式、先审后发等开放问题在本 PRD 给出第一版默认，便于工程实现，不代表学校 SSO 已对接。

默认决策（可被后续 1.2 推翻）：

- 账号：站点自建注册 / 登录；仅 `@basischina.com`。注册须邮箱验证码通过后才建账号。登录用邮箱 + 密码。忘记密码用同一套验证码重置。不接校园 SSO、不发短信。
- 角色：一个人可以同时有多个身份。注册默认为 `student`。`ADMIN_EMAIL` 匹配时在注册或登录加上 `super_admin`，不覆盖已有身份。超级管理员可加上或去掉 `student`、`teacher`、`editor` 与 `admin`，不能授予或去掉 `super_admin`。普通用户至少保留一个可分配身份。
- 发帖：Forum 发布即公开。News 保留分板块草稿，超级管理员同意的板块才出现在 News 上；同时支持独立文章投稿，投稿须经 `super_admin` 审核后公开。首页即 News feed，可按 `sport`、`dorm`、`scoop` 筛选；`all` 表示全部文章，不存为类别。没有把 Forum 帖直接复制上 News 的精选。
- 无活动帖：帖子不带开始时间与地点字段。

---

## 1. Overview & Audience

**目标：** 让在校学生登录后在 Forum 发帖讨论，并让同学按栏目在站点上读到校报稿与讨论。

**受众：** 同一所学校的在校学生（读者、发帖者、学生编辑）。

**成功标准（可观察）：**

- 一名学生完成注册并登录后，能在 Forum 发布主帖；另一未登录会话打开 Forum 与详情，能看到同一条内容，并能阅读帖子下的评论。
- 一名编辑能写 News 草稿并按板块提交；超级管理员同意后，同学在 News 里只读到已同意的板块。
- 管理员能删除已发布帖；作者在 System 里看到一条不可回复的通知。
- 服务进程重启后，上述账号、帖与评论仍在，不依赖浏览器本地缓存作为唯一存储。
- 未登录用户不能发帖或跟帖；错误密码、缺字段、无权限操作均有明确失败结果，且不写出脏数据。

---

## 2. Personas & Core User Stories

最多三个画像。**第一版主故事：P1-US1（登录发帖并被同学按栏目看见）。**

### P1 发帖学生

校园里想把事发出来的普通学生，不是编辑。

- **P1-US1（主故事）：** 作为已注册学生，我想登录后在 Forum 写标题和正文并发布，以便同学能在 Forum 读到我的帖并跟帖。
- **P1-US2：** 作为已登录学生，我想打开「我的帖子」看到自己发过的内容，以便确认已经发出去、能再点进详情。
- **P1-US3：** 作为已登录学生，我想在校验失败时看到具体原因并留在编辑页，以便改完再发，而不是以为发出去了。
- **P1-US4：** 作为已登录学生，我想在 Forum 详情给帖子写评论，以便讨论留在该帖下面。
- **P1-US5：** 作为已登录学生，我想选一个自带头像或上传自己的照片，以便同学在讨论里认出我。
- **P1-US6：** 作为已登录学生，我想在 Forum 发帖时附上现场照片，以便同学在卡片和详情里看到图，而不是只读文字。
- **P1-US7：** 作为已登录学生，我想在 Forum 列表给主帖点赞或取消，以便用数量表示认同；未登录只能看见数量。

### P2 校园读者

想知道校园新闻正在发生什么，不一定发帖。

- **P2-US1：** 作为访客或学生，我想不登录就浏览首页、校报栏目、Forum 列表及帖子详情与评论，以便先读到内容。
- **P2-US2：** 作为读者，我想从导航进入某一栏目只看该栏目帖子，以便把校报栏目和 Forum 讨论分开找。

### P3 学生编辑

须由超级管理员授予 `editor`。与 P1 同一账号体系。

- **P3-US1：** 作为编辑，我想按板块写 News 草稿并分别提交，以便超级管理员可以只把其中一些板块放到 News 上。
- **P3-US2：** 作为超级管理员，我想同意或退回单个板块，以便未完成的改动留在草稿里，已同意的部分已经能被同学读到。
- **P3-US3：** 作为超级管理员，我想授予 `editor` 或 `admin`、禁言或删除用户，以便管理谁能写稿、谁能删帖。

---

## 3. Key Features（MoSCoW）

Must 服务主故事 P1-US1（Forum 发帖被看见）以及角色、跟帖、News 分板块审稿所必需的部分。

### Must Have

| ID | 能力 | 说明 |
| --- | --- | --- |
| M1 | 注册、登录、退出 | 仅 `@basischina.com`。注册先发邮箱验证码，码通过后才建账号；请求里 `accept_terms` 必须为 `true`，服务端写入 `terms_accepted_at`。公开页 `/terms` 为用户协议（默认英文，可切中文）。未同意不建账号。登录用邮箱 + 密码。会话可跨请求识别当前用户。发帖回路离开登录不成立。协议上线前已有账号的 `terms_accepted_at` 为 `null`，登录不因此被拒。 |
| M23 | 找回密码 | 登录页可走忘记密码。校内邮箱收验证码后设新密码，再用登录接口进站。非 `@basischina.com` 当场拒绝，不发信。 |
| M24 | 登录后改密码 | 顶栏账号旁可改密码：校验当前密码后设新密码，无需再发验证码。 |
| M2 | 鉴权与权限 | 未登录可读已发布内容与 Forum 评论；仅登录用户可发帖 / 跟帖；直接发 News 被拒绝；用户不能改删自己的帖或评论。被禁言者仍可登录阅读。 |
| M3 | 多页面 | 至少：News（`/` 报头版式，不再单列 News 列表页）、Forum、CJ（月历、学生端五日周视图、管理端按周）、帖子详情（Forum 含评论）、登录/注册/找回密码、登录后改密码、用户协议、我的帖子、News 草稿、System 通知、超级管理员用户列表。Forum 发帖在栏目页内，无独立 Submit 页。 |
| M4 | 发帖 | Forum：标题、正文必填，发布后 `published`，作者绑定当前用户，可附带最多 4 张图。News 不经此接口公开。 |
| M6 | 按栏目阅读 | 栏目页只列出该栏目已发布帖。News 详情只展示已同意板块。 |
| M7 | News 露出 | `/` 的报头版式展示近期已发布 **News**，不含 Forum，不含尚无已同意板块的草稿。导航第一项是 News，没有单独的 News 列表页。 |
| M8 | 持久化 | 用户（含角色）、会话、帖子、评论、Forum 主帖点赞写入应用存储；重启后仍可登录并读到已发帖、评论与赞数。 |
| M9 | 关键错误处理 | 密码错误、未登录发帖/跟帖、缺必填、非法栏目、非法配图、无权限、存储失败：均返回明确失败，不创建半截已发布帖或评论。 |
| M10 | 写操作留痕 | Forum 发帖或创建 News 草稿成功时记录 `author_id`、`created_at`；服务端另写一条审计记录（谁、何时、创建了哪篇帖）。 |
| M11 | Forum | 与 News、CJ 平级的单一讨论区，不是用户自建多吧。打开 `/forum` 是推荐：分数 `0.6 × 赞 + 0.4 × 评论`，取前 10，分数相同则较新的在前。`/forum/latest` 是最新：按时间取前 10。`/forum/all` 是所有：按时间列出全部，可翻页。 |
| M26 | CJ | 与 Forum 平级的课表栏，必须登录并按角色进入三个独立入口。学生端从月历按整周进入周一至周五五列只读视图，Period 1–8 自选学科只存在浏览器本地；每位老师由超级管理员分配一个 CJ 学科，只能读取和更新该学科的 CJ 与考试；`super_admin` 管理端可读取和修改全部 CJ、考试以及老师学科分配。考试必须选择学科，学生端自动显示学科前缀。`editor` 与普通 `admin` 不自动获得 CJ 权限。老师或超级管理员可上传作业照片；百炼 `qwen3-vl-flash` 认出学科并写入当天的 IC / HW / A。裁切处补上的文字单独返回，不冒充照片原文。 |
| M27 | Teams 群聊生成当周 CJ | 仅 `super_admin`。一个已在目标群里的 Teams 账号经 Microsoft 登录一次，服务器只保存刷新令牌。管理端选择周次后先预览，确认后才把群聊文字交给 DeepSeek `deepseek-flash`，总结成已有学科的 IC / HW / A 并写入 `CJEntry`。不下载附件。对不上学科、星期或超长的条目跳过。学生周视图仍读原来的 CJ 字段。未连接或上游失败时不写入半截 CJ。 |
| M28 | News 独立投稿 | `editor` 或 `super_admin` 在 Draft 填写标题、正文、图片与类别并保存；Design 中选择原文或 API 排版。编辑提交后进入待审，只有 `super_admin` 可发布。公开 Front Page 按 `sport` / `dorm` / `scoop` 筛选，`all` 为汇总。 |
| M12 | Forum 评论 | 仅 Forum 详情：帖子下的评论。未登录可读；登录可写。不新增楼层，不写楼中楼。校报详情不加评论。 |
| M13 | 角色 | `student` / `teacher` / `editor` / `admin` / `super_admin`，可同时拥有多项。`ADMIN_EMAIL` 在注册或登录时加上 `super_admin`，不覆盖已有身份。 |
| M14 | News 分板块草稿 | `editor` 与 `super_admin` 在 `/news/drafts` 新建稿并按板块保存、提交。`super_admin` 可同意或退回单个板块。公开 News 只含已同意板块。已上线板块再改，仍须再次同意后才替换线上正文。 |
| M15 | 超级管理员用户列表 | 仅 `super_admin` 查看用户，并可替换其 `student` / `teacher` / `editor` / `admin` 组合、禁言或解除、删除用户。不能禁言或删除自己，也不能禁言或删除 `super_admin`，不能授予或去掉 `super_admin`。身份标签可以改自己的那一行。 |
| M16 | 头像 | 自带预设（`preset:oak` 等）或上传一张图；出现在顶栏、Forum 帖/楼、栏目内发帖表。校报栏目没有封面图字段。 |
| M17 | Forum 卡片 | `/forum` 每条为独立模块卡：头像、展示名、时间、标题、`excerpt`、有则 `images[0]`；底栏气泡（`reply_count`，点进详情）与拇指（`like_count`）。列表不展开楼层预览。校报列表仍用原印刷行。 |
| M18 | 配图 | Forum 主帖与 News 投稿可上传最多 4 张 jpeg/png/webp（每张 ≤2MB），存在 `images[]`。跟帖不传图。 |
| M19 | Forum 点赞 | 仅 Forum 主帖。登录可赞/取消（同一用户同一帖不加倍）；未登录只读数量，点赞去登录。校报帖不可赞。 |
| M20 | 停留时看到新帖 | News（`/`）与 Forum 打开后重复请求已有公开列表；他人新发的帖进入当前列表，无需整页刷新。Forum 详情同样拉新评论。后台拉失败不打断当前阅读、不盖错误条。不另开推送通道或新字段。 |
| M21 | 删帖与 System 通知 | `admin` 与 `super_admin` 可删除帖子。删之前给作者写一条 System 通知（标题已被移除）。帖、其评论、点赞、配图、板块与该帖审计一并去掉。作者、`editor` 与学生不能删。System 页不可回复。 |
| M22 | 禁言 | 仅 `super_admin` 可禁言或解除。被禁言者可以登录和阅读，不能发帖、跟帖、点赞、创建或提交草稿。不废除其会话。已发帖仍公开。 |
| M25 | 删除用户 | 仅 `super_admin` 可删除用户。作废其会话，并删除其帖子、评论、点赞与草稿。不给被删用户发 System 通知。 |

### Should Have

| ID | 能力 | 说明 |
| --- | --- | --- |
| S1 | 标题关键词检索 | 提升「被看见」，但主路径用栏目浏览即可走通。 |
| S2 | 编辑 / 删除自己的帖或评论 | 纠错；删除后详情与列表不再作为已发布出现。 |
| S5 | 审计记录可查询 | 受信任运营者按时间查看发帖审计；无此 UI 时数据仍在 M10。 |
| S6 | 下架已发布帖 | 处理明显违规；第一版默认发布即公开，下架可稍后由受信任角色执行。 |

### Could Have

| ID | 能力 | 说明 |
| --- | --- | --- |
| C1 | Featured / 头条精选、Submit 编辑流 | 学生媒体校报形态，不阻塞普通发帖。 |
| C2 | Opinion、Photo of the Day、Student Art | 页面稿或静态壳，非主故事必需。本版无独立 Photo / Events / Dorm Life 栏目。 |
| C3 | Track of the Day / Spotify 嵌入 | 第三方点缀；无此主站仍成立。 |
| C4 | 关注、推荐信息流 | 社交增强。News 分板块草稿已在 M14。Forum 主帖点赞已在 M19。 |
| C5 | 校园 SSO / 学号目录同步 | 开放问题，第一版不阻塞自建账号。 |
| C6 | Forum 先审后发 | 学生在 Forum 仍发布即公开。News 审稿已在 M14。 |

### Won't Have（本版本）

| ID | 不做 | 原因 |
| --- | --- | --- |
| W1 | 教务、选课、成绩、官方通知替换系统 | 与校园发帖无关。 |
| W2 | 关注图谱、模型打分、付费专栏 | Forum 的推荐只按赞 0.6、评论 0.4 取前 10，不算模型推荐。 |
| W3 | 原生 App、直播、活动售票 / 支付 | 非 Web 第一版范围；不接支付合规。 |
| W4 | 未评估的 AI 写作或审核模型 | 除 M26 的作业照片识别，以及 M27：超管把 Teams 群聊总结写入当周 CJ。不做 AI 审核，不自动改帖，不给学生或老师直接调用模型。 |
| W5 | 向量库、微服务拆分、指定云厂商 | 未评估，不写入本版承诺。 |
| W6 | 用户自建吧、校报帖下评论、楼层与楼中楼 | Forum 只有一个吧；评论直接挂在帖子上。 |
| W7 | 单条删评、下架状态、完整审核后台 | 管理员可删整帖（M21）。不能只删一楼，没有 `hidden` 状态。News 审稿只按板块同意或退回。 |
| W8 | 活动时间地点、Sports、Dorm Life / Events / Photo 栏目 | 本版栏目为 News、Forum 与 CJ；Opinion 为静态空栏。`/sports` 回到首页。 |

登录、数据库、多页面路由、测试均不在 Won't 中。它们按主故事需要出现在 Must 或工程实践中。

---

## 4. Acceptance Criteria

按主故事及使其成立的读写路径书写。格式：给定…当…则…。

### 4.1 主路径成功（P1-US1 + P2 看见 + P3 发稿）

1. 给定未注册访客在注册页，当填写未被占用的 `@basischina.com` 邮箱、收到验证码、符合规则的密码，且 `accept_terms` 为 `true`，则创建用户、写入 `terms_accepted_at`，且可立即用该邮箱密码登录。非该后缀则拒绝且不发信。
2. 给定已注册用户在登录页，当提交正确校内邮箱与密码，则进入已登录态，并可以在 Forum 直接写帖发布。非 `@basischina.com` 登录失败（字段错误，不建立会话）。
3. 给定已登录学生在 Forum，当填写标题、正文并发布，则该帖 `published`，`category=forum`，作者为当前用户，并进入该帖详情。
4. 给定 3 中刚发布的帖，当另一未登录会话打开 Forum，则列表中出现该标题；打开详情则正文一致；首页无 `category` 的列表**不**出现该 Forum 帖。
5. 给定编辑或超级管理员创建一篇 News 草稿并提交两个板块，当超级管理员只同意其中一块，则 News 列表与详情只出现已同意的那一块。
6. 给定已发布帖已写入存储，当重启应用进程后再次打开详情 URL 并用原账号登录，则帖仍在且原账号仍能登录。
7. 给定已登录用户，当打开「我的帖子」，则能看到自己已发布的标题并进入详情。

### 4.2 校验失败 / 权限不足 / 存储不可用

8. 给定登录页，当邮箱不存在或密码错误，则登录失败、不建立已登录会话，并提示凭据无效（不提示「仅密码错误」与「仅用户不存在」的区别亦可，但不得登录成功）。
9. 给定未登录访客，当直接请求发帖或提交发帖接口，则拒绝创建帖子，并要求登录（跳转登录或等价错误）。
10. 给定已登录用户，当标题为空、正文为空、未选栏目、或栏目不在允许集合内，则拒绝发布，停留在可编辑状态，已有输入不丢（刷新导致丢失除外），存储中不出现该条 `published` 帖。
12. 给定用户 A 的已发布帖，当另一名既不是 `admin` 也不是 `super_admin` 的用户尝试修改或删除该帖，则失败且帖内容不变。删除见第 27 条。
13. 给定发帖请求已通过校验，当存储写入失败，则向用户返回失败、不展示「发布成功」，且列表中不出现该帖。
18. 给定已登录用户，当用发帖接口提交 `category=news`，则 `403 forbidden`，公开列表不出现该稿。`category` 不在 `news` / `forum` 内则 `422`。
19. 给定 Forum 帖，当未登录读取评论则成功；当未登录跟帖则 `401`，不落评论。
20. 给定已登录用户在 Forum 详情，当发表一条评论，则该帖下可见；请求里带 `parent_id` 则 `422`，不新增楼层或楼中楼。
21. 给定编辑提交一个 News 板块，当超级管理员退回，则公开详情不出现该板块的新正文；编辑仍可修改并再次提交。
22. 给定超级管理员打开用户列表，当把一名学生的身份设为同时包含 `editor` 与 `teacher`，则对方 `roles` 含这两项。`admin`、`editor` 或学生调用该接口则 `403`。不能写入 `super_admin`。普通用户的 `roles` 不能为空。已有 `super_admin` 再被设成 `editor` 时，结果仍含 `super_admin`。
23. 给定校报详情页，当请求该帖的评论接口，则 `422`，页面不展示评论。
24. 给定已登录学生在 Forum 发帖并附上合法图片，当发布成功，则详情与 Forum 卡片能读到同一组 `images`；非法图片或向校报帖配图则失败且不落半截帖，校报 `images` 仍为 `[]`。
25. 给定已登录用户在 Forum 列表，当点赞一帖再取消，则 `like_count` 与 `liked` 随之变化且刷新后仍对；再点一次已赞不加倍。未登录点赞不写入，去登录。校报帖点赞失败。
26. 给定会话 A 停在 Forum 的最新或所有（不整页刷新），当会话 B 发布一条 Forum 帖，则数秒内 A 的列表顶部出现该标题。停在推荐时，0 赞且 0 评论的新帖不插到第一位。停在 `/` 时，对新公开的 News 稿同样成立。Forum 详情对他人新评论同样成立。拉新失败时 A 仍看得到已有内容。
33. 给定至少 11 篇已发布 Forum 帖，当打开推荐，则最多 10 条，且按 `0.6 × 赞 + 0.4 × 评论` 从高到低，分数相同则较新的在前。两条评论（0.8）排在一个赞（0.6）前面，一个赞排在一条评论（0.4）前面。当打开最新，则最多 10 条且较新的在前。当打开所有，则 `total` 为全部篇数并按时间分页。`feed` 与非 `forum` 栏目同时出现则 `422`。
27. 给定 `admin` 或 `super_admin`，当删除一条已发布帖，则该帖详情为 `404`，列表中不再出现，其评论与配图一并消失，作者的 System 列表出现一条含该标题的通知。学生或编辑调用删除则 `403`，帖仍在。System 页没有回复框。
28. 给定超级管理员禁言一名学生，当该学生再登录则成功；当发帖、跟帖或点赞则 `403`，且不写入。解除后可用原账号发帖。不能禁言自己或 `super_admin`。`admin` 不能禁言他人。
30. 给定超级管理员删除一名学生，则该用户不能再登录，其已发帖从公开列表消失。不能删除自己或 `super_admin`。
31. 给定一篇已有一块已同意内容的 News，当编辑修改该块并提交、超级管理员尚未同意，则公开详情仍是同意前的正文；同意后才换成新正文。
29. 给定已注册校内邮箱用户在找回密码页，当用该邮箱收到验证码并提交新密码，则旧密码不能再登录、新密码可以。非 `@basischina.com` 或不存在的账号：前者当场拒绝不发信；后者发码接口仍回成功、重置失败不泄露该邮箱是否已注册。
32. 给定未注册访客提交注册，当 `accept_terms` 不是 `true`（缺省或 `false`），则 `422`，不建账号，且该验证码仍可再用于一次成功注册。协议上线前已存在的账号 `terms_accepted_at` 为 `null`，用原密码登录仍成功。

### 4.3 关键非功能（可测、且为本产品需要）

14. **浏览器：** 在桌面 Chrome、Safari、Firefox 或 Edge 的近两个大版本中，4.1 的步骤 2–5 均能完成。第一版不验收 IE、原生 App、小程序。
15. **延迟：** 在本地或校园网常规条件下，栏目列表与帖子详情的 HTML 首屏（不含第三方嵌入）在 3 秒内可阅读正文或列表标题。不把未接入的图床 / CDN 超时算进本条失败，除非图片是正文唯一内容。
16. **量级：** 第一版按单校站点验收：至少支持 50 个已登录会话并存、栏目列表 100 篇已发布帖时仍能完成打开列表与详情。不做全校秒杀、不做跨校多租户。
17. **持久化：** 验收环境不得以「只写前端内存、刷新即丢」通过 4.1 步骤 6。

不验收：断网伪装演示、假数据路演模式、关注图谱与模型打分。

---

## 5. Entity Flow

### 5.1 系统边界

```
访客 / 学生浏览器
        │
        ▼
Elegram 应用（Web 页面 + 服务端）
        │
        ▼
应用存储（用户、会话或等价凭证、帖子、评论、审计记录）
```

发帖主路径无必须第三方产品 API。发验证码走通用 SMTP（环境变量），不绑定某一云厂商。M26 的作业照片识别调用百炼，M27 只在超级管理员确认导入时调用 Microsoft Graph 与 DeepSeek，密钥只在环境变量。学校 SSO 未对接。

### 5.2 核心实体

| 实体 | 关键字段 | 生命周期 |
| --- | --- | --- |
| User | id, email, password_hash, display_name, roles, avatar, muted, terms_accepted_at, created_at | 邮箱须 `@basischina.com`；验证码通过且 `accept_terms` 为 `true` 后注册为 `["student"]`，服务端写入 `terms_accepted_at`；`roles` 可含多项；`muted` 默认 false；禁言后仍可登录，不能写帖。协议上线前的账号该时间为 `null` |
| EmailCode | email, purpose, code_hash, expires_at, attempt_count | 注册或找回密码发码；明文不入库；发出后 2 分钟过期，或用过后失效 |
| Session | 可校验的登录凭证，绑定 user_id，可失效 | 登录创建 → 退出、删除用户或过期销毁。禁言不废除会话 |
| Post | id, author_id, title, body, category, status, images, created_at, updated_at | Forum 校验通过后 `published`。News 在至少一块被同意前为 `draft`，公开接口不返回。`admin` / `super_admin` 可整帖删除 |
| NewsCategory | post_id, topic | 独立 News 投稿的类别关联，`topic` 为 `sport` / `dorm` / `scoop`；文章可有多个类别 |
| NewsBlock | id, post_id, position, heading, published_heading, draft_body, published_body, review_status | `editing` / `pending` / `published`。同意把草稿写入已发布字段。公开详情只用已发布字段 |
| SystemNotice | id, user_id, body, created_at | 删帖时写给作者；只读，无回复 |
| PostLike | user_id, post_id, created_at | 仅 Forum 主帖；同一用户同一帖唯一；取消则删行 |
| Comment | id, post_id, author_id, parent_id, body, created_at | 仅 Forum；新评论 `parent_id` 为空。写入不接受楼层或楼中楼 |
| AuditEvent | id, actor_id, action, post_id, at | Forum 发帖或创建 News 草稿成功时追加；只增不改 |
| Subject | id, name, short_name, color, period, sort_order | CJ 学科目录。学生端不按 `period` 固定排课 |
| CJTeacherSubject | id, user_id, subject_id | 超级管理员给每位老师分配的唯一 CJ 学科；老师端据此过滤 CJ 与考试的读取和写入 |
| CJEntry | id, week_start, day_index, period, subject_id, ic, hw, announcement, updated_at | 某一周、某一天、某一学科的 IC / HW / A |
| TeamsConnection | 加密后的刷新令牌, updated_at | 全站一条。接口不返回令牌。Microsoft 登录成功后写入，预览时用来读群聊 |
| Exam | id, week_start, day_index, subject_id, title, time, location, note, updated_at | 某一周、某一学科的考试安排；前端用学科目录自动补显示前缀 |

`category` 枚举：`news`、`forum`。无 `category` 的列表只含 `news`。

`status`：`published` 或 News 草稿的 `draft`。Should 增加 `hidden`。

### 5.3 读写关系

```
User 1 ─── * Post
User 1 ─── * Session
User 1 ─── * Comment
User 1 ─── * PostLike
User 1 ─── * SystemNotice
User 1 ─── * AuditEvent（作为 actor）
Post 1 ─── * NewsBlock
Post 1 ─── * Comment
Post 1 ─── * PostLike
Post 1 ─── * AuditEvent
Comment（新评论不挂到另一条评论下）
```

| 动作 | 读 | 写 |
| --- | --- | --- |
| 注册 | User（查邮箱唯一） | User |
| 登录 | User | Session（匹配 `ADMIN_EMAIL` 时升 `super_admin`）。禁言不拒绝登录 |
| 退出 | Session | 删除或作废 Session |
| 浏览首页 / News / Forum / 详情 | Post（`published`）；News 详情另读已同意 NewsBlock；Forum 详情另读 Comment | 无 |
| 点赞 / 取消赞 | User、Post（须 Forum，且未禁言） | PostLike |
| 学生发帖 | User（当前会话，未禁言） | Post（仅 `forum`）、AuditEvent |
| 写 News 草稿 | User（`editor` 或 `super_admin`，未禁言） | Post（`draft` 直至有已同意板块）、NewsBlock、AuditEvent |
| 同意 / 退回板块 | User（须 `super_admin`） | NewsBlock 的已发布字段与 `review_status`；有已同意板块则 Post 为 `published` |
| 跟帖 | User、Post（须 Forum，且未禁言） | Comment |
| 我的帖子 | Post where author = 当前用户且 `published` | 无 |
| System | SystemNotice where user = 当前用户 | 无（删帖时由服务端写入） |
| 超级管理员改角色 / 禁言 | User 列表 | User.roles（可分配身份的新组合，已有 `super_admin` 保留）或 `muted`。禁言不废除会话 |
| 超级管理员删用户 | User | 删除 User、Session、其 Post、Comment、PostLike、NewsBlock |
| 删帖 | Post | 先写 SystemNotice 给作者，再删除 Post 及其 Comment、NewsBlock、PostLike、配图与该帖 AuditEvent |
| 超管从 Teams 导入 CJ | TeamsConnection、Subject | 预览不写 CJEntry。确认后覆盖该周对应学科的 IC / HW / A |

未登录：只读 `published` Post 与 Forum 评论与赞数。  
`student`：写 Forum 帖、评论与主帖点赞。  
`editor`：另写 News 草稿并提交板块。  
`admin`：删除帖子。  
`super_admin`：另改角色、禁言、删除用户、写草稿、同意或退回板块、删除帖子，并按 M27 导入 Teams CJ。  
存储失败时：上述写动作整笔失败，不出现「有详情 URL 但库中无行」或「有行无审计」的半成功（审计与帖子同一事务，或等价回滚）。
