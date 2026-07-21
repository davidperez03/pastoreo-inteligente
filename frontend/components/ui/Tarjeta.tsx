import type { ElementType, ComponentPropsWithoutRef } from "react";
import s from "./ui.module.css";

type Props<T extends ElementType> = {
  as?: T;
} & Omit<ComponentPropsWithoutRef<T>, "as">;

export default function Tarjeta<T extends ElementType = "div">({
  as,
  className,
  ...resto
}: Props<T>) {
  const Componente = as ?? "div";
  return <Componente className={`${s.tarjeta} ${className ?? ""}`} {...resto} />;
}
