# Elegram API 契约（第一版）

依据：`docs/PRD.md` Must Have 与 Entity Flow。本文件同时约束前端 Mock 与后端实现。不包含业务代码。

第一版 **无公开审计查询接口**（M10 仅服务端落库）。作者不能改自己的帖或评论，也不能删评论。作者可以删除自己已发布的 Forum 帖，不能删除他人的帖，也不能删除 News。`admin` 与 `super_admin` 可整帖删除；删除他人的帖时给作者一条 System 通知。仅 `super_admin` 可禁言或删除用户。包含 Forum 评论、角色、News 分板块草稿与独立 News 投稿。新评论直接挂在帖子上，不新增楼层或楼中楼。

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

公开读接口（栏目列表、详情、首页列表、Forum 评论列表）**不**要求鉴权。

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
| 403 | `forbidden` | 已登录但无权（直接发 News、非编辑写草稿、非超级管理员改角色 / 禁言 / 删用户 / 同意板块 / 导入 Teams CJ、既不是该 Forum 帖作者也不是 `admin` / `super_admin` 时删帖） |
| 403 | `account_muted` | 已登录但被禁言，仍调用发帖、跟帖、点赞、创建或提交草稿 |
| 404 | `not_found` | 帖子、评论父楼或用户不存在 |
| 409 | `email_taken` | 注册邮箱已被占用 |
| 422 | `validation_error` | 缺必填、超长、非法栏目、非法配图、非校内邮箱后缀、验证码无效或过期、注册时 `accept_terms` 不是 `true` |
| 503 | `storage_unavailable` | 存储写入失败，或 Teams / DeepSeek 调用失败；不得返回成功或半截资源 |

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
| `reply_preview` | ReplyPreview[] | Forum 最多 4 条楼层（无楼中楼）。其他列表为 `[]`。Forum **列表 UI 不展示**此字段 |
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

- **鉴权：** 否。`feed=mine` 需要登录。
- **职责：** 列出已发布帖。无 `category` 时供首页近期露出，**只含** `news`，不含 Forum，不含尚无已同意板块的 News 草稿。有 `category` 时只返回该栏目。

**Query**

| 参数 | 类型 | 必填 | 约束 |
| --- | --- | --- | --- |
| `category` | string | 否 | 若出现必须是 `news` \| `forum` |
| `feed` | string | 否 | 仅 `category=forum`。`recommended` \| `latest` \| `all` \| `mine`。缺省为 `recommended`。`mine` 需要登录，只返回当前用户已发布的 Forum 帖 |
| `page` | integer | 否 | ≥ 1，默认 1。`recommended` 与 `latest` 只允许 1 |
| `page_size` | integer | 否 | 1–50，默认 20。`recommended` 与 `latest` 忽略此值，固定最多 10 条 |

**Response**

- `200` `{ items: PostSummary[], page, page_size, total }`
- `400` `bad_request`（`page` / `page_size` 非法）
- `401` `unauthenticated`（`feed=mine` 且无会话）
- `422` `validation_error`（`category` 有值但不在枚举内；`feed` 非法，或与非 `forum` 栏目同时出现；`recommended` / `latest` 的 `page` 大于 1）

`feed=recommended`：分数为 `0.6 × like_count + 0.4 × reply_count`（`reply_count` 只计主评论），降序，分数相同则 `created_at` 降序，最多 10 条，`total` 不超过 10。`feed=latest`：按 `created_at` 降序，最多 10 条，`total` 不超过 10。`feed=all`：按 `created_at` 降序并分页。`feed=mine`：当前用户已发布的 Forum 帖，按 `created_at` 降序并分页，不含 News、不含他人的帖。
- `503` `storage_unavailable`

停留页面时客户端可重复请求本接口（建议间隔 ≥ 4 秒；页签隐藏时暂停），用同一 JSON 合并列表。不新增 query、不另开 WebSocket / SSE。

---

#### `GET /api/v1/posts/{post_id}`

- **鉴权：** 否
- **职责：** 已发布帖详情（含完整 `body` 与 `blocks`）。News 草稿返回 `404`。

**路径参数**

| 参数 | 类型 | 约束 |
| --- | --- | --- |
| `post_id` | string | UUID |

**Response**

- `200` + `PostDetail`
- `400` `bad_request`（`post_id` 不是 UUID）
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

- **鉴权：** 否
- **职责：** 列出 Forum 帖下的评论。分页作用在直接挂在帖上的评论。旧数据里若已有楼中楼，仍出现在对应评论的 `replies` 中；新写入不再产生楼层或楼中楼。

**Query：** `page`、`page_size`（同通用分页）。

**Response**

- `200` `{ items: CommentFloor[], page, page_size, total }`（`total` 为直接挂在帖上的评论数）
- `400` `bad_request`（非法 `post_id` 或分页）
- `404` `not_found`（帖不存在）
- `422` `validation_error`（帖存在但不是 Forum）
- `503` `storage_unavailable`

Forum 详情停留时可重复请求本接口（间隔与列表相同），合并已见评论并追加新评论。形状不变。

#### `POST /api/v1/posts/{post_id}/comments`

- **鉴权：** 是
- **职责：** 在 Forum 帖下写一条评论。评论直接挂在帖子上。不新增楼层，不写楼中楼。本版不能改删评论。

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
- **职责：** 删除该用户及其会话、帖子、评论、点赞与草稿。不写 System 通知。

**Response**

- `204` 无 body
- `401` `unauthenticated`
- `403` `forbidden`（不是 `super_admin`；或目标是自己；或目标是 `super_admin`）
- `404` `not_found`
- `503` `storage_unavailable`

`ADMIN_EMAIL`（环境变量，小写邮箱）在注册或登录时把 `super_admin` 加进该用户的 `roles`，不删掉已有身份。不要把真实邮箱写进仓库。

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
| `PATCH` / `DELETE` | `/api/v1/posts/{post_id}/comments/{comment_id}` | 本版不能改删单条评论。若误调用：`405`。 |
| `GET` | `/api/v1/audit-events` | Should（S5）。审计只写不读。 |

### 1.7 CJ

与 Forum 平级的课表，不是帖子栏目。`category` 枚举不含 `cj`。全部接口使用 `scoop_session` 登录会话，不再使用共享 CJ 口令。

- `student`：读取全部学科、CJ 与考试，用于组成自己的 Period 1–8；不能写。
- `teacher`：只读取和更新 `CJTeacherSubject` 分配给自己的唯一学科，包括该学科的 CJ 与考试。
- `super_admin`：读取和修改全部 CJ、考试与老师学科分配。
- `editor` / 普通 `admin`：无 CJ 接口权限。

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
- `403` `forbidden`（学生、普通管理角色，或老师写未分配学科）
- `404` `not_found`（学科不存在）
- `422` `validation_error`
- `503` `storage_unavailable`

#### `POST /api/v1/cj/recognize`

老师或 `super_admin` 上传一张作业照片。服务端把图和学科目录交给百炼 `qwen3-vl-flash`，按返回的学科写入该周该日的 CJ。已有条目时，只覆盖模型给出的非空 IC / HW / A。

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
- `403` `forbidden`
- `422` `validation_error`（图片、日期，或对不上学科）
- `503` `service_unavailable`（未配置 `DASHSCOPE_API_KEY`，或百炼没有返回可用结果）

#### `PUT /api/v1/cj/exams`

**Request body**

| 字段 | 类型 | 必填 | 约束 |
| --- | --- | --- | --- |
| `id` | string | 否 | 空则新建；有则覆盖该条 |
| `week_start` | string | 是 | `YYYY-MM-DD` |
| `day_index` | integer | 是 | 0–4 |
| `subject_id` | string | 是 | 已有学科；老师只能选分配给自己的学科 |
| `title` | string | 是 | 去空白后 1–800 |
| `time` | string | 是 | `HH:MM` |
| `location` | string | 否 | ≤800 |
| `note` | string | 否 | ≤800 |

**Response**

- `200` `{ "id", "updated_at" }`
- `401` `unauthenticated`
- `403` `forbidden`（学生、普通管理角色，或老师写入未分配学科）
- `404` `not_found`（学科不存在）
- `422` `validation_error`
- `503` `storage_unavailable`

#### `GET /api/v1/cj/teachers`

仅 `super_admin`。返回所有 `teacher` 账号以及每人的 `subject_ids`，供完整管理端配置。

#### `PUT /api/v1/cj/teachers/{teacher_id}`

仅 `super_admin`。Body 为 `{ "subject_ids": ["ap-calculus"] }`，整体替换该老师唯一可读写的 CJ 学科；数组允许为空，但最多一个元素。

- `200` `{ "id", "email", "display_name", "subject_ids" }`
- `401` `unauthenticated`
- `403` `forbidden`
- `404` `not_found`（账号不存在或不是老师）
- `422` `validation_error`（学科不存在或格式错误）

#### `GET /api/v1/cj/teams/status`

仅 `super_admin`。报告 Teams 是否已连接、DeepSeek 与 Microsoft 应用是否已配置。响应不含刷新令牌、访问令牌或 API key。

- `200`

```json
{
  "teams_connected": false,
  "deepseek_configured": false,
  "microsoft_configured": false
}
```

- `401` `unauthenticated`
- `403` `forbidden`

#### `POST /api/v1/cj/teams/connect`

仅 `super_admin`。开始 Microsoft 登录。成功时返回授权地址，浏览器转到该地址。登录完成后，微软把浏览器带到 `GET /api/v1/cj/teams/callback`。回调不是 JSON：校验一次性 `state` 与当前超级管理员会话，用授权码换刷新令牌，只在服务端保存，再重定向到 `{FRONTEND_ORIGIN}/cj/admin?teams=connected`。失败重定向到同一页 `?teams=error`，地址里不带令牌。

**Response**

- `200` `{ "authorize_url": "https://login.microsoftonline.com/..." }`
- `401` `unauthenticated`
- `403` `forbidden`
- `503` `storage_unavailable`（Microsoft 应用未配置）

#### `POST /api/v1/cj/teams/preview`

仅 `super_admin`。Body 只有 `week_start`（`YYYY-MM-DD`）。读取已连接账号能看到的群聊文字，交给 DeepSeek，返回将写入与将跳过的条目。不写 `CJEntry`。

将写入的每条为 `subject_id`、`day_index`（0–4）、`ic`、`hw`、`announcement`。跳过原因：`unknown_subject`、`invalid_day`、`field_too_long`、`empty`、`duplicate`、`invalid_payload`。跳过项的 `day_index` 无法识别时为 `null`。

- `200`

```json
{
  "week_start": "2026-10-05",
  "entries": [{
    "subject_id": "ap-calculus-11ac",
    "day_index": 0,
    "ic": "Limits and continuity review",
    "hw": "Complete FRQ Set 2",
    "announcement": "Quiz on Wednesday"
  }],
  "skipped": [{
    "subject_id": "not-a-course",
    "day_index": 0,
    "reason": "unknown_subject"
  }]
}
```

- `401` `unauthenticated`
- `403` `forbidden`
- `422` `validation_error`（`week_start` 非法或缺失）
- `503` `storage_unavailable`（未连接 Teams、未配置 DeepSeek，或 Graph / DeepSeek 失败）。不写入 CJ

#### `POST /api/v1/cj/teams/apply`

仅 `super_admin`。Body 为 `week_start` 与预览返回的 `entries`。服务端再次校验：只覆盖通过校验的周、日、学科槽的 `ic`、`hw`、`announcement`。无效条目进入 `skipped`，不写入。任一条目落库失败则整笔回滚。

- `200` `{ "week_start": "2026-10-05", "written": 1, "skipped": [] }`
- `401` `unauthenticated`
- `403` `forbidden`
- `422` `validation_error`
- `503` `storage_unavailable`（写入失败；不留下半截 CJ）

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
