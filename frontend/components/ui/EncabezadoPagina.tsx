import type { ReactNode } from "react";
import s from "./ui.module.css";

export default function EncabezadoPagina({
  titulo,
  descripcion,
  acciones,
}: {
  titulo: string;
  descripcion?: string;
  acciones?: ReactNode;
}) {
  return (
    <div className={s.encabezadoPagina}>
      <div className={s.encabezadoPagina__texto}>
        <h1>{titulo}</h1>
        {descripcion && <p>{descripcion}</p>}
      </div>
      {acciones && <div className={s.encabezadoPagina__acciones}>{acciones}</div>}
    </div>
  );
}
