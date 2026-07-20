import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SRP — Rotación de Pastos",
  description: "Gestión de rotación de ganado con planimetría y biomasa",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body>
        <nav className="nav">
          <a href="/">SRP</a>
          <a href="/mapa">Mapa</a>
          <a href="/dashboard">Dashboard</a>
        </nav>
        <main>{children}</main>
      </body>
    </html>
  );
}
