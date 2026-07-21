import type { Metadata } from "next";
import EstadoSesion from "@/components/auth/EstadoSesion";
import SelectorFinca from "@/components/fincas/SelectorFinca";
import { AuthProvider } from "@/lib/auth";
import { FincaActualProvider } from "@/lib/finca-actual";
import "./globals.css";

export const metadata: Metadata = {
  title: "SRP — Rotación de Pastos",
  description: "Gestión de rotación de ganado con planimetría y biomasa",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body>
        <AuthProvider>
          <FincaActualProvider>
            <nav className="appNav">
              <div style={{ display: "flex", alignItems: "center", gap: "2rem" }}>
                <a href="/" className="appNav__marca">
                  🌱 SRP
                </a>
                <span className="appNav__links">
                  <a href="/fincas">Fincas</a>
                  <a href="/mapa">Potreros</a>
                  <a href="/ganado">Ganado</a>
                  <a href="/dashboard">Dashboard</a>
                </span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
                <SelectorFinca />
                <EstadoSesion />
              </div>
            </nav>
            <main>{children}</main>
          </FincaActualProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
