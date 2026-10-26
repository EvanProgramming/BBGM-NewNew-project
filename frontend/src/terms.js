function p(text, bold = false) {
  return { text, bold };
}

export const TERMS = {
  en: {
    title: "User agreement",
    makers: "Founders: Tori Zhao and Jason Fang. This site was built by Leo Gao, Ben Lyu, Dewey Peng, and Tori Zhao. The newsletter is contributed by Media Club.",
    covers: "It covers Elegram: registration, sign-in, reading, Forum posts and comments, News copy, accounts, and notices.",
    version: "Version date: 26 October 2026.",
    lead: [
      p("Read this agreement before you register. "),
      p("Bold text covers account responsibility, security duties, and how violations are handled. ", true),
      p("Checking agree and finishing registration forms this agreement with the makers named above. If you only browse public pages and do not register, you still follow the security duties below."),
    ],
    sections: [
      {
        heading: "1. Scope",
        paragraphs: [
          p("1.1 Tori Zhao and Jason Fang founded this site. Leo Gao, Ben Lyu, Dewey Peng, and Tori Zhao built it for students at the same school to read the paper and talk on Forum. Media Club contributes the newsletter."),
          p("1.2 This agreement covers account security, how you use the site, and how the makers handle security. It is not a government filing, and the makers do not file reports to an authority through this site."),
          p("1.3 The site has no payments, no recommendation ranking, and no automatic review. A Forum post is public as soon as it is published. A News section stays off the public page until a super admin approves it."),
          p("1.4 This forum is an English forum. Please use English on Forum."),
        ],
      },
      {
        heading: "2. Account and identity",
        paragraphs: [
          p("2.1 Registration and password reset accept only an email address ending in @basischina.com. Any other suffix cannot register and does not receive a code."),
          p("2.2 Registration needs a valid email code and acceptance of this agreement. Without acceptance, no account is created."),
          p("2.3 The account is for you alone. ", true),
          p("Do not lend, rent, or sell it. Do not register with someone else’s email or display name, and do not sign in with someone else’s password."),
          p("2.4 A display name must not impersonate another person, or copy the name of an authority, a school, or a news organization. An avatar must be an image you have the right to use."),
        ],
      },
      {
        heading: "3. Password and session",
        paragraphs: [
          p("3.1 You set and keep your own password. Do not tell it to anyone, and do not leave it on a shared computer. ", true),
          p("After sign-in you can change it with your current password. If you forget it, use a code sent to your registered email and set a new one."),
          p("3.2 The server stores the password only as a hash, not as plain text. API responses do not return the password."),
          p("3.3 After sign-in, the browser stores a session cookie named scoop_session. The cookie is HttpOnly and SameSite=Lax, and it identifies the signed-in user. Sign out when you finish on a shared computer."),
          p("3.4 If someone else is using your account, a code looks wrong, or your password may have leaked, change the password at once and sign out other sessions. ", true),
          p("You answer for sign-in and posts that follow from failing to keep the password."),
        ],
      },
      {
        heading: "4. Your security duties",
        paragraphs: [
          p("While using this site, you must not:"),
          p("4.1 Break into another account, guess or collect someone else’s password, or skip sign-in and permission checks."),
          p("4.2 Upload or spread malicious files, interfere with the site, or probe, scan, or load-test an interface that is not open to you."),
          p("4.3 Post or spread illegal material, including content that endangers national security, rumors, obscenity, pornography, gambling, violence, terrorism or extremism, insults, defamation, or another person’s private information."),
          p("4.4 Harass someone, or post and comment while pretending to be someone else."),
          p("4.5 Collect, copy, or publish another user’s email, or registration details other than the avatar and display name, or use information from this site to harass someone."),
          p("4.6 Use Forum or News material you have no right to use in a way that harms someone else’s rights. You are responsible for the text and images you publish."),
        ],
      },
      {
        heading: "5. What the makers will do",
        paragraphs: [
          p("5.1 The makers protect accounts and content with what the site already does: a school-email check, verification codes, password hashes, an HttpOnly session cookie, and role limits on posting, drafts, and user management."),
          p("5.2 An admin can delete a published post that breaks this agreement. The author sees one notice on System, and that notice cannot be replied to."),
          p("5.3 A super admin can mute an account. A muted account can still sign in and read. It cannot post, reply, like, or write a News draft."),
          p("5.4 A super admin can delete an account. Deletion ends its session and removes its posts and comments."),
          p("5.5 The makers can refuse a registration, post, or comment that clearly breaks this agreement. They may keep material that may be illegal, and provide the necessary records when a competent authority investigates under the law."),
          p("5.6 The site has no report form. The Contact page does not send mail. If you see a violation, tell a super admin."),
        ],
      },
      {
        heading: "6. Information",
        paragraphs: [
          p("6.1 To register, sign in, and show the site, it processes your email, password hash, display name, role, avatar, mute status, the time you accepted this agreement, the time the account was created, and the posts, comments, and notices tied to you."),
          p("6.2 What other people can see about an author is the id, display name, and avatar. The email stays hidden."),
          p("6.3 The makers do not sell one user’s registration details to a third party, except when you have clearly agreed, when law or a competent authority requires it, or when it is required to provide the service in this agreement."),
          p("6.4 You can correct your account by changing the password, avatar, and display name. A super admin carries out account deletion."),
        ],
      },
      {
        heading: "7. Changes",
        paragraphs: [
          p("7.1 The makers may update this agreement and publish the new text at /terms. If you keep registering or keep using an account, you accept the updated text."),
          p("7.2 If you do not accept an update, stop registering and stop using the site, and ask a super admin to delete the account. An account that already existed before this agreement, with no recorded acceptance time, can still sign in with its password."),
        ],
      },
      {
        heading: "8. Other",
        paragraphs: [
          p("8.1 Formation, interpretation, and disputes under this agreement follow the law of mainland China."),
          p("8.2 Anything this agreement does not cover follows the user-agreement page published on the site at the time. If that page and this agreement differ, the text with the later version date applies."),
        ],
      },
    ],
  },
  zh: {
    title: "用户协议",
    makers: "创始人：Tori Zhao、Jason Fang。网站由 Leo Gao、Ben Lyu、Dewey Peng、Tori Zhao 搭建。校报由 Media Club 供稿。",
    covers: "本协议覆盖 Elegram：注册、登录、阅读、论坛发帖与评论、新闻稿、账号和通知。",
    version: "版本日期：2026 年 10 月 26 日。",
    lead: [
      p("注册前请阅读本协议。"),
      p("加粗文字说明账号责任、安全义务，以及违规如何处理。", true),
      p("勾选同意并完成注册，即与上面列出的制作者成立本协议。只浏览公开页面、不注册的人，仍须遵守下面的安全义务。"),
    ],
    sections: [
      {
        heading: "1. 范围",
        paragraphs: [
          p("1.1 Tori Zhao、Jason Fang 创立本站。Leo Gao、Ben Lyu、Dewey Peng、Tori Zhao 搭建本站，供同一所学校的学生阅读校报并在论坛讨论。校报由 Media Club 供稿。"),
          p("1.2 本协议约定账号安全、使用方式，以及制作者如何处理安全问题。这不是政府备案，制作者也不通过本站向主管机关报送。"),
          p("1.3 本站没有支付、没有推荐排序、没有自动审核。论坛帖子一经发布即公开。新闻板块在超级管理员同意之前不会出现在公开页面。"),
          p("1.4 此论坛为英文论坛。请你们在 Forum 中使用英文。"),
        ],
      },
      {
        heading: "2. 账号与身份",
        paragraphs: [
          p("2.1 注册和重置密码只接受以 @basischina.com 结尾的邮箱。其他后缀不能注册，也不会收到验证码。"),
          p("2.2 注册需要有效的邮箱验证码，并接受本协议。未接受则不创建账号。"),
          p("2.3 账号只供你本人使用。", true),
          p("不要出借、出租或出售。不要用他人的邮箱或显示名注册，也不要用他人的密码登录。"),
          p("2.4 显示名不得冒充他人，也不得套用机关、学校或新闻机构的名称。头像必须是你有权使用的图片。"),
        ],
      },
      {
        heading: "3. 密码与会话",
        paragraphs: [
          p("3.1 密码由你自己设置并保管。不要告诉任何人，也不要留在共用电脑上。", true),
          p("登录后可以用当前密码修改。忘记密码时，用发到注册邮箱的验证码设置新密码。"),
          p("3.2 服务器只保存密码哈希，不保存明文。接口响应不返回密码。"),
          p("3.3 登录后浏览器保存名为 scoop_session 的会话 Cookie。该 Cookie 为 HttpOnly、SameSite=Lax，用来识别当前用户。在共用电脑上用完请退出。"),
          p("3.4 如果别人正在使用你的账号、验证码看起来不对，或密码可能已泄露，请立刻修改密码并退出其他会话。", true),
          p("因未保管好密码而导致的登录和发帖，由你负责。"),
        ],
      },
      {
        heading: "4. 你的安全义务",
        paragraphs: [
          p("使用本站时，你不得："),
          p("4.1 闯入他人账号，猜测或收集他人密码，或绕过登录和权限检查。"),
          p("4.2 上传或传播恶意文件，干扰本站，或探测、扫描、压测不对你开放的接口。"),
          p("4.3 发布或传播违法内容，包括危害国家安全、谣言、淫秽色情、赌博、暴力、恐怖极端、侮辱诽谤，以及他人的隐私。"),
          p("4.4 骚扰他人，或在发帖和评论时冒充他人。"),
          p("4.5 收集、复制或公开其他用户的邮箱，或除头像和显示名以外的注册信息，或用本站上的信息骚扰他人。"),
          p("4.6 以损害他人权利的方式使用你无权使用的论坛或新闻材料。你对自己发布的文字和图片负责。"),
        ],
      },
      {
        heading: "5. 制作者会怎么做",
        paragraphs: [
          p("5.1 制作者用站点已有的方式保护账号和内容：校内邮箱检查、验证码、密码哈希、HttpOnly 会话 Cookie，以及对发帖、草稿和用户管理的角色限制。"),
          p("5.2 管理员可以删除违反本协议的已发布帖子。作者会在通知里看到一条不可回复的消息。"),
          p("5.3 超级管理员可以禁言。被禁言的账号仍可登录和阅读，不能发帖、跟帖、点赞或写新闻草稿。"),
          p("5.4 超级管理员可以删除账号。删除后会话结束，其帖子和评论一并去掉。"),
          p("5.5 制作者可以拒绝明显违反本协议的注册、发帖或评论。他们可以保留可能违法的材料，并在主管机关依法调查时提供必要记录。"),
          p("5.6 本站没有举报表单。联系页不发信。看到违规内容，请告诉超级管理员。"),
        ],
      },
      {
        heading: "6. 信息",
        paragraphs: [
          p("6.1 为了注册、登录和展示站点，本站处理你的邮箱、密码哈希、显示名、角色、头像、禁言状态、接受本协议的时间、账号创建时间，以及与你相关的帖子、评论和通知。"),
          p("6.2 其他人能看到的作者信息是 id、显示名和头像。邮箱不公开。"),
          p("6.3 制作者不把一名用户的注册信息出售给第三方，除非你明确同意、法律或主管机关要求，或为提供本协议中的服务所必需。"),
          p("6.4 你可以修改密码、头像和显示名。删除账号由超级管理员执行。"),
        ],
      },
      {
        heading: "7. 变更",
        paragraphs: [
          p("7.1 制作者可以更新本协议，并把新文本发布在 /terms。继续注册或继续使用账号，即接受更新后的文本。"),
          p("7.2 如果不接受更新，请停止注册和停止使用本站，并请超级管理员删除账号。本协议之前已存在、没有记录同意时间的账号，仍可用原密码登录。"),
        ],
      },
      {
        heading: "8. 其他",
        paragraphs: [
          p("8.1 本协议的订立、解释和争议适用中国大陆法律。"),
          p("8.2 本协议没有写到的事项，以当时站点上公布的用户协议页为准。若该页与本协议不一致，以版本日期较新的文本为准。"),
        ],
      },
    ],
  },
};
