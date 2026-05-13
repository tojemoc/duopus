export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function mergeHeaders(base: Record<string, string>, extra?: HeadersInit): Headers {
  const h = new Headers();
  for (const [k, v] of Object.entries(base)) {
    h.set(k, v);
  }
  if (extra === undefined || extra === null) return h;
  if (extra instanceof Headers) {
    extra.forEach((v, k) => {
      h.set(k, v);
    });
    return h;
  }
  if (Array.isArray(extra)) {
    for (const [k, v] of extra) {
      h.set(k, v);
    }
    return h;
  }
  for (const [k, v] of Object.entries(extra)) {
    if (v !== undefined) h.set(k, String(v));
  }
  return h;
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const defaultHeaders: Record<string, string> = {};
  const headers = mergeHeaders(defaultHeaders, init?.headers);
  const res = await fetch(path, {
    credentials: "include",
    ...init,
    headers,
  });
  if (!res.ok) {
    let msg = "Something went wrong.";
    try {
      const data = await res.json();
      msg = (data?.detail as string) || (data?.message as string) || msg;
    } catch {
      // ignore
    }
    throw new ApiError(msg, res.status);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export function formBody(fields: Record<string, string>) {
  const body = new URLSearchParams();
  for (const [k, v] of Object.entries(fields)) body.set(k, v);
  return body.toString();
}
