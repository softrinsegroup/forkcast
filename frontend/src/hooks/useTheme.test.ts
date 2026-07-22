import { describe, expect, it } from "vitest";
import { resolveTheme } from "./useTheme";

// Why: a saved choice must beat the OS preference, and the OS preference is
// only the fallback when the user has never chosen. This precedence is the
// rule most likely to regress, and it drives both the inline FOUC script and
// the hook's initial state.
describe("resolveTheme", () => {
  it("prefers a saved choice over the OS preference", () => {
    expect(resolveTheme("light", true)).toBe("light");
    expect(resolveTheme("dark", false)).toBe("dark");
  });

  it("falls back to the OS preference when nothing is saved", () => {
    expect(resolveTheme(null, true)).toBe("dark");
    expect(resolveTheme(null, false)).toBe("light");
  });

  it("ignores an unrecognized saved value and uses the OS preference", () => {
    expect(resolveTheme("system", true)).toBe("dark");
  });
});
