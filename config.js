/* Configurarea conturilor (Supabase). Lasă câmpurile goale ca aplicația să lucreze local (proiectele în acest browser).
 *
 * Unde găsești valorile: Supabase → proiectul tău → Project Settings → API (sau „Connect”):
 *   SUPABASE_URL      = „Project URL”, de forma https://abcdefghijklmnop.supabase.co
 *   SUPABASE_ANON_KEY = cheia „anon” / „public” (publishable). E publică prin design: datele sunt protejate de RLS.
 *
 * NU pune aici niciodată cheia „service_role” (secret) — ea ocolește RLS și ar da acces la toate conturile.
 * Înainte de prima folosire rulează o dată supabase/schema.sql în Supabase → SQL Editor.
 */
window.SM_CONFIG = {
  SUPABASE_URL: '',
  SUPABASE_ANON_KEY: '',
  // Varianta gratuită: exporturile (SVG / PDF / DXF / pachet) primesc filigranul discret „kromotec · versiune gratuită”
  // (în DXF pe un layer separat). false = fără filigran (varianta plătită).
  FILIGRAN: true,
};
