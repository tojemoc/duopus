import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "./useAuth";

export function RequireAuth() {
  const { me, loading } = useAuth();
  if (loading) return <div className="text-sm text-slate-600">Loading…</div>;
  if (!me) return <Navigate to="/login" replace />;
  return <Outlet />;
}

