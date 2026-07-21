import type { ReactNode } from "react";
import s from "./ui.module.css";

export default function EstadoVacio({
  titulo,
  descripcion,
  accion,
}: {
  titulo: string;
  descripcion?: string;
  accion?: ReactNode;
}) {
  return (
    <div className={s.estadoVacio}>
      <h3>{titulo}</h3>
      {descripcion && <p>{descripcion}</p>}
      {accion}
    </div>
  );
}
