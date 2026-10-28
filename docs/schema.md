# Elegram API 契约（第一版）

依据：`docs/PRD.md` Must Have 与 Entity Flow。本文件同时约束前端 Mock 与后端实现。不包含业务代码。

第一版 **无公开审计查询接口**（M10 仅服务端落库）。作者不能改自己的帖或评论。作者可以删除自己已发布的 Forum 帖，也可以撤回自己的评论；不能删除他人的帖或评论，也不能删除 News。`admin` 与 `super_admin` 可删除任意帖和任意评论；删除他人的帖或评论时给作者一条 System 通知。仅 `super_admin` 可禁言或删除用户。包含 Forum 评论、角色、News 分板块草稿与独立 News 投稿。新评论直接挂在帖子上，不新增楼层或楼中楼。漂流瓶是另一组接口，不是 `posts.category`。同学之间的漂流瓶响应不返回 `author_id`、`picker_id`、展示名、头像或邮箱。

---

## 0. 约定

### Base URL

```
/api/v1
```

默认 JSON：`Content-Type: application/json`。例外：`POST /api/v1/me/avatar` 与 `POST /api/v1/posts/{post_id}/images` 为 `multipart/form-data`（字段名 `file`）。`POST /api/v1/posts` 还可为 `multipart/form-data`（字段 `title` `body` `category`，重复文件字段 `images`）。

### 鉴权

Cookie Session。

- Cookie 名：`scoop_session`
- 属性：`HttpOnly`、`SameSite=Lax`、`Path=/`。生产环境加 `Secure`
- 登录、注册成功时由服务端 `Set-Cookie`
- 退出时清除该 Cookie
- 浏览器跨请求自动带 Cookie；前端 Mock 需模拟「已登录 / 未登录」两组

**需要鉴权的请求**在缺少有效会话时：

```http
HTTP/1.1 401 Unauthorized
Content-Type: application/json
```

```json
{
  "error": {
    "code": "unauthenticated",
    "message": "Please sign in to continue.",
    "fields": []
  }
}
```

公开读接口（News 栏目列表、News 详情、首页列表）**不**要求鉴权。Forum 列表、Forum 详情和 Forum 评论列表要求登录。漂流瓶、下棋和起床铃全部接口要求鉴权。

### 通用错误包络

所有 4xx / 5xx 均为此形状。`fields` 仅用于字段级校验；其他错误给 `[]`。

```json
{
  "error": {
    "code": "string",
    "message": "string",
    "fields": [
      { "field": "string", "message": "string" }
    ]
  }
}
```

| HTTP | `error.code` | 何时 |
| --- | --- | --- |
| 400 | `bad_request` | 分页参数非法等无法归到字段校验的请求错误 |
| 401 | `unauthenticated` | 无会话或会话无效 |
| 401 | `invalid_credentials` | 登录邮箱或密码不对（不区分「用户不存在」与「密码错误」） |
| 403 | `forbidden` | 已登录但无权（直接发 News、非编辑写草稿、非超级管理员改角色 / 禁言 / 删用户 / 同意板块、既不是该 Forum 帖作者也不是 `admin` / `super_admin` 时删帖、当日漂流瓶次数用尽、打开不属于自己且自己不是管理员的漂流瓶对话） |
| 403 | `account_muted` | 已登录但被禁言，仍调用发帖、跟帖、点赞、创建或提交草稿、扔瓶子、捞瓶子或回复漂流瓶、加入起床铃歌曲、给起床铃投票或撤回起床铃的票 |
| 404 | `not_found` | 帖子、评论父楼、用户、漂流瓶、漂流瓶对话或起床铃一轮不存在 |
| 409 | `email_taken` | 注册邮箱已被占用 |
| 409 | `sync_in_progress` | CJ 同步已经在进行，本次不开始第二次 |
| 409 | `round_open` | 起床铃已有一轮未截止 |
| 409 | `track_taken` | 这一轮已经有人加入同一首 QQ 音乐歌曲 |
| 422 | `validation_error` | 缺必填、超长、非法栏目、非法配图、非校内邮箱后缀、验证码无效或过期、注册时 `accept_terms` 不是 `true` |
| 503 | `storage_unavailable` | 存储写入失败，或作业照片识别调用失败；不得返回成功或半截资源 |
| 503 | `service_unavailable` | CJ 课表同步未配置密钥，或课表接口 / DeepSeek 调用失败；不改已有 CJ 行 |
| 503 | `qq_unavailable` | 起床铃搜索、加歌或取封面时 QQ 音乐调用失败；不新增候选 |

成功响应不包 `{ "data": ... }` 中间层：对象或列表字段直接放在 JSON 根上。

### 时间、id、分页

| 项 | 约定 |
| --- | --- |
| id | 字符串 UUID v4，创建后不变 |
| 时间 | UTC，ISO 8601 且带 `Z`，例如 `2026-09-07T14:30:00Z` |
| 分页 Query | `page` 整数 ≥ 1，默认 `1`；`page_size` 整数 1–50，默认 `20` |
| 分页非法 | `400` + `bad_request` |
| 列表成功 | `{ "items": [...], "page", "page_size", "total" }`；空列表 `items` 为 `[]`，`total` 为 `0` |
| 排序 | 无 `category`、News、我的帖子按 `created_at` 降序。Forum 见 `feed`。楼层按 `created_at` 升序（楼号 1 起） |

### 共享字段形状

**AuthorPublic**（对外帖子中的作者，不含邮箱）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | string | 用户 id |
| `display_name` | string | 展示名 |
| `avatar` | string | `preset:{oak\|gym\|book\|dorm\|bus\|night}` 或同源上传路径 `/uploads/avatars/{id}.{ext}`。缺省按 `preset:oak` |

**UserPrivate**（当前登录用户）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | string | |
| `email` | string | |
| `display_name` | string | |
| `roles` | string[] | 身份，可同时有多个。顺序固定为 `student`、`teacher`、`editor`、`admin`、`super_admin`。注册为 `["student"]`。`ADMIN_EMAIL` 在注册或登录时加上 `super_admin`，不删掉已有身份。 |
| `avatar` | string | 同 AuthorPublic |
| `muted` | boolean | 是否禁言。注册默认为 `false`。禁言后仍可登录 |
| `terms_accepted_at` | string \| null | 同意用户协议的时间，UTC ISO 8601 带 `Z`。注册成功时由服务端写入。协议上线前已存在的账号为 `null`。客户端不能指定该时间 |
| `created_at` | string | |

**PostSummary**（列表：首页、栏目、我的帖子）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | string | |
| `title` | string | |
| `excerpt` | string | 由 `body` 截断，最多 160 字，供卡片绑定；不是另一份正文 |
| `category` | string | `news` \| `forum` |
| `status` | string | 公开列表恒为 `published`。News 草稿在草稿接口里可以是 `draft` |
| `created_at` | string | |
| `updated_at` | string | 创建时与 `created_at` 相同 |
| `author` | AuthorPublic | |
| `reply_count` | integer | 楼层数。校报栏目与无 `category` 的列表为 `0` |
| `reply_preview` | ReplyPreview[] | Forum 最多 2 条最近的主评论（无楼中楼），按 `created_at` 从早到晚。其他列表为 `[]`。Forum 列表在卡片底栏下展示这 2 条 |
| `images` | string[] | Forum 或独立 News 投稿配图，同源路径 `/uploads/posts/{post_id}/{file}`，最多 4 张 |
| `like_count` | integer | Forum 主帖赞数。校报栏目与无 `category` 的列表为 `0` |
| `liked` | boolean | 当前会话是否已赞该帖；无会话或校报列表为 `false` |
| `news_categories` | string[] | News 独立投稿的类别子集：`sport`、`dorm`、`scoop`；旧版位稿与 Forum 为 `[]` |
| `pinned` | boolean | 是否置顶。缺省 `false`。仅 `super_admin` 可改。公开列表把 `true` 排在前面，最近置顶的更靠前 |

**ReplyPreview**（Forum 卡片用）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | string | 楼层 id |
| `body` | string | |
| `created_at` | string | |
| `author` | AuthorPublic | |

**PublishedBlock**（News 详情里已同意的板块）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | string | |
| `heading` | string | 已同意的板块标题 |
| `body` | string | 已同意的板块正文 |
| `position` | integer | 从 1 起，升序 |

**PostDetail** = PostSummary 的全部字段 + `body` + `blocks`。

- Forum：`body` 是全文，`blocks` 为 `[]`。
- News：`blocks` 只含已同意板块。`body` 是这些板块按顺序拼成的全文，供仍读 `body` 的客户端使用。没有已同意板块的稿不在本接口出现（`404`）。

**Notice**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | string | |
| `body` | string | 给当前用户的一句说明，例如帖子标题已被移除 |
| `created_at` | string | |

**ForumActivity**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `unread` | integer | 只有 `0` 或 `1`。`1` 表示别人在你上次把 Forum 互动标成已读之后，赞过或评论过你已发布的 Forum 帖。自己的赞和评论不算。校报帖不算。不会大于 1 |

**NewsBlockStaff**（草稿接口，含未公开正文）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | string | |
| `position` | integer | 从 1 起 |
| `heading` | string | 草稿标题 |
| `draft_body` | string | 草稿正文 |
| `published_heading` | string \| null | 已同意标题；从未同意则为 `null` |
| `published_body` | string \| null | 已同意正文；从未同意则为 `null` |
| `review_status` | string | `editing` \| `pending` \| `published` |

**NewsDraftSummary**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | string | 与公开帖 id 相同 |
| `title` | string | |
| `status` | string | `draft`（尚无已同意板块）或 `published` |
| `created_at` | string | |
| `updated_at` | string | |
| `author` | AuthorPublic | |

**NewsDraftDetail** = NewsDraftSummary + `blocks`（`NewsBlockStaff[]`，按 `position` 升序）。

**CommentReply**（楼中楼，挂在某一楼层下）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | string | |
| `body` | string | |
| `parent_id` | string | 所属楼层 id |
| `created_at` | string | |
| `author` | AuthorPublic | |

**CommentFloor**（楼层）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | string | |
| `body` | string | |
| `parent_id` | null | 楼层恒为 `null` |
| `floor` | integer | 全帖楼号，从 1 起，按楼层 `created_at` 升序 |
| `created_at` | string | |
| `author` | AuthorPublic | |
| `replies` | CommentReply[] | 该楼的楼中楼，按 `created_at` 升序 |

密码、`password_hash`、审计记录 **永不**出现在响应里。

---

## 1. 接口列表

### 1.1 Auth

#### `POST /api/v1/auth/email-codes`

- **鉴权：** 否
- **职责：** 向校内邮箱发送 6 位验证码。`purpose=register` 用于注册；`purpose=reset` 用于找回密码。非 `@basischina.com` **不写库、不发信**。码发出后 **2 分钟**过期。

**Request body**

| 字段 | 类型 | 必填 | 约束 |
| --- | --- | --- | --- |
| `email` | string | 是 | 有效邮箱，大小写不敏感，存储前规范化为小写；必须是 `@basischina.com` |
| `purpose` | string | 是 | `register` 或 `reset` |

**Response**

- `204` 无 body。不回验证码。`reset` 无论该邮箱是否已注册都回 `204`（防枚举）。
- `409` `email_taken`（仅 `purpose=register` 且邮箱已被占用）
- `422` `validation_error`（缺字段、邮箱非法、非校内后缀、`purpose` 非法、同一邮箱 60 秒内再发）
- `503` `storage_unavailable`（存储或发信失败）

---

#### `POST /api/v1/auth/register`

- **鉴权：** 否
- **职责：** 校验校内邮箱与验证码后注册学生账号；成功则创建用户、写入 `terms_accepted_at`、建立会话并 `Set-Cookie`。校验顺序：字段（含 `accept_terms` 必须为 JSON `true`）→ 后缀与码有效 → 再建用户。`accept_terms` 不是 `true` 时不消耗验证码。不接受客户端传来的同意时间。

**Request body**

| 字段 | 类型 | 必填 | 约束 |
| --- | --- | --- | --- |
| `email` | string | 是 | 有效邮箱，大小写不敏感，存储前规范化为小写；必须是 `@basischina.com` |
| `password` | string | 是 | 8–128 字符 |
| `display_name` | string | 是 | 去掉首尾空白后 1–40 字符 |
| `code` | string | 是 | 6 位数字；须与该邮箱最近一次 `purpose=register` 的未过期码一致（发出后 2 分钟内） |
| `accept_terms` | boolean | 是 | 必须为 JSON `true`。`false` 或缺省为 `422`，`fields[].field` 为 `accept_terms` |

**Response**

- `201` + `UserPrivate`（含服务端写入的 `terms_accepted_at`）；`Set-Cookie: scoop_session=...`
- `409` `email_taken`
- `422` `validation_error`（缺字段、邮箱非法、非校内后缀、密码过短、展示名为空、验证码无效或过期、未同意协议）
- `503` `storage_unavailable`

---

#### `POST /api/v1/auth/password-reset`

- **鉴权：** 否
- **职责：** 用校内邮箱验证码设置新密码。成功不建立会话；用户再走 `POST /api/v1/auth/login`。

**Request body**

| 字段 | 类型 | 必填 | 约束 |
| --- | --- | --- | --- |
| `email` | string | 是 | 有效邮箱，必须是 `@basischina.com`，规范化为小写 |
| `code` | string | 是 | 6 位数字；须与该邮箱最近一次 `purpose=reset` 的未过期码一致（发出后 2 分钟内） |
| `password` | string | 是 | 8–128 字符 |

**Response**

- `204` 无 body
- `422` `validation_error`（非校内后缀、缺字段、密码过短、验证码无效或过期；账号不存在时与码错同一 `code` 字段，不泄露是否已注册）
- `503` `storage_unavailable`

---

#### `POST /api/v1/auth/login`

- **鉴权：** 否
- **职责：** 校验邮箱密码，建立会话。非 `@basischina.com` 不查库比对密码。

**Request body**

| 字段 | 类型 | 必填 | 约束 |
| --- | --- | --- | --- |
| `email` | string | 是 | 有效邮箱，必须是 `@basischina.com` |
| `password` | string | 是 | 非空 |

**Response**

- `200` + `UserPrivate`；`Set-Cookie: scoop_session=...`
- `401` `invalid_credentials`（邮箱不存在或密码错误，同一文案）
禁言账号密码正确时仍 `200` 并建立会话。写操作另见 `account_muted`。
- `422` `validation_error`（缺字段、邮箱非法、非校内后缀）
- `503` `storage_unavailable`（读存储失败时）

---

#### `POST /api/v1/auth/logout`

- **鉴权：** 是
- **职责：** 作废当前会话并清除 Cookie。

**Request：** 无 body。

**Response**

- `204` 无 body；`Set-Cookie` 过期 `scoop_session`
- `401` `unauthenticated`

---

#### `GET /api/v1/me`

- **鉴权：** 是
- **职责：** 返回当前会话用户，供导航与栏目内发帖判断登录态。

**Request：** 无。

**Response**

- `200` + `UserPrivate`
- `401` `unauthenticated`

---

#### `PUT /api/v1/me/password`

- **鉴权：** 是
- **职责：** 已登录用户用当前密码改成新密码。成功保持当前会话，不发验证码。

**Request body**

| 字段 | 类型 | 必填 | 约束 |
| --- | --- | --- | --- |
| `current_password` | string | 是 | 非空；须与库中密码一致 |
| `password` | string | 是 | 8–128 字符；须与 `current_password` 不同 |

**Response**

- `204` 无 body
- `401` `unauthenticated`
- `422` `validation_error`（缺字段、新密码过短或与当前相同、当前密码不对写在 `current_password`）
- `503` `storage_unavailable`

---

#### `PUT /api/v1/me/avatar`

- **鉴权：** 是
- **职责：** 换成自带预设头像。

**Request body**

| 字段 | 类型 | 必填 | 约束 |
| --- | --- | --- | --- |
| `preset` | string | 是 | `oak` \| `gym` \| `book` \| `dorm` \| `bus` \| `night` |

**Response**

- `200` + `UserPrivate`（`avatar` 为 `preset:{preset}`）
- `401` `unauthenticated`
- `422` `validation_error`
- `503` `storage_unavailable`

---

#### `POST /api/v1/me/avatar`

- **鉴权：** 是
- **职责：** 上传一张头像。`Content-Type: multipart/form-data`，字段名 `file`。jpeg / png / webp，≤1MB。

**Response**

- `200` + `UserPrivate`（`avatar` 为 `/uploads/avatars/{user_id}.{ext}`）
- `401` `unauthenticated`
- `422` `validation_error`（类型或大小非法）
- `503` `storage_unavailable`

---

### 1.2 Posts

#### `GET /api/v1/posts`

- **鉴权：** `category=forum`（含全部 `feed`）需要登录。无 `category` 或 `category=news` 不要求登录。
- **职责：** 列出已发布帖。无 `category` 时供首页近期露出，**只含** `news`，不含 Forum，不含尚无已同意板块的 News 草稿。有 `category` 时只返回该栏目。未登录请求 Forum 列表不返回帖子。

**Query**

| 参数 | 类型 | 必填 | 约束 |
| --- | --- | --- | --- |
| `category` | string | 否 | 若出现必须是 `news` \| `forum` |
| `feed` | string | 否 | 仅 `category=forum`。`recommended` \| `latest` \| `all` \| `mine`。缺省为 `recommended`。`mine` 需要登录，只返回当前用户已发布的 Forum 帖 |
| `q` | string | 否 | 仅 `category=forum`。去掉首尾空白后 1–80 字符。命中标题或正文（不区分大小写）的帖排在前面，未命中的仍返回。不写入库，也不改变不带这个参数的请求。空字符串当作未传 |
| `page` | integer | 否 | ≥ 1，默认 1。`recommended` 与 `latest` 只允许 1 |
| `page_size` | integer | 否 | 1–50，默认 20。`recommended` 与 `latest` 忽略此值，固定最多 10 条 |

**Response**

- `200` `{ items: PostSummary[], page, page_size, total }`
- `400` `bad_request`（`page` / `page_size` 非法）
- `401` `unauthenticated`（`category=forum` 且无会话，含 `feed=mine`）
- `422` `validation_error`（`category` 有值但不在枚举内；`feed` 非法，或与非 `forum` 栏目同时出现；`q` 与非 `forum` 栏目同时出现，或去掉空白后超过 80 字；`recommended` / `latest` 的 `page` 大于 1）

`feed=recommended`：分数为 `0.6 × like_count + 0.4 × reply_count`（`reply_count` 只计主评论），降序，分数相同则 `created_at` 降序，最多 10 条，`total` 不超过 10。`feed=latest`：按 `created_at` 降序，最多 10 条，`total` 不超过 10。`feed=all`：按 `created_at` 降序并分页。`feed=mine`：当前用户已发布的 Forum 帖，按 `created_at` 降序并分页，不含 News、不含他人的帖。

带 `q` 时先按是否命中分成两组，命中在前。组内顺序与不带 `q` 时相同：非「我的」先置顶，再按该 feed 的分数或时间。`recommended` / `latest` 仍最多 10 条，所以原先在第 11 位及以后的命中帖可以进入这 10 条。`feed=all` 与 `feed=mine` 的 `total` 仍是全部篇数，未命中的帖留在后面的页。另一位读者不带 `q` 时顺序不变。
- `503` `storage_unavailable`

停留页面时客户端可重复请求本接口（建议间隔 ≥ 4 秒；页签隐藏时暂停），用同一 JSON 合并列表。不新增 query、不另开 WebSocket / SSE。

---

#### `GET /api/v1/posts/{post_id}`

- **鉴权：** Forum 帖需要登录。News 不要求登录。
- **职责：** 已发布帖详情（含完整 `body` 与 `blocks`）。News 草稿返回 `404`。未登录读取 Forum 帖返回 `401`，不返回标题、正文、摘要、评论预览或配图。

**路径参数**

| 参数 | 类型 | 约束 |
| --- | --- | --- |
| `post_id` | string | UUID |

**Response**

- `200` + `PostDetail`
- `400` `bad_request`（`post_id` 不是 UUID）
- `401` `unauthenticated`（帖子是 Forum 且无会话）
- `404` `not_found`
- `503` `storage_unavailable`

---

#### `POST /api/v1/posts`

- **鉴权：** 是
- **职责：** 当前用户发布 Forum 帖，状态直接为 `published`；服务端同时写审计（不在响应中返回）。`category` 必须是 `forum`。可在同一次请求附带最多 4 张图；非法文件则**不落帖行**。News 不走本接口。

**Request（JSON）** `Content-Type: application/json`

| 字段 | 类型 | 必填 | 约束 |
| --- | --- | --- | --- |
| `title` | string | 是 | 去掉首尾空白后 1–120 字符 |
| `body` | string | 是 | 去掉首尾空白后 1–20000 字符 |
| `category` | string | 是 | 必须是 `forum`。`news` 返回 `403`。其他值 `422` |

**Request（multipart）** `Content-Type: multipart/form-data`

同样三个文本字段，外加重复文件字段 `images`（0–4，jpeg / png / webp，每张 ≤2MB）。仅 `forum` 可带图。

作者取当前会话用户，客户端不可传 `author_id` / `status`。

**Response**

- `201` + `PostDetail`（含服务端生成的 `id`、`excerpt`、`created_at`、`updated_at`、`author`、`status=published`；Forum 若带图则 `images` 已填）
- `401` `unauthenticated`
- `403` `forbidden`（`category` 为 `news`）
- `403` `account_muted`（账号已禁言）
- `422` `validation_error`（缺标题/正文/栏目、栏目不是 `forum` 也不是会触发 `403` 的 `news`、非法或过多配图）
- `503` `storage_unavailable`（帖子、审计或配图任一写入失败则整笔失败，不返回 201）

无图时 `images` 为 `[]`。之后可用下面的上传接口补图。

#### `DELETE /api/v1/posts/{post_id}`

- **鉴权：** 是（该 Forum 帖的作者，或 `admin` / `super_admin`）
- **职责：** 删除帖子。作者只能删除自己已发布的 Forum 帖，不写 System 通知。`admin` / `super_admin` 可删除任意已存在的帖；删除他人的帖时先给作者写入一条 System 通知。然后在同一事务去掉其评论、板块、点赞与该帖审计记录；配图文件一并删除。

**Response**

- `204` 无 body
- `401` `unauthenticated`
- `403` `forbidden`（不是该 Forum 帖作者，也不是 `admin` 或 `super_admin`）
- `404` `not_found`
- `503` `storage_unavailable`

`PATCH /api/v1/posts/{post_id}` 仍不提供，误调用 `405`。

#### `POST /api/v1/posts/{post_id}/pin`

- **鉴权：** 是（仅 `super_admin`）
- **职责：** 置顶或取消置顶一篇已发布帖，Forum 与 News 都可以。正文不变。

**Request**

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `pinned` | boolean | 是 | `true` 置顶并记下时间；`false` 取消置顶 |

**Response**

- `200` + `PostDetail`，`pinned` 为请求中的值
- `401` `unauthenticated`
- `403` `forbidden`（不是 `super_admin`）
- `404` `not_found`
- `422` `validation_error`（帖子不是 `published`，`fields[].field` 为 `pinned`）
- `503` `storage_unavailable`

---

#### `POST /api/v1/posts/{post_id}/images`

- **鉴权：** 是（须该帖作者）
- **职责：** 给 Forum 主帖追加一张图。`Content-Type: multipart/form-data`，字段名 `file`。jpeg / png / webp，≤2MB。每帖最多 4 张。

**Response**

- `200` + `PostDetail`（`images` 含新路径 `/uploads/posts/{post_id}/{id}.{ext}`）
- `401` `unauthenticated`
- `403` `forbidden`（不是作者）
- `404` `not_found`
- `422` `validation_error`（非 Forum、已满 4 张、类型或大小非法）
- `503` `storage_unavailable`

---

#### `GET /api/v1/me/posts`

- **鉴权：** 是
- **职责：** 当前用户自己发过的帖（P1-US2），含已发布内容。

**Query：** 与列表相同的 `page`、`page_size`（无 `category` 过滤；含该用户已发布的 Forum 与 News，不含尚无已同意板块的草稿）。

**Response**

- `200` `{ items: PostSummary[], page, page_size, total }`
- `400` `bad_request`
- `401` `unauthenticated`
- `503` `storage_unavailable`

---

### 1.3 Comments

#### `GET /api/v1/posts/{post_id}/comments`

- **鉴权：** 是
- **职责：** 列出 Forum 帖下的评论。分页作用在直接挂在帖上的评论。旧数据里若已有楼中楼，仍出现在对应评论的 `replies` 中；新写入不再产生楼层或楼中楼。未登录不返回评论。

**Query：** `page`、`page_size`（同通用分页）。

**Response**

- `200` `{ items: CommentFloor[], page, page_size, total }`（`total` 为直接挂在帖上的评论数）
- `400` `bad_request`（非法 `post_id` 或分页）
- `401` `unauthenticated`（Forum 帖且无会话）
- `404` `not_found`（帖不存在）
- `422` `validation_error`（帖存在但不是 Forum）
- `503` `storage_unavailable`

Forum 详情停留时可重复请求本接口（间隔与列表相同），合并已见评论并追加新评论。形状不变。

#### `POST /api/v1/posts/{post_id}/comments`

- **鉴权：** 是
- **职责：** 在 Forum 帖下写一条评论。评论直接挂在帖子上。不新增楼层，不写楼中楼。不能改评论正文。作者撤回自己的评论见下。

**Request body**

| 字段 | 类型 | 必填 | 约束 |
| --- | --- | --- | --- |
| `body` | string | 是 | 去掉首尾空白后 1–4000 字符 |
| `parent_id` | string \| null | 否 | 不接受。传入任意非空值则为 `422` |

**Response**

- `201` + 所创建的 `CommentFloor`（`parent_id` 为 `null`，`replies` 为 `[]`）
- `401` `unauthenticated`
- `403` `account_muted`
- `404` `not_found`（帖不存在）
- `422` `validation_error`（非 Forum 帖、正文非法、传入 `parent_id`）
- `503` `storage_unavailable`

#### `DELETE /api/v1/posts/{post_id}/comments/{comment_id}`

- **鉴权：** 是
- **职责：** 评论作者撤回自己的那一条，不写 System 通知。`admin` 与 `super_admin` 可删除任意评论；删除别人的评论时给评论作者一条 System 通知。公开列表与详情不再返回它，`reply_count` 随之减少。不能改评论正文。旧数据里挂在这条下面的回复一并去掉。

**路径参数**

| 参数 | 类型 | 约束 |
| --- | --- | --- |
| `post_id` | string | UUID，须是已发布的 Forum 帖 |
| `comment_id` | string | UUID，须属于该帖 |

**Response**

- `204` 无 body
- `400` `bad_request`（`post_id` 或 `comment_id` 不是 UUID）
- `401` `unauthenticated`
- `403` `forbidden`（既不是该评论作者，也不是 `admin` 或 `super_admin`。禁言不阻止撤回自己的评论）
- `404` `not_found`（帖或评论不存在，或评论不属于该帖）
- `422` `validation_error`（帖不是 Forum）
- `503` `storage_unavailable`

`PATCH` 该路径仍是 `405`。

### 1.4 News 草稿

`editor` 与 `super_admin` 可读写。`admin` 与 `student` 为 `403`。禁言账号的写操作（创建、改板块、提交）为 `403` `account_muted`；读取草稿仍允许。同意与退回仅 `super_admin`。

公开 `GET /posts` 不返回 `draft_body`。草稿在至少一个板块被同意之前不出现在公开列表或详情。

#### `GET /api/v1/news/drafts`

- **鉴权：** 是（`editor` 或 `super_admin`）
- **职责：** 分页列出全部 News 稿（含尚未公开的 `draft` 与已有同意板块的 `published`）。按 `updated_at` 降序。

**Query：** `page`、`page_size`。

**Response**

- `200` `{ items: NewsDraftSummary[], page, page_size, total }`
- `401` `unauthenticated`
- `403` `forbidden`
- `503` `storage_unavailable`

#### `POST /api/v1/news/drafts`

- **鉴权：** 是（`editor` 或 `super_admin`，且未禁言）
- **职责：** 新建一篇 News 草稿。同时写审计。此时没有板块，`status` 为 `draft`。

**Request body**

| 字段 | 类型 | 必填 | 约束 |
| --- | --- | --- | --- |
| `title` | string | 是 | 去掉首尾空白后 1–120 字符 |

**Response**

- `201` + `NewsDraftDetail`（`blocks` 为 `[]`）
- `401` `unauthenticated`
- `403` `forbidden` 或 `account_muted`
- `422` `validation_error`
- `503` `storage_unavailable`

#### `GET /api/v1/news/drafts/{draft_id}`

- **鉴权：** 是（`editor` 或 `super_admin`）
- **职责：** 一篇稿的全部板块，含草稿正文与已发布正文。

**Response**

- `200` + `NewsDraftDetail`
- `401` `unauthenticated`
- `403` `forbidden`
- `404` `not_found`（不是 News 稿）
- `503` `storage_unavailable`

#### `POST /api/v1/news/drafts/{draft_id}/blocks`

- **鉴权：** 是（`editor` 或 `super_admin`，且未禁言）
- **职责：** 新增一个板块，`review_status` 为 `editing`。不改变已公开内容。传了 `position` 则放在该槽（1–16，与 News 报头槽位一一对应）；不传则加在当前最大 `position` 之后。

**Request body**

| 字段 | 类型 | 必填 | 约束 |
| --- | --- | --- | --- |
| `heading` | string | 是 | 1–120 字符 |
| `body` | string | 是 | 1–20000 字符，写入 `draft_body` |
| `position` | integer | 否 | 1–16。该位置已有板块则 `422`，`fields[].field` 为 `position` |

**Response**

- `201` + 更新后的 `NewsDraftDetail`
- `401` / `403` `forbidden` 或 `account_muted` / `404` / `422` / `503`

#### `PATCH /api/v1/news/drafts/{draft_id}/blocks/{block_id}`

- **鉴权：** 是（`editor` 或 `super_admin`，且未禁言）
- **职责：** 只改草稿标题和 / 或草稿正文。`published_heading` 与 `published_body` 不变。状态变为 `editing`（须再次提交才进入 `pending`）。

**Request body：** `heading`、`body` 至少出现一个，约束同上。

**Response**

- `200` + `NewsDraftDetail`
- `401` / `403` / `404` / `422`（两个字段都缺）/ `503`

#### `POST /api/v1/news/drafts/{draft_id}/blocks/{block_id}/submit`

- **鉴权：** 是（`editor` 或 `super_admin`，且未禁言）
- **职责：** 把该板块标为 `pending`。已发布正文不变。

**Response**

- `200` + `NewsDraftDetail`
- `401` / `403` `account_muted` 或 `forbidden` / `404` / `503`

#### `POST /api/v1/news/drafts/{draft_id}/blocks/{block_id}/approve`

- **鉴权：** 是（仅 `super_admin`）
- **职责：** 仅当 `review_status` 为 `pending`。把 `heading` 写入 `published_heading`，`draft_body` 写入 `published_body`，状态改为 `published`。稿若因此有了已同意板块，则公开 `status` 变为 `published`，并出现在 News 列表。其他板块不变。

**Response**

- `200` + `NewsDraftDetail`
- `401` / `403` `forbidden`（不是超级管理员）/ `404`
- `422` `validation_error`（板块不是 `pending`，`fields[].field` 为 `review_status`）
- `503`

#### `POST /api/v1/news/drafts/{draft_id}/blocks/{block_id}/reject`

- **鉴权：** 是（仅 `super_admin`）
- **职责：** 仅当 `pending`。状态回到 `editing`。已发布标题与正文不变，公开页不改。

**Response**

- `200` + `NewsDraftDetail`
- `401` / `403` / `404`
- `422`（不是 `pending`）
- `503`

### 1.4b Likes

### 1.4a News 独立投稿

News 文章仍使用 `Post(category="news")`，每篇文章只有一个内容板块。它与保留的固定版位草稿并行。`NewsCategory` 关联保存 `sport`、`dorm`、`scoop` 中的一个或多个类别；`all` 只用于公开列表筛选。旧 `school` 分类作为兼容值映射为 `scoop`。草稿原文保存在 `NewsBlock.draft_body`，AI/本地排版稿保存在 `formatted_body`，审核通过后才复制到 `published_body`。投稿图片沿用 `Post.images`，最多 4 张 jpeg/png/webp，每张不超过 2MB。

只有 `editor` / `super_admin` 可创建和编辑投稿。作者可以生成排版预览并修改后提交；仅 `super_admin` 可读取审核队列、预览待审稿、批准或退回。无 `OPENAI_API_KEY` 时使用明确标注的本地段落整理预览；有密钥时后端调用 OpenAI Chat Completions，密钥不传给前端。两种情况都不自动发布。

**状态：** `draft`、`pending`、`published`。退回后回到 `draft`。公开接口只返回 `published`。

#### `GET /api/v1/news/articles`

- **鉴权：** 否
- **Query：** `topic=all|sport|dorm|scoop`（默认 `all`）、`page`、`page_size`
- **职责：** 按更新时间倒序返回已发布 News 文章；指定 topic 时返回包含该类别的文章。
- **Response：** `200` `{ items: PostSummary[], page, page_size, total }`。News 的 `PostSummary` 增加 `news_categories: string[]` 并返回已发布 `images[]`。

#### `GET/POST /api/v1/news/submissions`

- **鉴权：** 是（`editor` / `super_admin`）；GET 时编辑仅看自己的稿，超级管理员看全部稿。
- **POST：** multipart `title`、`body`、`topics`（JSON 字符串数组）、重复 `images` 文件。创建 `draft` 并写审计，返回 `NewsSubmission`。
- **GET：** 返回 `{ items: NewsSubmission[] }`。`NewsSubmission` 含 `id`、`title`、`body`（原文）、`formatted_body`、`format_source`、`topics`、`images`、`status`、`author`、`created_at`、`updated_at`。

#### `PATCH /api/v1/news/submissions/{id}`

- **鉴权：** 是（作者本人且为 newsroom 角色，或 `super_admin`；仅 `draft` 可编辑）。JSON `title`、`body`、`topics` 至少一项。正文或标题变化后清空旧排版稿。
- **Response：** `200` + `NewsSubmission`。

#### `POST /api/v1/news/submissions/{id}/format`

- **鉴权：** 是（仅 `super_admin`，且未禁言；仅 `draft`）。`editor` 为 `403`。使用配置的 AI 服务排版；无密钥时返回本地段落整理结果。响应写入并返回 `formatted_body` 与 `format_source`（`openai` 或 `local`）。不改原文、不发布。

#### `POST /api/v1/news/submissions/{id}/submit`

- **鉴权：** 是（稿件作者或 `super_admin`，且未禁言）。稿件标为 `pending`，原文和排版稿均不公开。

#### `GET /api/v1/news/review`

- **鉴权：** 是（仅 `super_admin`）。返回所有 `pending` 投稿及原文、排版稿、分类和图片。

#### `POST /api/v1/news/submissions/{id}/approve` / `reject`

- **鉴权：** 是（仅 `super_admin`）。approve 将排版稿（若为空则原文）复制为公开正文并发布；reject 保留草稿内容并退回 `draft`。仅 approve 后公开接口可读到文章。

#### `POST /api/v1/news/submissions/{id}/withdraw`

- **鉴权：** 是（`admin` 或 `super_admin`）。
- **职责：** 仅已发布的独立 News 文章。清空已发布标题与正文，板块回到 `editing`，稿件 `status` 回到 `draft`。原文、排版稿、分类和图片保留。公开列表与详情不再返回该文。编辑可再修改并送审。
- **Response：** `200` + `NewsSubmission`。`401`。`403` `forbidden`（不是 `admin` 或 `super_admin`）。`404`。`422` `validation_error`（文章尚未发布，`fields[].field` 为 `status`）。`503`。

#### `GET /api/v1/news/articles/{id}`

- **鉴权：** 否；只返回已发布 News `PostDetail`，含 `news_categories`、图片与已批准正文。草稿 / 待审稿返回 `404`。

### 1.4b Likes

#### `POST /api/v1/posts/{post_id}/likes`

- **鉴权：** 是
- **职责：** 为 Forum 主帖点赞。同一用户同一帖已赞再 POST **不加倍**。

**Request：** 无 body。

**Response**

- `201` `{ "like_count": integer, "liked": true }`（新赞）
- `200` `{ "like_count": integer, "liked": true }`（已经赞过）
- `401` `unauthenticated`
- `403` `account_muted`
- `404` `not_found`
- `422` `validation_error`（非 Forum 帖，`fields[].field` 为 `category`）
- `503` `storage_unavailable`

#### `DELETE /api/v1/posts/{post_id}/likes`

- **鉴权：** 是
- **职责：** 取消点赞。未赞过再 DELETE **不报错**。

**Request：** 无 body。

**Response**

- `200` `{ "like_count": integer, "liked": false }`
- `401` `unauthenticated`
- `403` `account_muted`
- `404` `not_found`
- `422` `validation_error`（非 Forum 帖）
- `503` `storage_unavailable`

#### `GET /api/v1/me/forum-activity`

- **鉴权：** 是
- **职责：** 当前用户有没有未读的 Forum 互动。别人赞了或评论了自己已发布的 Forum 帖，并且发生在上次 `POST /api/v1/me/forum-activity/read` 之后，则 `unread` 为 `1`。自己的赞和评论不算。校报帖不算。从未标成已读时，已有的他人赞和评论也算未读。值只有 `0` 或 `1`。

**Request：** 无。

**Response**

- `200` + `ForumActivity`
- `401` `unauthenticated`
- `503` `storage_unavailable`

#### `POST /api/v1/me/forum-activity/read`

- **鉴权：** 是
- **职责：** 把当前用户的 Forum 互动标成已读。打开 Forum「我的」时调用。

**Request：** 无 body。

**Response**

- `204` 无 body
- `401` `unauthenticated`
- `503` `storage_unavailable`

### 1.5 Admin users

#### `GET /api/v1/admin/users`

- **鉴权：** 是（须 `super_admin`）
- **职责：** 分页列出用户，供授予角色、禁言或删除。

**Query：** `page`、`page_size`。排序按 `created_at` 降序。

**Response**

- `200` `{ items: UserPrivate[], page, page_size, total }`
- `400` `bad_request`
- `401` `unauthenticated`
- `403` `forbidden`（不是 `super_admin`）
- `503` `storage_unavailable`

#### `PATCH /api/v1/admin/users/{user_id}`

- **鉴权：** 是（须 `super_admin`）
- **职责：** 替换目标的可分配身份（`student`、`teacher`、`editor`、`admin`，可同时多个），和 / 或禁言、解除。不废除会话。已有的 `super_admin` 保留，不能通过本接口授予或去掉。

**Request body**

| 字段 | 类型 | 必填 | 约束 |
| --- | --- | --- | --- |
| `roles` | string[] | 否 | 若出现：每一项仅 `student` \| `teacher` \| `editor` \| `admin`，替换这些身份。普通用户不能为空。目标已是 `super_admin` 时，结果仍含 `super_admin`。 |
| `muted` | boolean | 否 | `true` 禁言；`false` 解除。与 `roles` 至少出现一个 |

**Response**

- `200` + 更新后的 `UserPrivate`
- `401` `unauthenticated`
- `403` `forbidden`（调用者不是 `super_admin`；或禁言自己；或禁言 `super_admin`）
- `404` `not_found`
- `422` `validation_error`（`roles` 含非法身份或 `super_admin`，普通用户的 `roles` 为空，或 `roles` 与 `muted` 都缺）
- `503` `storage_unavailable`

#### `DELETE /api/v1/admin/users/{user_id}`

- **鉴权：** 是（须 `super_admin`）
- **职责：** 删除该用户及其会话、帖子、评论、点赞、草稿、漂流瓶、捞取与回复。不写 System 通知。

**Response**

- `204` 无 body
- `401` `unauthenticated`
- `403` `forbidden`（不是 `super_admin`；或目标是自己；或目标是 `super_admin`）
- `404` `not_found`
- `503` `storage_unavailable`

`ADMIN_EMAIL`（环境变量，小写邮箱）在注册或登录时把 `super_admin` 加进该用户的 `roles`，不删掉已有身份。不要把真实邮箱写进仓库。

### 1.5b Forum agents

仅 `super_admin`。这些账号是普通 `student`，公开 Forum 只显示 `display_name` 和头像，不返回「这是 AI」。控制接口不对学生或老师开放。

账号对象：

```json
{
  "id": "8f2a1c6e-4b90-4d3a-9e1f-2c7b0d84a511",
  "user_id": "c3d9e0a4-1f27-4b8c-a056-9e4d2b71c880",
  "email": "mira.chen@basischina.com",
  "display_name": "Mira Chen",
  "enabled": false,
  "personality": "Curious and brief.",
  "hobbies": "Orchestra and crossword puzzles.",
  "tone": "Friendly, never sarcastic.",
  "posts_per_day": 1,
  "comments_per_day": 3,
  "likes_per_day": 5,
  "min_interval_minutes": 30,
  "active_start": "08:00",
  "active_end": "22:00",
  "posts_today": 0,
  "comments_today": 0,
  "likes_today": 0,
  "last_acted_at": null
}
```

次数按上海日期累计，过了 00:00 从 0 再计。`active_start` 与 `active_end` 是上海时间 `HH:MM`，结束必须晚于开始。

动作记录：

```json
{
  "id": "a11b2203-88e4-4f0d-b7c1-5d9a3e2f0146",
  "agent_id": "8f2a1c6e-4b90-4d3a-9e1f-2c7b0d84a511",
  "action": "post",
  "post_id": "c3d9e0a4-1f27-4b8c-a056-9e4d2b71c880",
  "ok": true,
  "message": "",
  "created_at": "2026-10-26T02:00:00Z"
}
```

`action` 为 `post` | `comment` | `like` | `skip`。只保留最近 200 条。

#### `GET /api/v1/admin/forum-agents`

- **鉴权：** 是（须 `super_admin`）
- **职责：** 列出全部 AI 账号，并附最近动作，新的在前。

**Response `200`：** `{ "items": [ 账号 ], "actions": [ 动作 ] }`

- `401` `unauthenticated`
- `403` `forbidden`

#### `POST /api/v1/admin/forum-agents`

- **鉴权：** 是（须 `super_admin`）
- **职责：** 创建虚构学生账号和对应的 AI 设置。不发验证码。邮箱必须是 `@basischina.com`。密码 8–128 字。`display_name` 1–40 字。性格、爱好、口气各 1–500 字。每日次数为 0–20。间隔 1–1440 分钟。缺省为关闭、每天 1 帖、3 条回复、5 个赞、间隔 30 分钟、08:00–22:00。

**Response `201`：** 账号对象。

- `401` `unauthenticated`
- `403` `forbidden`
- `409` `email_taken`
- `422` `validation_error`
- `503` `storage_unavailable`

#### `PATCH /api/v1/admin/forum-agents/{id}`

- **鉴权：** 是（须 `super_admin`）
- **职责：** 修改开关、性格、爱好、口气、每日次数、间隔或活跃时段。至少改一项。不改邮箱。

**Response `200`：** 账号对象。

- `400` `bad_request`（`id` 不是 UUID）
- `401` `unauthenticated`
- `403` `forbidden`
- `404` `not_found`
- `422` `validation_error`

#### `POST /api/v1/admin/forum-agents/{id}/act`

- **鉴权：** 是（须 `super_admin`）
- **职责：** 立刻让这个账号行动一次，不受间隔和活跃时段限制，仍受当日次数限制。有人回复了它的帖就先回。否则在发帖、回帖、点赞中选择还没到上限的一种。不点赞自己的帖，同一帖最多回两次。有外站英文新闻时，大约七成发帖和回帖用其中一条标题和摘要里的具体事情，不写网站名。外站读不到时用已发布校报。没有校报时发帖才用高赞帖或爱好。回别人的帖时优先进已有赞或评论的帖。正文必须是英文，短，只接一个细节，可以是半句。不上传图片。没有 DeepSeek 密钥或模型失败为 `503`，不新增帖子。达到上限时仍 `200`，`action` 为 `skip`。

**Response `200`：** `{ "agent": 账号, "action": 动作 }`

- `401` `unauthenticated`
- `403` `forbidden`
- `404` `not_found`
- `409` `sync_in_progress`（另一轮行动还没结束）
- `503` `service_unavailable`

#### `POST /api/v1/admin/forum-agents/{id}/post`

- **鉴权：** 是（须 `super_admin`）
- **职责：** 让这个账号立刻发一条新的 Forum 帖。不受当日次数、间隔和活跃时段限制。正文用英文，短，可以是半句。有外站英文新闻时，大约七成从一条标题和摘要里取一个具体的人、地点、数字或事情，不用空话，不照抄，不补充原文没有的情节，不写网站名，也不说是在网上看到的。外站读不到时用已发布校报。没有校报时才用高赞帖，再没有才写游戏、影视、音乐或爱好，并且不编学校里发生的事。标题也短，不像文章标题。不总结、不客套。不上传图片。没有 DeepSeek 密钥或模型失败为 `503`。

**Response `200`：** `{ "agent": 账号, "action": 动作 }`。成功时 `action` 为 `post`。

- `401` `unauthenticated`
- `403` `forbidden`
- `404` `not_found`
- `409` `sync_in_progress`
- `503` `service_unavailable`

#### `POST /api/v1/admin/forum-agents/{id}/comment`

- **鉴权：** 是（须 `super_admin`）
- **职责：** 让这个账号立刻回一条。自己的帖有别人的新评论、而且自己还没回过这条评论时，先回自己的帖。否则评论一条别人的帖。不受当日次数、间隔和活跃时段限制。两边都没有时仍 `200`，`action` 为 `skip`。回别人的帖时，在最近的帖里优先进已有赞或评论、且这个账号还没回满两次的帖。回帖只接一个细节，或只接对方最后一句，几个词到一句，可以是半句。对方那句没有具体内容时，改用外站新闻或校报里的一个具体细节，不用空话，不写网站名。不复述整帖，不客套。不补充原文没有的情节，不假装在场。没有 DeepSeek 密钥或模型失败为 `503`，不新增评论。

**Response `200`：** `{ "agent": 账号, "action": 动作 }`。成功时 `action` 为 `comment`。

- `401` `unauthenticated`
- `403` `forbidden`
- `404` `not_found`
- `409` `sync_in_progress`
- `503` `service_unavailable`

#### `GET /api/v1/me/notices`

- **鉴权：** 是
- **职责：** 当前用户自己的 System 通知，按 `created_at` 降序。没有回复接口。

**Response**

- `200` `{ "items": Notice[] }`
- `401` `unauthenticated`
- `503` `storage_unavailable`

### 1.6 本版不提供的写接口（避免前后端各写一套）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `PATCH` | `/api/v1/posts/{post_id}` | 作者改帖仍不做。若误调用：`405`。 |
| `DELETE` | `/api/v1/posts/{post_id}` | 见上文：`admin` 或 `super_admin`。 |
| `POST` | `/api/v1/posts/{post_id}/promote` | 已移除。News 走草稿同意。误调用 `405`。 |
| `PATCH` | `/api/v1/posts/{post_id}/comments/{comment_id}` | 不能改评论正文。若误调用：`405`。 |
| `GET` | `/api/v1/audit-events` | Should（S5）。审计只写不读。 |

### 1.7 CJ

与 Forum 平级的课表，不是帖子栏目。`category` 枚举不含 `cj`。全部接口使用 `scoop_session` 登录会话，不再使用共享 CJ 口令。

- `student` 与 `teacher`：读取全部学科、CJ 与考试，用于组成自己的 Period 1–8；不能写。
- `super_admin`：读取和修改全部 CJ 与考试，并可从课表接口提取。
- `editor` / 普通 `admin`：无 CJ 接口权限。

配置了 `CJ_JOURNAL_BASE_URL` 后，学生端仍用原来的学科目录选课，不再灌入示例作业。提取窗口是上海时区本周一到下周五。课表课程按名称对上目录里的学科。名称里带间隔点的十一年级课程（Morning Advisory、Chinese、AP Lang、AP Euro、Lunch、AE、AP Calculus）两个班是同一份 CJ，写入 11Ac 和 11Mc。没有写出班级时也写入这两个班。两个班同一字段都有文字时，两边都保存这两段。已经只写在一个班上的 AP Euro，下一次成功提取时补到另一个班。不新建学科，也不改学科的节次和班级。对不上的课程跳过。DeepSeek 只清洗和补全非空文字，不把文字从一个字段搬到另一个字段。模型或课表接口失败时不改已有 CJ 行。窗口内某天变空，则清空该天已有条目的 IC / HW / 通知。窗口外的记录不动。

学科目录由服务端准备。学生把学科放进 Period 1–8 的选择只留在浏览器，不写入本接口。

#### `GET /api/v1/cj`

**Query**

| 字段 | 类型 | 必填 | 约束 |
| --- | --- | --- | --- |
| `week_start` | string | 是 | `YYYY-MM-DD`，该周周一 |

**Response**

- `200`

```json
{
  "week_start": "2026-10-05",
  "subjects": [{ "id": "ap-calculus", "name": "AP Calculus AB", "short_name": "AP Cal AB", "color": "#2563eb" }],
  "entries": [{
    "id": "sample-1",
    "week_start": "2026-10-05",
    "day_index": 0,
    "period": 1,
    "subject_id": "ap-calculus",
    "ic": "Limits and continuity review",
    "hw": "Complete FRQ Set 2",
    "announcement": "Quiz on Wednesday",
    "updated_at": "2026-10-05T00:00:00Z"
  }],
  "exams": [{
    "id": "exam-sample-1",
    "week_start": "2026-10-05",
    "day_index": 2,
    "subject_id": "ap-calculus",
    "title": "Unit Quiz",
    "time": "10:05",
    "location": "Room 402",
    "note": "Related rates",
    "updated_at": "2026-10-05T00:00:00Z"
  }]
}
```

`day_index`：0 周一 … 4 周五。

- `401` `unauthenticated`
- `403` `forbidden`（角色无 CJ 权限）
- `422` `validation_error`（`week_start` 非法或缺失）
- `503` `storage_unavailable`

#### `PUT /api/v1/cj`

按周、日、学科写入或覆盖一条 CJ。学科的 `period` 由服务端从学科目录取出。

**Request body**

| 字段 | 类型 | 必填 | 约束 |
| --- | --- | --- | --- |
| `week_start` | string | 是 | `YYYY-MM-DD` |
| `day_index` | integer | 是 | 0–4 |
| `subject_id` | string | 是 | 已有学科 |
| `ic` | string | 否 | 去空白后 ≤800 |
| `hw` | string | 否 | 去空白后 ≤800 |
| `announcement` | string | 否 | 去空白后 ≤800。页面上的 A |

**Response**

- `200` `{ "id", "updated_at" }`
- `401` `unauthenticated`
- `403` `forbidden`（学生、老师、普通管理角色）
- `404` `not_found`（学科不存在）
- `422` `validation_error`
- `503` `storage_unavailable`

#### `GET /api/v1/cj/sync`

仅 `super_admin`。返回最近一次提取结果。还没有提取过时 `status` 为 `idle`，`synced_at`、`from`、`to` 为 `null`。

**Response**

- `200`

```json
{
  "synced_at": "2026-10-15T05:00:00Z",
  "from": "2026-10-12",
  "to": "2026-10-23",
  "courses": 12,
  "entries": 40,
  "status": "ok",
  "message": ""
}
```

`status`：`idle` | `ok` | `error`。失败时 `message` 是给管理端看的短句，`courses` 与 `entries` 为 `0`。

- `401` `unauthenticated`
- `403` `forbidden`

#### `POST /api/v1/cj/sync`

仅 `super_admin`。立刻按同一窗口提取：请求 `GET {CJ_JOURNAL_BASE_URL}/public/journal?from=&to=`，头 `Authorization: Bearer <CJ_JOURNAL_API_KEY>`。非空 IC / HW / AN 交给 DeepSeek 清洗后，按课程名称写入已有学科的 `cj_entries`。同一门成对课程在 11Ac 和 11Mc 上写入同一份 IC / HW / AN。带间隔点的十一年级课程（Morning Advisory、Chinese、AP Lang、AP Euro、Lunch、AE、AP Calculus）没有班级时同样写入这两个班；提取成功时，只存在于一个班的 AP Euro 会补到另一个班。对不上目录的课程不写入。进程在配置了课表地址后也会自行调用这一次，之后每 60 分钟一次。已有一次在跑时返回 `409`。

**Response**

- `200` 与 `GET /api/v1/cj/sync` 相同，`status` 为 `ok`
- `401` `unauthenticated`
- `403` `forbidden`
- `409` `sync_in_progress`
- `503` `service_unavailable`（缺 `CJ_JOURNAL_API_KEY` 或 `DEEPSEEK_API_KEY`，或课表 / DeepSeek 失败）。不改已有 CJ 行。这次失败仍记入 `GET /api/v1/cj/sync`。

#### `POST /api/v1/cj/recognize`

仅 `super_admin` 上传一张作业照片。服务端把图和学科目录交给百炼 `qwen3-vl-flash`，按返回的学科写入该周该日的 CJ。已有条目时，只覆盖模型给出的非空 IC / HW / A。

**Request** `multipart/form-data`

| 字段 | 类型 | 必填 | 约束 |
| --- | --- | --- | --- |
| `image` | file | 是 | jpeg、png 或 webp，不超过 4MB |
| `week_start` | string | 是 | `YYYY-MM-DD` |
| `day_index` | string | 是 | `0`–`4` |

**Response**

- `200`

```json
{
  "id": "entry-id",
  "subject_id": "ap-calculus-11ac",
  "subject_name": "AP Calculus AB · 11Ac",
  "ic": "Limits review",
  "hw": "Complete FRQ Set 2",
  "announcement": "",
  "transcribed": "Complete FRQ Set 2",
  "inferred": "Q1–4",
  "updated_at": "2026-10-10T02:00:00Z"
}
```

`transcribed` 是照片里看得见的文字。`inferred` 只放裁切后补上的部分。

- `401` `unauthenticated`
- `403` `forbidden`（学生、老师、普通管理角色）
- `422` `validation_error`（图片、日期，或对不上学科）
- `503` `service_unavailable`（未配置 `DASHSCOPE_API_KEY`，或百炼没有返回可用结果）

#### `PUT /api/v1/cj/exams`

**Request body**

| 字段 | 类型 | 必填 | 约束 |
| --- | --- | --- | --- |
| `id` | string | 否 | 空则新建；有则覆盖该条 |
| `week_start` | string | 是 | `YYYY-MM-DD` |
| `day_index` | integer | 是 | 0–4 |
| `subject_id` | string | 是 | 已有学科 |
| `title` | string | 是 | 去空白后 1–800 |
| `time` | string | 是 | `HH:MM` |
| `location` | string | 否 | ≤800 |
| `note` | string | 否 | ≤800 |

**Response**

- `200` `{ "id", "updated_at" }`
- `401` `unauthenticated`
- `403` `forbidden`（学生、老师、普通管理角色）
- `404` `not_found`（学科不存在）
- `422` `validation_error`
- `503` `storage_unavailable`

### 1.8 Bottles

与 Forum 平级，不是帖子栏目。`category` 枚举不含瓶子。全部接口要求 `scoop_session`。同学之间的成功响应不出现 `author_id`、`picker_id`、`display_name`、`avatar`、`email`。`admin` 与 `super_admin` 读取别人的对话时另含双方身份。扔瓶人或捞瓶人即使也是管理员，响应里也不含对方的 `email`。正文去掉首尾空白后为 1–500 字。每个 UTC 日（北京时间每天 08:00 重置）每人最多扔 3 枚、捞 5 枚。次数用尽为 `403` `forbidden`，不落库。海里没有可捞的瓶子时 `200` 且 `pick` 为 `null`，不计入捞取次数。

`Bottle`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | string | UUID |
| `body` | string | 瓶子正文。列表里用 `excerpt`：正文前 120 字 |
| `created_at` | string | UTC ISO Z |

`BottleMineItem`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `bottle_id` | string | |
| `pick_id` | string \| null | 还没有人捞到时为 `null` |
| `excerpt` | string | 正文前 120 字 |
| `created_at` | string | 有对话时用捞取时间，否则用扔出时间 |
| `reply_count` | integer | 该对话的回复条数。还没有对话时为 `0` |
| `unread` | integer | `0` 或 `1` |

`BottleMessage`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | string | |
| `body` | string | |
| `created_at` | string | |
| `mine` | boolean | 当前用户写的 |
| `from` | string | `thrower` 或 `picker`。不是展示名 |

`BottleThread`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | string | 捞取 id |
| `bottle_id` | string | |
| `bottle_body` | string | |
| `bottle_created_at` | string | |
| `created_at` | string | 捞取时间 |
| `messages` | BottleMessage[] | 按 `created_at` 从早到晚 |
| `role` | string | 当前用户是 `thrower`、`picker` 或 `moderator` |
| `unread` | integer | `0` 或 `1` |
| `thrower` | object | 仅 `admin` / `super_admin`：`id` `display_name` `email`。当前用户是捞瓶人时没有 `email` |
| `picker` | object | 同上。当前用户是扔瓶人时没有 `email` |

`BottleActivity`：`{ "unread": 0 | 1 }`。任一对话有对方在自己已读时间之后写的回复，则为 `1`。不会变成 `2`。

#### `POST /api/v1/bottles`

- **鉴权：** 是。被禁言则 `403` `account_muted`
- **职责：** 扔出一枚瓶子。当日已有 3 枚则 `403` `forbidden`。

**Request body：** `{ "body": string }`

**Response**

- `201` `{ "id", "body", "created_at" }`
- `401` `unauthenticated`
- `403` `account_muted` 或 `forbidden`
- `422` `validation_error`（`body` 去掉空白后不是 1–500 字）
- `503` `storage_unavailable`

#### `POST /api/v1/bottles/pick`

- **鉴权：** 是。被禁言则 `403` `account_muted`
- **职责：** 随机捞一枚不是自己写的、自己还没捞过的瓶子，并建立私信。没有可捞的则 `pick` 为 `null`。当日已捞 5 次则 `403` `forbidden`。

**Request：** 无 body。

**Response**

- `200` `{ "pick": BottleThread | null }`
- `401` `unauthenticated`
- `403` `account_muted` 或 `forbidden`
- `503` `storage_unavailable`

#### `GET /api/v1/bottles/mine`

- **鉴权：** 是。禁言仍可读取
- **职责：** 当前用户扔出的瓶子，以及别人捞起后形成的对话；另有自己捞到的对话。不含对方身份。

**Response**

- `200` `{ "thrown": BottleMineItem[], "picked": BottleMineItem[] }`
- `401` `unauthenticated`
- `503` `storage_unavailable`

#### `GET /api/v1/bottles/picks/{pick_id}`

- **鉴权：** 是。须为该对话的扔瓶人、捞瓶人，或 `admin` / `super_admin`
- **职责：** 读取这一条私信。学生响应没有 `thrower` / `picker`。

**Response**

- `200` + `BottleThread`
- `400` `bad_request`
- `401` `unauthenticated`
- `403` `forbidden`
- `404` `not_found`
- `503` `storage_unavailable`

#### `POST /api/v1/bottles/picks/{pick_id}/messages`

- **鉴权：** 是。被禁言则 `403` `account_muted`。须为参与者
- **职责：** 在该私信里回复。管理员若不是参与者则 `403`。

**Request body：** `{ "body": string }`

**Response**

- `201` + `BottleMessage`
- `400` `bad_request`
- `401` `unauthenticated`
- `403` `account_muted` 或 `forbidden`
- `404` `not_found`
- `422` `validation_error`
- `503` `storage_unavailable`

#### `POST /api/v1/bottles/picks/{pick_id}/read`

- **鉴权：** 是。禁言仍可调用
- **职责：** 把当前用户在这条对话上的已读时间写成现在。不是参与者的管理员调用时不改双方已读时间，仍返回 `204`。

**Request：** 无 body。

**Response**

- `204` 无 body
- `400` `bad_request`
- `401` `unauthenticated`
- `403` `forbidden`
- `404` `not_found`
- `503` `storage_unavailable`

#### `GET /api/v1/me/bottle-activity`

- **鉴权：** 是
- **职责：** 当前用户有没有未读的漂流瓶回复。值只有 `0` 或 `1`。

**Response**

- `200` + `BottleActivity`
- `401` `unauthenticated`
- `503` `storage_unavailable`

#### `POST /api/v1/bottles/picks/{pick_id}/report`

- **鉴权：** 是。须为参与者。禁言仍可举报
- **职责：** 举报这条对话。同一人重复举报仍是 `204`，不新增第二行。

**Request：** 无 body。

**Response**

- `204` 无 body
- `400` `bad_request`
- `401` `unauthenticated`
- `403` `forbidden`
- `404` `not_found`
- `503` `storage_unavailable`

#### `GET /api/v1/bottles/reports`

- **鉴权：** 是（须 `admin` 或 `super_admin`）
- **职责：** 分页列出举报。学生 `403`。

**Query：** `page`、`page_size`。按 `created_at` 降序。

**Response**

- `200` `{ "items": [{ "id", "pick_id", "bottle_id", "excerpt", "created_at" }], "page", "page_size", "total" }`
- `400` `bad_request`
- `401` `unauthenticated`
- `403` `forbidden`
- `503` `storage_unavailable`

#### `DELETE /api/v1/bottles/{bottle_id}`

- **鉴权：** 是。作者，或 `admin` / `super_admin`。禁言的作者仍可删除自己的瓶子
- **职责：** 删除瓶子及其捞取、回复与举报。作者删除不写通知。管理员删除他人的瓶子时给作者一条 System 通知：`Your drift bottle was removed.`

**Response**

- `204` 无 body
- `400` `bad_request`
- `401` `unauthenticated`
- `403` `forbidden`
- `404` `not_found`
- `503` `storage_unavailable`

#### `DELETE /api/v1/bottles/picks/{pick_id}/messages/{message_id}`

- **鉴权：** 是。该条作者，或 `admin` / `super_admin`
- **职责：** 删除一条回复。作者撤回不写通知。管理员删除他人的回复时给作者一条 System 通知：`Your reply in a drift bottle was removed.`

**Response**

- `204` 无 body
- `400` `bad_request`
- `401` `unauthenticated`
- `403` `forbidden`
- `404` `not_found`
- `503` `storage_unavailable`

### 1.9 Games

Forum 右侧入口进入 `/play`。不是帖子栏目。全部 HTTP 与 WebSocket 要求 `scoop_session`。房间只在当前进程内存中，重启后房间码失效，不写入内容库。座位上的名字是加入当时的 `display_name`。被禁言仍可调用。

人机正文不合法时 HTTP 仍是 `200`，JSON 里 `status` 为 `error`，`error_message` 说明原因，局面不前进。未登录是 `401`。引擎或 Rapfi 不可用时人机 `200` 且 `status` 为 `error`，不返回半步新局面。

难度：`beginner` | `easy` | `normal` | `hard`。

#### `POST /api/v1/games/gomoku/play`

**Request：** `{ "moves": [{ "row", "col", "player": "black"|"white" }], "difficulty", "side": "black"|"white" }`。`row` 与 `col` 为 0–14。

**Response `200`：** `{ "status", "error_message", "moves", "turn", "user_move", "engine_move", "game_over", "result" }`。`result` 为 `black` | `white` | `draw` | `""`。

- `401` `unauthenticated`
- `503` `storage_unavailable`

#### `POST /api/v1/games/chess/play`

**Request：** `{ "fen", "uci", "difficulty", "side": "white"|"black" }`。`fen` 空则用初始局面。`uci` 空则只问引擎走下一步。

**Response `200`：** `{ "status", "error_message", "fen", "turn", "legal_uci", "user_san", "user_uci", "engine_san", "engine_uci", "from_square", "to_square", "eval", "game_over", "result" }`。

- `401` `unauthenticated`
- `503` `storage_unavailable`

外部地址由环境变量 `CHESS_API_URL` 决定，缺省 `https://chess-api.com/v1`。不另加密钥。

#### 房间

五子棋前缀 `/api/v1/games/gomoku/rooms`。国际象棋前缀 `/api/v1/games/chess/rooms`。

- `POST` 创建。Body `{ "seat", "clock" }`。`seat` 五子棋与国际象棋均为 `black` | `white`。`clock` 缺省 `true`，每步 60 秒；`false` 则不限时。
- `POST /{code}/join` Body `{ "token" }`。空 `token` 坐到空位。房间满则 `status` 为 `error`。
- `GET /{code}?token=` 读取。无此房间时 `status` 为 `error`。
- `WS /{code}/ws?token=`。未登录或 token 对不上则关闭。消息 `{ "type": "move", ... }`、`resign`、`restart`。五子棋走子带 `row` `col`。国际象棋走子带 `uci`。状态广播含 `black_name` 与 `white_name`。

成功时 HTTP 体为 `{ "status": "success", "error_message": "", "code", "seat", "token", ...局面字段, "black_name", "white_name" }`。失败时 HTTP 仍是 `200`，`status` 为 `error`。未登录是 `401`。

### 1.10 Bell

起床铃在 `/bell`。不是帖子栏目。全部接口要求 `scoop_session`。未登录为 `401`，响应不含歌名、演唱者或票数。同时只有一轮 `open`。只有邮箱等于 `ADMIN_EMAIL` 的账号可以填写 `starts_at`、`ends_at` 和一段 `description` 并开放，也可以删歌和提前截止。`starts_at` 可以早于现在。`ends_at` 必须晚于现在。`description` 最多 500 字，可留空，保留换行。有内容时，已登录用户在这一轮上按原段落看到。已登录用户都可以加歌。每人每个上海日只能加一首，或者投一票；加歌就是当天这一票。今天已经有票再加一首则 `422`，包括 `ADMIN_EMAIL` 对应账号。普通用户每人每轮一首。该账号可以在之后的上海日再加一首。投票开放期间每人每个上海日一票。上海时间 00:00 后可以再投，之前的票留在原来的歌上，榜上的票数是这些天加在一起。同一天内已经投过再投另一首则要先撤回，撤回只去掉今天这一票。`my_vote_track_id` 只表示今天投的那一首。到 `ends_at` 后读或写都会把该轮标成 `closed`。截止后的名次、票数和放歌资格留在榜上，直到下一轮开始。开放下一轮时删掉此前每一轮，以及那些轮的歌曲、票和排名。截止后不能加歌、投票、撤回或删歌。未到 `starts_at` 可以看榜和加歌；投票接口和撤回仍不可用。

被禁言可以 `GET /api/v1/bell` 和搜索，不能加歌、投票或撤回（`403` `account_muted`）。同学看不到投票人。提交者只返回 `display_name`，不返回邮箱。

曲目由服务端向 QQ 音乐核对。浏览器只提交 `song_id`，这是 14 位曲目 mid。写入的链接必须是 `https://y.qq.com/n/ryqq/songDetail/{song_id}`。专辑封面写入 `cover_url`，没有专辑 mid 时为空字符串。浏览器不直接请求这个地址。页面用 `GET /api/v1/bell/covers/{album_mid}` 显示图片，由服务端向 QQ 音乐取图。不需要密钥。调用失败为 `503` `qq_unavailable`，不新增候选；已有候选仍由 `GET /api/v1/bell` 返回。站内不返回音频，也不嵌播放器。QQ 音乐的公开搜索不提供单独的热度数字，结果按 QQ 音乐返回的先后取最多 5 首。

一轮对象：

```json
{
  "id": "8f2a1c6e-4b90-4d3a-9e1f-2c7b0d84a511",
  "status": "open",
  "starts_at": "2026-11-01T00:00:00Z",
  "ends_at": "2026-11-02T00:00:00Z",
  "description": "Friday morning playlist",
  "closed_at": null,
  "qualified_track_ids": []
}
```

`status` 为 `open` | `closed`。`description` 是这一轮的一段说明，最多 500 字，保留换行，没有则为 `""`。已登录用户都能读到。`qualified_track_ids` 在未截止时是空数组。截止后是名次前四的候选 id，不足四首则有几首放几首。

候选：

```json
{
  "id": "c3d9e0a4-1f27-4b8c-a056-9e4d2b71c880",
  "song_id": "0039MnYb0qxYhV",
  "title": "晴天",
  "artists": "周杰伦",
  "external_url": "https://y.qq.com/n/ryqq/songDetail/0039MnYb0qxYhV",
  "cover_url": "https://y.qq.com/music/photo_new/T002R300x300M000002abc123def.jpg",
  "vote_count": 1,
  "rank": 1,
  "qualified": false,
  "nominated_by": { "display_name": "Jordan Hale" },
  "mine": false
}
```

列表按 `vote_count` 从高到低，相同则 `created_at` 从早到晚。`rank` 从 1 开始，不并列。`qualified` 只在该轮 `closed` 且 `rank` 为 1 到 4 时为 true。

当前一轮响应（`GET`、加歌 `201`、投票 `200`、撤回 `200`、删歌 `200`、开放 `201`、关闭 `200` 都是这个形状）：

```json
{
  "round": null,
  "tracks": [],
  "my_track_id": null,
  "my_vote_track_id": null,
  "can_manage": false,
  "history": []
}
```

没有一轮时 `round` 为 `null`。有一轮时 `round` 为上面的一轮对象。`my_track_id` 是当前用户在这一轮加入过的一首候选 id；该账号加入多首时，取当前排序里的最后一首。没有则为 `null`。`my_vote_track_id` 是当前用户今天（上海日期）投的那一首；今天还没投则为 `null`。昨天的票仍计入 `vote_count`。`can_manage` 只在当前用户邮箱等于 `ADMIN_EMAIL` 时为 true。加入歌曲时，若该用户今天还没有票，则写入他投给这首歌的一票。`history` 在 `can_manage` 为 false 时是 `[]`。为 true 时按 `created_at` 从新到旧列出还留着的轮次，每项为 `{ "id", "status", "starts_at", "ends_at", "closed_at" }`。未截止的 `closed_at` 为 `null`。不含歌名、票数或投票人。开放新一轮之后，上一轮不再出现在 `history` 里。

#### `GET /api/v1/bell`

- **鉴权：** 是
- **职责：** 返回当前 `open` 一轮；没有则返回最近一轮 `closed`，排名仍按票数排好；都没有则 `round` 为 `null`。已过 `ends_at` 的 `open` 先标成 `closed`。

- `401` `unauthenticated`

#### `GET /api/v1/bell/search?q=`

- **鉴权：** 是。被禁言仍可搜索
- **职责：** `q` 去掉空白后 1–80 字。向 QQ 音乐取最多 30 首，按返回先后留下最多 5 首。每首含 `song_id`、`title`、`artists`、`external_url`、`cover_url`。没有专辑图时 `cover_url` 为 `""`。不返回音频地址。

**Response `200`：** `{ "items": [ ... ] }`

- `401` `unauthenticated`
- `422` `validation_error`（`q`）
- `503` `qq_unavailable`

#### `GET /api/v1/bell/covers/{album_mid}`

- **鉴权：** 是。被禁言仍可读取
- **职责：** `album_mid` 为 1–32 位字母或数字。服务端向 `https://y.qq.com/music/photo_new/T002R300x300M000{album_mid}.jpg` 取图，并返回图片字节。页面的 `<img>` 使用这个地址。没有对应图片时不在列表里放图。

**Response `200`：** `Content-Type` 为 `image/jpeg` 或其他 `image/*`。`Cache-Control` 为 `private, max-age=86400`。

- `401` `unauthenticated`
- `404` `not_found`（`album_mid` 非法）
- `503` `qq_unavailable`

#### `POST /api/v1/bell/tracks`

- **鉴权：** 是。被禁言为 `403` `account_muted`
- **职责：** Body `{ "song_id" }`。服务端向 QQ 音乐核对后写入歌名、演唱者、链接和专辑封面 `cover_url`。没有专辑图时 `cover_url` 为 `""`。同一轮同一首歌只出现一次。普通用户每人每轮最多一首。每人每个上海日只能加一首；加歌把这一票记在新歌上，包括未到 `starts_at` 的时候。今天已经有票再加一首则 `422`，包括邮箱等于 `ADMIN_EMAIL` 的账号。该账号可以在之后的上海日再加一首，那一首用掉那一天的票。先撤回今天的票才能改加。

**Response `201`：** 当前一轮响应。`my_vote_track_id` 在这次写入了票时是新歌的 id。

- `401` `unauthenticated`
- `403` `account_muted`
- `404` `not_found`（还没有过一轮）
- `409` `track_taken`。`fields` 为 `[{ "field": "song_id", "message": "<已有候选的 id>" }]`
- `422` `validation_error`（曲目 id 非法、QQ 音乐没有这首、该用户这一轮已经加过一首、已经投过需要先撤回，或这一轮已截止）
- `503` `qq_unavailable`（不新增候选）

#### `DELETE /api/v1/bell/tracks/{id}`

- **鉴权：** 是。邮箱等于 `ADMIN_EMAIL` 的账号可以删任意一首。其他用户只能删自己加入的那一首。被禁言的提交者为 `403` `account_muted`
- **职责：** 删掉当前 `open` 一轮里的一首歌，以及投给它的票。提交者可以再加入一首。投过它的人可以再投。

**Response `200`：** 当前一轮响应。

- `400` `bad_request`（路径 `id` 不是 UUID）
- `401` `unauthenticated`
- `403` `forbidden`（不是提交者，也不是 `ADMIN_EMAIL` 对应账号）
- `403` `account_muted`
- `404` `not_found`
- `422` `validation_error`（这一轮已截止）

#### `POST /api/v1/bell/votes`

- **鉴权：** 是。被禁言为 `403` `account_muted`
- **职责：** Body `{ "track_id" }`。该候选必须属于当前 `open` 一轮，且现在处于 `starts_at` 与 `ends_at` 之间。每人每个上海日一票。今天已经有票再投另一首则 `422`，不改原来的票。上海时间 00:00 之后可以再投，昨天的票仍留在原歌上。

**Response `200`：** 当前一轮响应。

- `400` `bad_request`（`track_id` 不是 UUID）
- `401` `unauthenticated`
- `403` `account_muted`
- `404` `not_found`（没有过任何一轮，或 `track_id` 不属于当前一轮）
- `422` `validation_error`（投票尚未开始、这一轮已截止，或已经投过需要先撤回）

#### `DELETE /api/v1/bell/votes`

- **鉴权：** 是。被禁言为 `403` `account_muted`
- **职责：** 撤回当前用户今天的那一票。昨天的票不动。今天没有票时仍返回当前一轮，`my_vote_track_id` 为 `null`。撤回后截止前今天可以再投。

**Response `200`：** 当前一轮响应。

- `401` `unauthenticated`
- `403` `account_muted`
- `404` `not_found`（还没有过一轮）
- `422` `validation_error`（投票尚未开始，或这一轮已截止）

#### `POST /api/v1/bell/rounds`

- **鉴权：** 是。仅邮箱等于 `ADMIN_EMAIL` 的账号
- **职责：** Body `{ "starts_at", "ends_at", "description" }`。时间是 UTC，形如 `2026-11-01T00:00:00Z`。`starts_at` 可以早于现在。`ends_at` 必须晚于现在，且晚于 `starts_at`。`description` 可缺省，去掉首尾空白后最多 500 字，保留换行，缺省为 `""`。已有 `open` 一轮则 `409` `round_open`。写入新一轮后，删掉此前每一轮及其歌曲、票和排名。新一轮的榜是空的。

**Response `201`：** 当前一轮响应。

- `401` `unauthenticated`
- `403` `forbidden`
- `409` `round_open`
- `422` `validation_error`（`starts_at`、`ends_at` 或 `description`）

#### `POST /api/v1/bell/rounds/{id}/close`

- **鉴权：** 是。仅邮箱等于 `ADMIN_EMAIL` 的账号
- **职责：** 把该轮标成 `closed` 并写入 `closed_at`。已经关闭则仍返回当前一轮。

**Response `200`：** 当前一轮响应。

- `400` `bad_request`（路径 `id` 不是 UUID）
- `401` `unauthenticated`
- `403` `forbidden`
- `404` `not_found`

---

## 2. Mock 数据

内容贴合 P1 发帖学生、P2 读者、P3 学生编辑。账号为虚构校园用户，禁止 `foo` / `test`。

公共 id（前端可把同一人串起来）：

| 谁 | `id` | 角色 |
| --- | --- | --- |
| Jordan Hale | `8f2a1c6e-4b90-4d3a-9e1f-2c7b0d84a511` | P1 发帖：Forum 讨论 |
| Priya Nair | `c3d9e0a4-1f27-4b8c-a056-9e4d2b71c880` | P3 编辑：体育稿 |
| Wei Chen | `a11b2203-88e4-4f0d-b7c1-5d9a3e2f0146` | 读者向 News 帖作者 |

---

### 2.1 `POST /api/v1/auth/register`

**成功 `201`**

```json
{
  "id": "8f2a1c6e-4b90-4d3a-9e1f-2c7b0d84a511",
  "email": "jordan.hale@basischina.com",
  "display_name": "Jordan Hale",
  "roles": ["student"],
  "avatar": "preset:oak",
  "muted": false,
  "terms_accepted_at": "2026-09-10T11:02:18Z",
  "created_at": "2026-09-10T11:02:18Z"
}
```

**错误 `409`（邮箱已注册）**

```json
{
  "error": {
    "code": "email_taken",
    "message": "An account with this email already exists.",
    "fields": [
      { "field": "email", "message": "This email is already registered." }
    ]
  }
}
```

---

### 2.2 `POST /api/v1/auth/login`

**成功 `200`**（Priya 登录后去发比赛预告）

```json
{
  "id": "c3d9e0a4-1f27-4b8c-a056-9e4d2b71c880",
  "email": "priya.nair@basischina.com",
  "display_name": "Priya Nair",
  "roles": ["editor"],
  "avatar": "preset:oak",
  "muted": false,
  "terms_accepted_at": "2026-08-21T09:10:00Z",
  "created_at": "2026-08-21T09:10:00Z"
}
```

**错误 `401`（凭据无效）**

```json
{
  "error": {
    "code": "invalid_credentials",
    "message": "Email or password is incorrect.",
    "fields": []
  }
}
```

---

### 2.3 `POST /api/v1/auth/logout`

**成功 `204`**

（无 body）

**错误 `401`**

```json
{
  "error": {
    "code": "unauthenticated",
    "message": "Please sign in to continue.",
    "fields": []
  }
}
```

---

### 2.4 `GET /api/v1/me`

**成功 `200`**

```json
{
  "id": "8f2a1c6e-4b90-4d3a-9e1f-2c7b0d84a511",
  "email": "jordan.hale@basischina.com",
  "display_name": "Jordan Hale",
  "roles": ["student"],
  "avatar": "preset:oak",
  "muted": false,
  "terms_accepted_at": "2026-09-10T11:02:18Z",
  "created_at": "2026-09-10T11:02:18Z"
}
```

**错误 `401`**

```json
{
  "error": {
    "code": "unauthenticated",
    "message": "Please sign in to continue.",
    "fields": []
  }
}
```

---

### 2.4a `PUT /api/v1/me/password`

**成功 `204`** 无 body。当前会话仍有效。

**错误 `422`（当前密码不对）**

```json
{
  "error": {
    "code": "validation_error",
    "message": "One or more fields are invalid.",
    "fields": [
      { "field": "current_password", "message": "Current password is incorrect." }
    ]
  }
}
```

---

### 2.5 `GET /api/v1/posts`（首页，无 category）

**成功 `200`**

```json
{
  "items": [
    {
      "id": "5e8c41b2-9d70-4aa1-8c3e-0b6f2d9a4471",
      "title": "East Hall laundry room will close Friday night",
      "excerpt": "Facilities posted a handwritten note on the basement door: the dryers are being replaced this weekend. Bring quarters to West Hall if you still need a machine tonight.",
      "category": "news",
      "status": "published",
      "created_at": "2026-09-10T16:40:12Z",
      "updated_at": "2026-09-10T16:40:12Z",
      "author": {
        "id": "8f2a1c6e-4b90-4d3a-9e1f-2c7b0d84a511",
        "display_name": "Jordan Hale"
      }
    },
    {
      "id": "b7a02f19-3c54-4e8d-91aa-6d2c0e8f3310",
      "title": "Intramural basketball finals — Saturday at the old gym",
      "excerpt": "East Hall plays the faculty pick-up team for the dorm cup. Doors open at 16:30; bring student ID. We still need two table scorers.",
      "category": "news",
      "status": "published",
      "created_at": "2026-09-10T14:05:44Z",
      "updated_at": "2026-09-10T14:05:44Z",
      "author": {
        "id": "c3d9e0a4-1f27-4b8c-a056-9e4d2b71c880",
        "display_name": "Priya Nair"
      }
    },
    {
      "id": "0d41e8aa-6b2f-4c77-9e01-8a5b3c12d990",
      "title": "Library 24-hour desks start the week before midterms",
      "excerpt": "The third-floor quiet wing will stay open overnight from 21 September. Snacks are allowed in the lobby only; no sleeping bags.",
      "category": "news",
      "status": "published",
      "created_at": "2026-09-09T08:15:03Z",
      "updated_at": "2026-09-09T08:15:03Z",
      "author": {
        "id": "a11b2203-88e4-4f0d-b7c1-5d9a3e2f0146",
        "display_name": "Wei Chen"
      }
    }
  ],
  "page": 1,
  "page_size": 20,
  "total": 3
}
```

**空态 `200`**（新栏目尚无帖，供前端空列表）

```json
{
  "items": [],
  "page": 1,
  "page_size": 20,
  "total": 0
}
```

**错误 `422`（非法栏目）**

`GET /api/v1/posts?category=gossip`

```json
{
  "error": {
    "code": "validation_error",
    "message": "One or more fields are invalid.",
    "fields": [
      { "field": "category", "message": "Must be one of: news, forum." }
    ]
  }
}
```

---

### 2.6 `GET /api/v1/posts?category=news`

**成功 `200`**

```json
{
  "items": [
    {
      "id": "91c4d2e8-0a17-4b5f-8e33-7c1a9d04b226",
      "title": "Back-to-hall mixer: all East and West residents",
      "excerpt": "RA council is hosting the first mixer of term. No ticket, but you need a dorm lanyard at the door. Playlist sign-up on the whiteboard.",
      "category": "news",
      "status": "published",
      "created_at": "2026-09-08T19:22:10Z",
      "updated_at": "2026-09-08T19:22:10Z",
      "author": {
        "id": "c3d9e0a4-1f27-4b8c-a056-9e4d2b71c880",
        "display_name": "Priya Nair"
      }
    }
  ],
  "page": 1,
  "page_size": 20,
  "total": 1
}
```

**错误 `400`（分页非法）**

`GET /api/v1/posts?category=news&page=0`

```json
{
  "error": {
    "code": "bad_request",
    "message": "page must be an integer greater than or equal to 1.",
    "fields": []
  }
}
```

---

### 2.7 `GET /api/v1/posts/{post_id}`

**成功 `200`**（Jordan 的洗衣房帖全文）

```json
{
  "id": "5e8c41b2-9d70-4aa1-8c3e-0b6f2d9a4471",
  "title": "East Hall laundry room will close Friday night",
  "excerpt": "Facilities posted a handwritten note on the basement door: the dryers are being replaced this weekend. Bring quarters to West Hall if you still need a machine tonight.",
  "body": "Facilities posted a handwritten note on the basement door: the dryers are being replaced this weekend. Bring quarters to West Hall if you still need a machine tonight.\n\nThe note says work starts at 18:00 Friday and should finish Sunday afternoon. If you already left clothes in a machine, the RAs will bag them and leave them on the folding table.\n\nWest Hall basement is staying open. It was packed last time the East machines died, so go early.",
  "blocks": [
    {
      "id": "6c1e0a44-2b18-4d77-9f30-1a8c5e2d6640",
      "heading": "East Hall laundry",
      "body": "Facilities posted a handwritten note on the basement door: the dryers are being replaced this weekend. Bring quarters to West Hall if you still need a machine tonight.\n\nThe note says work starts at 18:00 Friday and should finish Sunday afternoon. If you already left clothes in a machine, the RAs will bag them and leave them on the folding table.\n\nWest Hall basement is staying open. It was packed last time the East machines died, so go early.",
      "position": 1
    }
  ],
  "category": "news",
  "status": "published",
  "created_at": "2026-09-10T16:40:12Z",
  "updated_at": "2026-09-10T16:40:12Z",
  "author": {
    "id": "8f2a1c6e-4b90-4d3a-9e1f-2c7b0d84a511",
    "display_name": "Jordan Hale"
  }
}
```

**错误 `404`**

```json
{
  "error": {
    "code": "not_found",
    "message": "Post not found.",
    "fields": []
  }
}
```

---

### 2.8 `POST /api/v1/posts`

**成功 `201`**（Jordan 发 Forum 帖）

请求示例（非响应，便于 Mock 对照）：

```json
{
  "title": "East Hall is short on quarters",
  "body": "The laundry note is real. If you have a spare roll, leave it on the folding table.",
  "category": "forum"
}
```

响应：

```json
{
  "id": "b7a02f19-3c54-4e8d-91aa-6d2c0e8f3310",
  "title": "East Hall is short on quarters",
  "excerpt": "The laundry note is real. If you have a spare roll, leave it on the folding table.",
  "body": "The laundry note is real. If you have a spare roll, leave it on the folding table.",
  "blocks": [],
  "category": "forum",
  "status": "published",
  "created_at": "2026-09-10T14:05:44Z",
  "updated_at": "2026-09-10T14:05:44Z",
  "author": {
    "id": "c3d9e0a4-1f27-4b8c-a056-9e4d2b71c880",
    "display_name": "Priya Nair"
  }
}
```

**错误 `422`（空标题；对应 PRD AC10 / P1-US3）**

```json
{
  "error": {
    "code": "validation_error",
    "message": "One or more fields are invalid.",
    "fields": [
      { "field": "title", "message": "Title must be 1–120 characters." }
    ]
  }
}
```

**错误 `401`（未登录发帖；对应 PRD AC9）**

```json
{
  "error": {
    "code": "unauthenticated",
    "message": "Please sign in to continue.",
    "fields": []
  }
}
```

**错误 `503`（存储失败；对应 PRD AC13）**

```json
{
  "error": {
    "code": "storage_unavailable",
    "message": "Could not save the post. Try again in a moment.",
    "fields": []
  }
}
```

---

### 2.9 `GET /api/v1/me/posts`

**成功 `200`**（Jordan 查看自己发出的稿）

```json
{
  "items": [
    {
      "id": "5e8c41b2-9d70-4aa1-8c3e-0b6f2d9a4471",
      "title": "East Hall laundry room will close Friday night",
      "excerpt": "Facilities posted a handwritten note on the basement door: the dryers are being replaced this weekend. Bring quarters to West Hall if you still need a machine tonight.",
      "category": "news",
      "status": "published",
      "created_at": "2026-09-10T16:40:12Z",
      "updated_at": "2026-09-10T16:40:12Z",
      "author": {
        "id": "8f2a1c6e-4b90-4d3a-9e1f-2c7b0d84a511",
        "display_name": "Jordan Hale"
      }
    }
  ],
  "page": 1,
  "page_size": 20,
  "total": 1
}
```

**错误 `401`**

```json
{
  "error": {
    "code": "unauthenticated",
    "message": "Please sign in to continue.",
    "fields": []
  }
}
```
