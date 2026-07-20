export default function Home() {
  return (
    <section>
      <h1>Sistema de Rotación de Pastos</h1>
      <p>
        Gestión de potreros con planimetría georreferenciada, biomasa estimada
        (modelo agronómico + NDVI) y sugerencia de rotación.
      </p>
      <ul>
        <li>
          <a href="/mapa">Mapa de potreros</a> — dibujar, editar e importar planimetrías
        </li>
        <li>
          <a href="/dashboard">Dashboard</a> — estado por potrero y sugerencias de rotación
        </li>
      </ul>
    </section>
  );
}
