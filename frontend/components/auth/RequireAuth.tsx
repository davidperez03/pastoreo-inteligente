"use client";

/** Envuelve una página que requiere sesión: mientras se resuelve el estado
 * inicial de auth no redirige (evita un parpadeo hacia /login en cada
 * recarga), y una vez resuelto, sin usuario, manda a /login conservando la
 * ruta de origen para volver tras iniciar sesión. */

import { useRouter, usePathname } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/lib/auth";

export default function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, cargando } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!cargando && !user) {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    }
  }, [cargando, user, pathname, router]);

  if (cargando || !user) {
    return <p>Verificando sesión…</p>;
  }
  return <>{children}</>;
}
