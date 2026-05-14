import { useEffect, useMemo, useState } from "react";
import { api } from "../api";

type UserRow = {
  id: number;
  email: string;
  display_name: string;
  role: "editor" | "admin";
  is_active: boolean;
};

type Role = UserRow["role"];

function isRole(value: string): value is Role {
  return value === "editor" || value === "admin";
}

function usernameFromEmail(email: string) {
  const i = email.indexOf("@");
  return i >= 0 ? email.slice(0, i) : email;
}

function emailFromUsername(username: string) {
  const u = username.trim();
  if (u.includes("@")) return u;
  return `${u}@example.com`;
}

export function AdminUsersPage() {
  const [rows, setRows] = useState<UserRow[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [newUsername, setNewUsername] = useState("");
  const [newDisplay, setNewDisplay] = useState("");
  const [newRole, setNewRole] = useState<"editor" | "admin">("editor");
  const [newPassword, setNewPassword] = useState("");

  const load = async () => {
    setErr(null);
    const data = await api<UserRow[]>("/api/users");
    setRows(data);
  };

  useEffect(() => {
    load().catch((e: any) => setErr(e?.message || "Failed to load users."));
  }, []);

  const create = async () => {
    setBusy(true);
    setErr(null);
    try {
      await api("/api/users", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: emailFromUsername(newUsername),
          password: newPassword,
          display_name: newDisplay || newUsername,
          role: newRole,
        }),
      });
      setNewUsername("");
      setNewDisplay("");
      setNewPassword("");
      setNewRole("editor");
      await load();
    } catch (e: any) {
      setErr(e?.message || "Failed to create user.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <div className="text-lg font-semibold">Users</div>
        <div className="text-sm text-slate-600 mt-1">Admin creates users. No self-registration.</div>
      </div>

      {err && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">
          {err}
        </div>
      )}

      <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-3">
        <div className="font-medium">Create user</div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <div>
            <label htmlFor="newUsername" className="block text-xs font-medium text-slate-700">
              Username
            </label>
            <input
              id="newUsername"
              className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
              value={newUsername}
              onChange={(e) => setNewUsername(e.target.value)}
              placeholder="e.g. martin"
            />
          </div>
          <div>
            <label htmlFor="newDisplay" className="block text-xs font-medium text-slate-700">
              Display name
            </label>
            <input
              id="newDisplay"
              className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
              value={newDisplay}
              onChange={(e) => setNewDisplay(e.target.value)}
              placeholder="e.g. Martin Novak"
            />
          </div>
          <div>
            <label htmlFor="newRole" className="block text-xs font-medium text-slate-700">
              Role
            </label>
            <select
              id="newRole"
              className="mt-1 w-full rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm"
              value={newRole}
              onChange={(e) => {
                const v = e.target.value;
                if (isRole(v)) setNewRole(v);
              }}
            >
              <option value="editor">editor</option>
              <option value="admin">admin</option>
            </select>
          </div>
          <div>
            <label htmlFor="newPassword" className="block text-xs font-medium text-slate-700">
              Password
            </label>
            <input
              id="newPassword"
              className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              type="password"
            />
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            className="rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            type="button"
            onClick={create}
            disabled={busy || !newUsername.trim() || !newPassword}
          >
            Create
          </button>
          <div className="text-xs text-slate-500">Usernames are stored as emails internally.</div>
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="px-3 py-2 text-left w-16">ID</th>
              <th className="px-3 py-2 text-left">Username</th>
              <th className="px-3 py-2 text-left">Display name</th>
              <th className="px-3 py-2 text-left w-28">Role</th>
              <th className="px-3 py-2 text-left w-24"></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((u) => (
              <UserRowItem key={u.id} user={u} onChange={load} />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function UserRowItem({ user, onChange }: { user: UserRow; onChange: () => Promise<void> }) {
  const [display, setDisplay] = useState(user.display_name);
  const [role, setRole] = useState<UserRow["role"]>(user.role);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    setDisplay(user.display_name);
    setRole(user.role);
    setErr(null);
  }, [user.id, user.display_name, user.role]);

  const dirty = useMemo(() => display !== user.display_name || role !== user.role, [display, role, user]);

  const save = async () => {
    setBusy(true);
    setErr(null);
    try {
      await api(`/api/users/${user.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ display_name: display, role }),
      });
      await onChange();
    } catch (e: any) {
      setErr(e?.message || "Failed to save.");
    } finally {
      setBusy(false);
    }
  };

  const del = async () => {
    if (!confirm(`Delete user ${user.display_name}?`)) return;
    setBusy(true);
    setErr(null);
    try {
      await api(`/api/users/${user.id}`, { method: "DELETE" });
      await onChange();
    } catch (e: any) {
      setErr(e?.message || "Failed to delete.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <tr className="border-t border-slate-100">
      <td className="px-3 py-2 text-slate-600">{user.id}</td>
      <td className="px-3 py-2 font-mono text-slate-800">{usernameFromEmail(user.email)}</td>
      <td className="px-3 py-2">
        <label htmlFor={`user-${user.id}-display`} className="sr-only">
          Display name
        </label>
        <input
          id={`user-${user.id}-display`}
          className="w-full rounded-md border border-slate-300 px-2 py-1 text-sm"
          value={display}
          onChange={(e) => setDisplay(e.target.value)}
        />
        {err && <div className="mt-1 text-xs text-rose-700">{err}</div>}
      </td>
      <td className="px-3 py-2">
        <label htmlFor={`user-${user.id}-role`} className="sr-only">
          Role
        </label>
        <select
          id={`user-${user.id}-role`}
          className="w-full rounded-md border border-slate-300 bg-white px-2 py-1 text-sm"
          value={role}
          onChange={(e) => {
            const v = e.target.value;
            if (isRole(v)) setRole(v);
          }}
        >
          <option value="editor">editor</option>
          <option value="admin">admin</option>
        </select>
      </td>
      <td className="px-3 py-2">
        <div className="flex justify-end gap-2">
          <button
            type="button"
            className="rounded-md border border-slate-300 bg-white px-2 py-1 text-xs hover:bg-slate-50 disabled:opacity-50"
            onClick={del}
            disabled={busy}
          >
            Delete
          </button>
          <button
            type="button"
            className="rounded-md bg-blue-600 px-2 py-1 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            onClick={save}
            disabled={busy || !dirty}
          >
            Save
          </button>
        </div>
      </td>
    </tr>
  );
}

