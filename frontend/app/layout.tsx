import type { Metadata } from "next";
import EstadoSesion from "@/components/auth/EstadoSesion";
import { AuthProvider } from "@/lib/auth";
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
          <nav className="nav" style={{ justifyContent: "space-between", display: "flex" }}>
            <span style={{ display: "flex", gap: "1.5rem" }}>
              <a href="/">SRP</a>
              <a href="/mapa">Mapa</a>
              <a href="/dashboard">Dashboard</a>
            </span>
            <EstadoSesion />
          </nav>
          <main>{children}</main>
        </AuthProvider>
      </body>
    </html>
  );
}
