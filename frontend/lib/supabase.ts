/** Cliente Supabase (singleton) para el navegador.
 *
 * Solo maneja sesión/identidad. Todo acceso a datos de negocio pasa por
 * `lib/api.ts` contra nuestro backend, nunca directo a Supabase desde
 * componentes — el backend es quien aplica la RLS multi-tenant real.
 */

import { createClient } from "@supabase/supabase-js";

const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

if (!url || !anonKey) {
  throw new Error(
    "Faltan NEXT_PUBLIC_SUPABASE_URL / NEXT_PUBLIC_SUPABASE_ANON_KEY (frontend/.env.local)",
  );
}

export const supabase = createClient(url, anonKey);
