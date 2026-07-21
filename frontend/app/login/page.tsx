"use client";

/** Login con email/password contra Supabase Auth (§10 de la spec).
 *
 * No hay signup self-service a propósito: un usuario recién autenticado sin
 * fila en la tabla `usuarios` no pertenece a ninguna organización, y el
 * backend lo rechaza con 403 (ver srp/shared/auth.py). Vincular usuarios a
 * una organización es, por ahora, una acción de administrador
 * (scripts/crear_usuario_supabase.py) — coherente con la etapa de piloto,
 * donde no hay alta pública de cuentas.
 */

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { useAuth } from "@/lib/auth";
import { supabase } from "@/lib/supabase";

export default function PaginaLogin() {
  return (
    <Suspense fallback={<p>Cargando…</p>}>
      <FormularioLogin />
    </Suspense>
  );
}

function FormularioLogin() {
  const { user } = useAuth();
  const router = useRouter();
  const params = useSearchParams();
  const siguiente = params.get("next") ?? "/dashboard";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (user) {
    router.replace(siguiente);
    return null;
  }

  async function enviar(e: React.FormEvent) {
    e.preventDefault();
    setEnviando(true);
    setError(null);
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    setEnviando(false);
    if (error) {
      setError(
        error.message === "Invalid login credentials"
          ? "Correo o contraseña incorrectos."
          : error.message,
      );
      return;
    }
    router.replace(siguiente);
  }

  return (
    <section style={{ maxWidth: "24rem", margin: "3rem auto" }}>
      <h1>Iniciar sesión</h1>
      <p>Sistema de Rotación de Pastos — acceso para ganaderos y administradores.</p>
      <form onSubmit={enviar} style={{ display: "grid", gap: "0.75rem", marginTop: "1.5rem" }}>
        <label>
          Correo
          <input
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            style={{ display: "block", width: "100%" }}
          />
        </label>
        <label>
          Contraseña
          <input
            type="password"
            required
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            style={{ display: "block", width: "100%" }}
          />
        </label>
        {error && (
          <p role="alert" style={{ color: "#b91c1c" }}>
            {error}
          </p>
        )}
        <button type="submit" disabled={enviando}>
          {enviando ? "Entrando…" : "Entrar"}
        </button>
      </form>
    </section>
  );
}
