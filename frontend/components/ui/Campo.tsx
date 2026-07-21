import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from "react";
import s from "./ui.module.css";

interface Props extends InputHTMLAttributes<HTMLInputElement> {
  etiqueta: string;
  ayuda?: string;
  error?: string;
}

export function Campo({ etiqueta, ayuda, error, id, ...resto }: Props) {
  const inputId = id ?? etiqueta.toLowerCase().replace(/\s+/g, "-");
  return (
    <div className={s.campo}>
      <label htmlFor={inputId}>{etiqueta}</label>
      <input id={inputId} {...resto} />
      {error ? (
        <p className={s.campoError}>{error}</p>
      ) : ayuda ? (
        <p className={s.campoAyuda}>{ayuda}</p>
      ) : null}
    </div>
  );
}

interface PropsSelect extends SelectHTMLAttributes<HTMLSelectElement> {
  etiqueta: string;
  ayuda?: string;
  children: ReactNode;
}

export function CampoSelect({ etiqueta, ayuda, id, children, ...resto }: PropsSelect) {
  const inputId = id ?? etiqueta.toLowerCase().replace(/\s+/g, "-");
  return (
    <div className={s.campo}>
      <label htmlFor={inputId}>{etiqueta}</label>
      <select id={inputId} {...resto}>
        {children}
      </select>
      {ayuda && <p className={s.campoAyuda}>{ayuda}</p>}
    </div>
  );
}
