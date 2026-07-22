import { useState } from "react";

export type Theme = "light" | "dark";

const STORAGE_KEY = "forkcast-theme";

// Resolves the theme the app should start in. A saved choice always wins;
// otherwise fall back to the OS preference. The inline script in index.html
// mirrors this so the class is set before first paint — keep them in sync.
export function resolveTheme(saved: string | null, prefersDark: boolean): Theme {
  if (saved === "light" || saved === "dark") return saved;
  return prefersDark ? "dark" : "light";
}

// The inline script in index.html is the source of truth for the initial
// theme; read the class it set rather than resolving again here.
function currentTheme(): Theme {
  return document.documentElement.classList.contains("dark") ? "dark" : "light";
}

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(currentTheme);

  function toggle() {
    const next: Theme = theme === "dark" ? "light" : "dark";
    document.documentElement.classList.toggle("dark", next === "dark");
    localStorage.setItem(STORAGE_KEY, next);
    setTheme(next);
  }

  return { theme, toggle };
}
