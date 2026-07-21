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
import { Suspense, useEffect, useState } from "react";
import Boton from "@/components/ui/Boton";
import { Campo } from "@/components/ui/Campo";
import Tarjeta from "@/components/ui/Tarjeta";
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

  // La redirección va en un efecto, no en el cuerpo del render: llamar
  // router.replace() durante el render de este componente actualiza el
  // estado del Router mientras FormularioLogin todavía se está renderizando
  // ("Cannot update a component while rendering a different component").
  useEffect(() => {
    if (user) router.replace(siguiente);
  }, [user, siguiente, router]);

  if (user) {
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
    <section style={{ maxWidth: "24rem", margin: "4rem auto" }}>
      <div style={{ textAlign: "center", marginBottom: "1.5rem" }}>
        <div style={{ fontSize: "2rem" }}>🌱</div>
        <h1>Sistema de Rotación de Pastos</h1>
        <p style={{ color: "var(--texto-tenue)" }}>Acceso para ganaderos y administradores</p>
      </div>
      <Tarjeta>
        <form onSubmit={enviar}>
          <Campo
            etiqueta="Correo"
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <Campo
            etiqueta="Contraseña"
            type="password"
            required
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          {error && (
            <p role="alert" className="campoError" style={{ color: "var(--rojo-700)", marginBottom: "1rem" }}>
              {error}
            </p>
          )}
          <Boton type="submit" cargando={enviando} style={{ width: "100%" }}>
            Entrar
          </Boton>
        </form>
      </Tarjeta>
    </section>
  );
}
