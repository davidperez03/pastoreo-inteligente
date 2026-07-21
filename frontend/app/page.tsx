import Tarjeta from "@/components/ui/Tarjeta";

const SECCIONES = [
  {
    href: "/fincas",
    icono: "🏡",
    titulo: "Fincas",
    descripcion: "Crea y elige la finca sobre la que trabajas.",
  },
  {
    href: "/mapa",
    icono: "🗺️",
    titulo: "Potreros",
    descripcion: "Dibuja, edita e importa la planimetría de tus potreros.",
  },
  {
    href: "/ganado",
    icono: "🐄",
    titulo: "Ganado",
    descripcion: "Lotes y registro de entrada/salida entre potreros.",
  },
  {
    href: "/dashboard",
    icono: "📊",
    titulo: "Dashboard",
    descripcion: "Estado por potrero, biomasa y sugerencias de rotación.",
  },
];

export default function Home() {
  return (
    <section>
      <div style={{ maxWidth: "40rem", marginBottom: "2.5rem" }}>
        <h1>Sistema de Rotación de Pastos</h1>
        <p>
          Gestión de potreros con planimetría georreferenciada, biomasa estimada
          por modelo agronómico + NDVI satelital, y sugerencia de rotación de
          ganado sin sobrepastorear.
        </p>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(15rem, 1fr))",
          gap: "1rem",
        }}
      >
        {SECCIONES.map((s) => (
          <a key={s.href} href={s.href} style={{ textDecoration: "none", color: "inherit" }}>
            <Tarjeta style={{ height: "100%" }}>
              <div style={{ fontSize: "1.6rem", marginBottom: "0.5rem" }}>{s.icono}</div>
              <h2 style={{ marginBottom: "0.35rem" }}>{s.titulo}</h2>
              <p style={{ margin: 0, fontSize: "0.9rem" }}>{s.descripcion}</p>
            </Tarjeta>
          </a>
        ))}
      </div>
    </section>
  );
}
