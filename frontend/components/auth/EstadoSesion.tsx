"use client";

import { useRouter } from "next/navigation";
import Boton from "@/components/ui/Boton";
import { useAuth } from "@/lib/auth";

/** Muestra el correo del usuario + botón de salir, o un link a /login. */
export default function EstadoSesion() {
  const { user, cargando, signOut } = useAuth();
  const router = useRouter();

  if (cargando) return null;

  if (!user) {
    return <a href="/login">Iniciar sesión</a>;
  }

  return (
    <span style={{ display: "inline-flex", gap: "0.75rem", alignItems: "center" }}>
      <span style={{ fontSize: "0.85rem", color: "var(--texto-tenue)" }}>{user.email}</span>
      <Boton
        variante="fantasma"
        onClick={async () => {
          await signOut();
          router.replace("/login");
        }}
      >
        Cerrar sesión
      </Boton>
    </span>
  );
}
