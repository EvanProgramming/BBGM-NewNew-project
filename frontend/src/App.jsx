import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./auth";
import { I18nProvider } from "./i18n";
import PaperShell from "./components/PaperShell";
import About from "./pages/About";
import AdminUsers from "./pages/AdminUsers";
import AvatarSettings from "./pages/AvatarSettings";
import ChangePassword from "./pages/ChangePassword";
import Category, { StaticCategory } from "./pages/Category";
import CjAdmin from "./pages/CjAdmin";
import CjPortal, { RequireCjRole } from "./pages/CjAccess";
import CjCourseDetail from "./pages/CjCourseDetail";
import CjDay from "./pages/CjDay";
import CjMonth from "./pages/CjMonth";
import CjTeacher from "./pages/CjTeacher";
import CjWeek from "./pages/CjWeek";
import CjYear from "./pages/CjYear";
import Contact from "./pages/Contact";
import Home from "./pages/Home";
import MyPosts from "./pages/MyPosts";
import NewsDrafts from "./pages/NewsDrafts";
import NewsDesign from "./pages/NewsDesign";
import NewsReview from "./pages/NewsReview";
import NewsSubmit from "./pages/NewsSubmit";
import PostDetail from "./pages/PostDetail";
import SystemNotices from "./pages/SystemNotices";
import Register from "./pages/Register";
import Terms from "./pages/Terms";
import ResetPassword from "./pages/ResetPassword";
import SignIn from "./pages/SignIn";

export default function App() {
  return (
    <BrowserRouter>
      <I18nProvider>
      <AuthProvider>
        <Routes>
          <Route element={<PaperShell />}>
            <Route path="/" element={<Home />} />
            <Route path="/news/drafts" element={<NewsDrafts />} />
            <Route path="/news/submit" element={<NewsSubmit />} />
            <Route path="/news/review" element={<NewsReview />} />
            <Route path="/news/review/:submissionId" element={<NewsReview />} />
            <Route path="/news" element={<Navigate to="/" replace />} />
            <Route path="/news/design" element={<NewsDesign />} />
            <Route path="/sports" element={<Navigate to="/" replace />} />
            <Route path="/forum" element={<Category category="forum" feed="recommended" title="Forum" />} />
            <Route path="/forum/latest" element={<Category category="forum" feed="latest" title="Forum" />} />
            <Route path="/forum/all" element={<Category category="forum" feed="all" title="Forum" />} />
            <Route path="/forum/mine" element={<Category category="forum" feed="mine" title="Forum" />} />
            <Route path="/cj" element={<CjPortal />} />
            <Route path="/cj/student" element={<RequireCjRole roles={["student"]}><CjWeek /></RequireCjRole>} />
            <Route path="/cj/student/calendar" element={<RequireCjRole roles={["student"]}><CjMonth /></RequireCjRole>} />
            <Route path="/cj/student/year" element={<RequireCjRole roles={["student"]}><CjYear /></RequireCjRole>} />
            <Route path="/cj/student/week" element={<RequireCjRole roles={["student"]}><CjWeek /></RequireCjRole>} />
            <Route path="/cj/student/day" element={<RequireCjRole roles={["student"]}><CjDay /></RequireCjRole>} />
            <Route path="/cj/student/course" element={<RequireCjRole roles={["student"]}><CjCourseDetail /></RequireCjRole>} />
            <Route path="/cj/day" element={<RequireCjRole roles={["student"]}><CjDay /></RequireCjRole>} />
            <Route path="/cj/week" element={<RequireCjRole roles={["student"]}><CjWeek /></RequireCjRole>} />
            <Route path="/cj/teacher" element={<RequireCjRole roles={["teacher"]}><CjTeacher /></RequireCjRole>} />
            <Route path="/cj/admin" element={<RequireCjRole roles={["super_admin"]}><CjAdmin /></RequireCjRole>} />
            <Route path="/cj/admin/student-preview" element={<RequireCjRole roles={["super_admin"]}><CjDay portal="admin" calendarPath="/cj/admin" weekPath="/cj/admin" detailPath="/cj/admin/student-preview/course" /></RequireCjRole>} />
            <Route path="/cj/admin/student-preview/course" element={<RequireCjRole roles={["super_admin"]}><CjCourseDetail portal="admin" backPath="/cj/admin/student-preview" /></RequireCjRole>} />
            <Route path="/opinion" element={<StaticCategory title="Opinion" />} />
            <Route path="/community" element={<Navigate to="/forum" replace />} />
            <Route path="/submit" element={<Navigate to="/forum" replace />} />
            <Route path="/dorm-life" element={<Navigate to="/" replace />} />
            <Route path="/events" element={<Navigate to="/" replace />} />
            <Route path="/photo" element={<Navigate to="/" replace />} />
            <Route path="/posts/:postId" element={<PostDetail />} />
            <Route path="/me/posts" element={<MyPosts />} />
            <Route path="/me/avatar" element={<AvatarSettings />} />
            <Route path="/me/password" element={<ChangePassword />} />
            <Route path="/admin/users" element={<AdminUsers />} />
            <Route path="/paper" element={<Navigate to="/" replace />} />
            <Route path="/system" element={<SystemNotices />} />
            <Route path="/sign-in" element={<SignIn />} />
            <Route path="/register" element={<Register />} />
            <Route path="/reset-password" element={<ResetPassword />} />
            <Route path="/about" element={<About />} />
            <Route path="/terms" element={<Terms />} />
            <Route path="/contact" element={<Contact />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </AuthProvider>
      </I18nProvider>
    </BrowserRouter>
  );
}
