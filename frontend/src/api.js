const BASE = import.meta.env.VITE_API_BASE || "/api/v1";

export class ApiError extends Error {
  constructor(status, error) {
    super(error?.message || "Request failed.");
    this.name = "ApiError";
    this.status = status;
    this.code = error?.code || "bad_request";
    this.fields = error?.fields || [];
  }
}

async function request(path, options = {}) {
  let res;
  try {
    res = await fetch(`${BASE}${path}`, {
      credentials: "include",
      ...options,
      headers: {
        ...(options.body && !(options.body instanceof FormData) ? { "Content-Type": "application/json" } : {}),
        ...options.headers,
      },
    });
  } catch {
    throw new ApiError(0, {
      code: "storage_unavailable",
      message: "Could not reach the server.",
      fields: [],
    });
  }

  if (res.status === 204) return null;

  let data = null;
  try {
    data = await res.json();
  } catch {
    data = null;
  }

  if (!res.ok) {
    throw new ApiError(
      res.status,
      data?.error || { code: "bad_request", message: "Request failed.", fields: [] },
    );
  }
  return data;
}

async function uploadFile(path, file) {
  const body = new FormData();
  body.append("file", file);
  let res;
  try {
    res = await fetch(`${BASE}${path}`, {
      method: "POST",
      credentials: "include",
      body,
    });
  } catch {
    throw new ApiError(0, {
      code: "storage_unavailable",
      message: "Could not reach the server.",
      fields: [],
    });
  }

  let data = null;
  try {
    data = await res.json();
  } catch {
    data = null;
  }

  if (!res.ok) {
    throw new ApiError(
      res.status,
      data?.error || { code: "bad_request", message: "Request failed.", fields: [] },
    );
  }
  return data;
}

export const api = {
  me: () => request("/me"),
  changePassword: (body) =>
    request("/me/password", { method: "PUT", body: JSON.stringify(body) }),
  setAvatarPreset: (preset) =>
    request("/me/avatar", { method: "PUT", body: JSON.stringify({ preset }) }),
  uploadAvatar: (file) => uploadFile("/me/avatar", file),
  login: (body) => request("/auth/login", { method: "POST", body: JSON.stringify(body) }),
  register: (body) => request("/auth/register", { method: "POST", body: JSON.stringify(body) }),
  sendEmailCode: (body) => request("/auth/email-codes", { method: "POST", body: JSON.stringify(body) }),
  resetPassword: (body) => request("/auth/password-reset", { method: "POST", body: JSON.stringify(body) }),
  logout: () => request("/auth/logout", { method: "POST" }),
  listPosts: ({ category, feed, page = 1, pageSize = 20 } = {}) => {
    const query = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
    });
    if (category) query.set("category", category);
    if (feed) query.set("feed", feed);
    return request(`/posts?${query}`);
  },
  getPost: (id) => request(`/posts/${encodeURIComponent(id)}`),
  createPost: (body, files = []) => {
    if (files.length) {
      const form = new FormData();
      form.append("title", body.title);
      form.append("body", body.body);
      form.append("category", body.category);
      files.slice(0, 4).forEach((file) => form.append("images", file));
      return request("/posts", { method: "POST", body: form });
    }
    return request("/posts", { method: "POST", body: JSON.stringify(body) });
  },
  uploadPostImage: (postId, file) => uploadFile(`/posts/${encodeURIComponent(postId)}/images`, file),
  myPosts: ({ page = 1, pageSize = 20 } = {}) => {
    const query = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
    });
    return request(`/me/posts?${query}`);
  },
  listComments: (postId, { page = 1, pageSize = 20 } = {}) => {
    const query = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
    });
    return request(`/posts/${encodeURIComponent(postId)}/comments?${query}`);
  },
  createComment: (postId, body) =>
    request(`/posts/${encodeURIComponent(postId)}/comments`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  notices: () => request("/me/notices"),
  listDrafts: ({ page = 1, pageSize = 20 } = {}) => {
    const query = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
    });
    return request(`/news/drafts?${query}`);
  },
  createDraft: (title) =>
    request("/news/drafts", { method: "POST", body: JSON.stringify({ title }) }),
  getDraft: (id) => request(`/news/drafts/${encodeURIComponent(id)}`),
  addBlock: (draftId, { heading, body, position }) =>
    request(`/news/drafts/${encodeURIComponent(draftId)}/blocks`, {
      method: "POST",
      body: JSON.stringify({
        heading,
        body,
        ...(position == null ? {} : { position }),
      }),
    }),
  patchBlock: (draftId, blockId, body) =>
    request(`/news/drafts/${encodeURIComponent(draftId)}/blocks/${encodeURIComponent(blockId)}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  submitBlock: (draftId, blockId) =>
    request(`/news/drafts/${encodeURIComponent(draftId)}/blocks/${encodeURIComponent(blockId)}/submit`, {
      method: "POST",
    }),
  approveBlock: (draftId, blockId) =>
    request(`/news/drafts/${encodeURIComponent(draftId)}/blocks/${encodeURIComponent(blockId)}/approve`, {
      method: "POST",
    }),
  rejectBlock: (draftId, blockId) =>
    request(`/news/drafts/${encodeURIComponent(draftId)}/blocks/${encodeURIComponent(blockId)}/reject`, {
      method: "POST",
    }),
  listNewsArticles: ({ topic = "all", page = 1, pageSize = 20 } = {}) => {
    const query = new URLSearchParams({ topic, page: String(page), page_size: String(pageSize) });
    return request(`/news/articles?${query}`);
  },
  getNewsArticle: (id) => request(`/news/articles/${encodeURIComponent(id)}`),
  listNewsSubmissions: () => request("/news/submissions"),
  createNewsSubmission: (formData) => request("/news/submissions", { method: "POST", body: formData }),
  patchNewsSubmission: (id, body) =>
    request(`/news/submissions/${encodeURIComponent(id)}`, { method: "PATCH", body: JSON.stringify(body) }),
  addNewsSubmissionImages: (id, formData) =>
    request(`/news/submissions/${encodeURIComponent(id)}/images`, { method: "POST", body: formData }),
  removeNewsSubmissionImage: (id, image) =>
    request(`/news/submissions/${encodeURIComponent(id)}/images`, { method: "DELETE", body: JSON.stringify({ image }) }),
  formatNewsSubmission: (id) =>
    request(`/news/submissions/${encodeURIComponent(id)}/format`, { method: "POST" }),
  submitNewsSubmission: (id, mode) =>
    request(`/news/submissions/${encodeURIComponent(id)}/submit`, { method: "POST", body: JSON.stringify({ mode }) }),
  listNewsReview: () => request("/news/review"),
  getNewsReview: (id) => request(`/news/review/${encodeURIComponent(id)}`),
  approveNewsSubmission: (id) =>
    request(`/news/submissions/${encodeURIComponent(id)}/approve`, { method: "POST" }),
  rejectNewsSubmission: (id) =>
    request(`/news/submissions/${encodeURIComponent(id)}/reject`, { method: "POST" }),
  publishNewsSubmission: (id, mode) =>
    request(`/news/submissions/${encodeURIComponent(id)}/publish`, { method: "POST", body: JSON.stringify({ mode }) }),
  withdrawNewsSubmission: (id) =>
    request(`/news/submissions/${encodeURIComponent(id)}/withdraw`, { method: "POST" }),
  listUsers: ({ page = 1, pageSize = 20 } = {}) => {
    const query = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
    });
    return request(`/admin/users?${query}`);
  },
  patchUserRoles: (userId, roles) =>
    request(`/admin/users/${encodeURIComponent(userId)}`, {
      method: "PATCH",
      body: JSON.stringify({ roles }),
    }),
  setUserMuted: (userId, muted) =>
    request(`/admin/users/${encodeURIComponent(userId)}`, {
      method: "PATCH",
      body: JSON.stringify({ muted }),
    }),
  deleteUser: (userId) => request(`/admin/users/${encodeURIComponent(userId)}`, { method: "DELETE" }),
  deletePost: (postId) => request(`/posts/${encodeURIComponent(postId)}`, { method: "DELETE" }),
  pinPost: (postId, pinned) =>
    request(`/posts/${encodeURIComponent(postId)}/pin`, {
      method: "POST",
      body: JSON.stringify({ pinned }),
    }),
  readCj: (weekStart) => {
    const query = new URLSearchParams({ week_start: weekStart });
    return request(`/cj?${query}`);
  },
  saveCj: (body) =>
    request("/cj", {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  recognizeCj: (file, { weekStart, dayIndex }) => {
    const body = new FormData();
    body.append("image", file);
    body.append("week_start", weekStart);
    body.append("day_index", String(dayIndex));
    return request("/cj/recognize", { method: "POST", body });
  },
  saveExam: (body) =>
    request("/cj/exams", {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  deleteExam: (examId) =>
    request(`/cj/exams/${encodeURIComponent(examId)}`, { method: "DELETE" }),
  createCjSubject: (body) =>
    request("/cj/subjects", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  deleteCjSubject: (subjectId) =>
    request(`/cj/subjects/${encodeURIComponent(subjectId)}`, { method: "DELETE" }),
  listCjTeachers: () => request("/cj/teachers"),
  assignCjTeacherSubjects: (teacherId, subjectIds) =>
    request(`/cj/teachers/${encodeURIComponent(teacherId)}`, {
      method: "PUT",
      body: JSON.stringify({ subject_ids: subjectIds }),
    }),
  likePost: (postId) => request(`/posts/${encodeURIComponent(postId)}/likes`, { method: "POST" }),
  unlikePost: (postId) => request(`/posts/${encodeURIComponent(postId)}/likes`, { method: "DELETE" }),
  forumActivity: () => request("/me/forum-activity"),
  readForumActivity: () => request("/me/forum-activity/read", { method: "POST" }),
};

export function fieldMessage(error, field) {
  return error?.fields?.find((item) => item.field === field)?.message || "";
}

export function safeNext(value) {
  if (typeof value !== "string") return "/";
  if (value.startsWith("/") && !value.startsWith("//")) return value;
  return "/";
}
