import { useCallback, useEffect, useState } from "react";
import { ApiError, api } from "./api";

export type Me = {
  id: number;
  email: string;
  display_name: string;
  role: "editor" | "admin";
};

export function useAuth() {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const u = await api<Me>("/api/auth/me");
      setMe(u);
    } catch (e) {
      if (e instanceof ApiError && (e.status === 401 || e.status === 403)) {
        setMe(null);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { me, loading, refresh };
}

