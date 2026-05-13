import { BrowserRouter, Route, Routes } from "react-router-dom";
import { AppLayout } from "./AppLayout";
import { RequireAuth } from "./RequireAuth";
import { AdminTemplatesPage } from "./pages/AdminTemplatesPage";
import { AdminUsersPage } from "./pages/AdminUsersPage";
import { LoginPage } from "./pages/LoginPage";
import { RundownEditorPage } from "./pages/RundownEditorPage";
import { RundownListPage } from "./pages/RundownListPage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<RequireAuth />}>
          <Route element={<AppLayout />}>
            <Route path="/" element={<RundownListPage />} />
            <Route path="/rundown/:id" element={<RundownEditorPage />} />
            <Route path="/admin/templates" element={<AdminTemplatesPage />} />
            <Route path="/admin/users" element={<AdminUsersPage />} />
          </Route>
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
