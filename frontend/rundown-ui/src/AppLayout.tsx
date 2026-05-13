import { Link, Outlet, useNavigate } from "react-router-dom";
import { api } from "./api";
import { useAuth } from "./useAuth";

export function AppLayout() {
  const { me, refresh } = useAuth();
  const nav = useNavigate();

  const logout = async () => {
    await api<void>("/api/auth/logout", { method: "POST" });
    await refresh();
    nav("/login", { replace: true });
  };

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/90 backdrop-blur">
        <div className="mx-auto max-w-6xl px-4 py-3 flex items-center gap-3">
          <Link to="/" className="font-semibold text-slate-900">
            Duopus
          </Link>
          <div className="text-sm text-slate-500">Phase 1</div>
          <nav className="ml-6 flex items-center gap-2 text-sm">
            {me?.role === "admin" && (
              <>
                <Link className="rounded-md px-2 py-1 hover:bg-slate-100" to="/admin/templates">
                  Templates
                </Link>
                <Link className="rounded-md px-2 py-1 hover:bg-slate-100" to="/admin/users">
                  Users
                </Link>
              </>
            )}
          </nav>
          <div className="ml-auto flex items-center gap-3">
            {me && <div className="text-sm text-slate-700">{me.display_name}</div>}
            <button
              className="rounded-md border border-slate-300 bg-white px-2 py-1 text-sm hover:bg-slate-50"
              type="button"
              onClick={logout}
            >
              Logout
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-4">
        <Outlet />
      </main>
    </div>
  );
}

