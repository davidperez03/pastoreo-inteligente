/** Wrapper de acceso a la API del backend.
 *
 * Todos los componentes deben pasar por aquí (nunca fetch directo): centraliza
 * base URL, auth y manejo de errores. El token sale de la sesión de Supabase
 * (persistida y refrescada por supabase-js) — `supabase.auth.getSession()`
 * resuelve del caché en memoria/localStorage sin llamada de red salvo que
 * el token esté vencido y necesite refrescarse.
 */

import { supabase } from "./supabase";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const {
    data: { session },
  } = await supabase.auth.getSession();
  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(session ? { Authorization: `Bearer ${session.access_token}` } : {}),
      ...init?.headers,
    },
  });
  if (!res.ok) {
    throw new ApiError(res.status, await res.text());
  }
  return res.json() as Promise<T>;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "POST", body: JSON.stringify(body) }),
};
