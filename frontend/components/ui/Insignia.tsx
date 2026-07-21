import type { ReactNode } from "react";
import s from "./ui.module.css";

type Color = "verde" | "ambar" | "rojo" | "gris";

export default function Insignia({ color = "gris", children }: { color?: Color; children: ReactNode }) {
  return <span className={`${s.insignia} ${s[`insignia--${color}`]}`}>{children}</span>;
}
