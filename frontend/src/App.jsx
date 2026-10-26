import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./auth";
import { I18nProvider } from "./i18n";
import PaperShell from "./components/PaperShell";
import About from "./pages/About";
import Bell from "./pages/Bell";
import BottleThread from "./pages/BottleThread";
import Bottles from "./pages/Bottles";
import AdminUsers from "./pages/AdminUsers";
import AvatarSettings from "./pages/AvatarSettings";
import ChangePassword from "./pages/ChangePassword";
import Category, { StaticCategory } from "./pages/Category";
import CjAdmin from "./pages/CjAdmin";
import CjPortal, { CJ_PAUSED, CjPaused, RequireCjRole } from "./pages/CjAccess";
import CjCourseDetail from "./pages/CjCourseDetail";
import CjDay from "./pages/CjDay";
import CjMonth from "./pages/CjMonth";
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
import Play from "./pages/Play";
import SystemNotices from "./pages/SystemNotices";
import Register from "./pages/Register";
import Terms from "./pages/Terms";
import ResetPassword from "./pages/ResetPassword";
import SignIn from "./pages/SignIn";

const CJ_READ = ["student", "teacher"];

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
            <Route path="/play" element={<Play />} />
            <Route path="/bell" element={<Bell />} />
            <Route path="/bottles" element={<Bottles />} />
            <Route path="/bottles/picks/:pickId" element={<BottleThread />} />
            <Route path="/cj" element={CJ_PAUSED ? <CjPaused /> : <CjPortal />} />
            <Route path="/cj/student" element={CJ_PAUSED ? <CjPaused /> : <RequireCjRole roles={CJ_READ}><CjWeek /></RequireCjRole>} />
            <Route path="/cj/student/calendar" element={CJ_PAUSED ? <CjPaused /> : <RequireCjRole roles={CJ_READ}><CjMonth /></RequireCjRole>} />
            <Route path="/cj/student/year" element={CJ_PAUSED ? <CjPaused /> : <RequireCjRole roles={CJ_READ}><CjYear /></RequireCjRole>} />
            <Route path="/cj/student/week" element={CJ_PAUSED ? <CjPaused /> : <RequireCjRole roles={CJ_READ}><CjWeek /></RequireCjRole>} />
            <Route path="/cj/student/day" element={CJ_PAUSED ? <CjPaused /> : <RequireCjRole roles={CJ_READ}><CjDay /></RequireCjRole>} />
            <Route path="/cj/student/course" element={CJ_PAUSED ? <CjPaused /> : <RequireCjRole roles={CJ_READ}><CjCourseDetail /></RequireCjRole>} />
            <Route path="/cj/day" element={CJ_PAUSED ? <CjPaused /> : <RequireCjRole roles={CJ_READ}><CjDay /></RequireCjRole>} />
            <Route path="/cj/week" element={CJ_PAUSED ? <CjPaused /> : <RequireCjRole roles={CJ_READ}><CjWeek /></RequireCjRole>} />
            <Route path="/cj/teacher" element={<Navigate to="/cj" replace />} />
            <Route path="/cj/admin" element={CJ_PAUSED ? <CjPaused /> : <RequireCjRole roles={["super_admin"]}><CjAdmin /></RequireCjRole>} />
            <Route path="/cj/admin/student-preview" element={CJ_PAUSED ? <CjPaused /> : <RequireCjRole roles={["super_admin"]}><CjDay portal="admin" calendarPath="/cj/admin" weekPath="/cj/admin" detailPath="/cj/admin/student-preview/course" /></RequireCjRole>} />
            <Route path="/cj/admin/student-preview/course" element={CJ_PAUSED ? <CjPaused /> : <RequireCjRole roles={["super_admin"]}><CjCourseDetail portal="admin" backPath="/cj/admin/student-preview" /></RequireCjRole>} />
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
