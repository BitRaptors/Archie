export type AccentColor =
  | "neon"
  | "sky-blue"
  | "amber-flame"
  | "princeton-orange"
  | "blue-green"

export const ACCENT_BORDER: Record<AccentColor, string> = {
  "neon": "border-neon",
  "sky-blue": "border-sky-blue",
  "amber-flame": "border-amber-flame",
  "princeton-orange": "border-princeton-orange",
  "blue-green": "border-blue-green",
}

export const ACCENT_TEXT: Record<AccentColor, string> = {
  "neon": "text-neon",
  "sky-blue": "text-sky-blue",
  "amber-flame": "text-amber-flame",
  "princeton-orange": "text-princeton-orange",
  "blue-green": "text-blue-green",
}

export const ACCENT_BG: Record<AccentColor, string> = {
  "neon": "bg-neon",
  "sky-blue": "bg-sky-blue",
  "amber-flame": "bg-amber-flame",
  "princeton-orange": "bg-princeton-orange",
  "blue-green": "bg-blue-green",
}

// Brutalist 8px x 8px hard offset shadow per accent.
export const ACCENT_SHADOW: Record<AccentColor, string> = {
  "neon": "shadow-[8px_8px_0px_0px_#39ff14]",
  "sky-blue": "shadow-[8px_8px_0px_0px_#8ecae6]",
  "amber-flame": "shadow-[8px_8px_0px_0px_#ffb703]",
  "princeton-orange": "shadow-[8px_8px_0px_0px_#fb8500]",
  "blue-green": "shadow-[8px_8px_0px_0px_#219ebc]",
}

// Hero variant — 12px x 12px shadow.
export const ACCENT_SHADOW_HERO: Record<AccentColor, string> = {
  "neon": "shadow-[12px_12px_0px_0px_#39ff14]",
  "sky-blue": "shadow-[12px_12px_0px_0px_#8ecae6]",
  "amber-flame": "shadow-[12px_12px_0px_0px_#ffb703]",
  "princeton-orange": "shadow-[12px_12px_0px_0px_#fb8500]",
  "blue-green": "shadow-[12px_12px_0px_0px_#219ebc]",
}
