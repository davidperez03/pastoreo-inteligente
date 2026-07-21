import type { ButtonHTMLAttributes } from "react";
import s from "./ui.module.css";

type Variante = "primario" | "secundario" | "peligro" | "fantasma";

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variante?: Variante;
  cargando?: boolean;
}

export default function Boton({
  variante = "primario",
  cargando = false,
  disabled,
  children,
  ...resto
}: Props) {
  return (
    <button
      className={`${s.boton} ${s[`boton--${variante}`]}`}
      disabled={disabled || cargando}
      {...resto}
    >
      {cargando && <span className={s.spinner} aria-hidden />}
      {children}
    </button>
  );
}
