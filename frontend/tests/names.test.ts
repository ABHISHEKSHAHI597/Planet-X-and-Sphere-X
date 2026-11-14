import { describe, expect, it } from "vitest";
import { displayName } from "../src/lib/names";

describe("displayName", () => {
  it("drops SIMBAD's catalogue prefixes and keeps everything else", () => {
    expect(displayName({ name: "NAME Barnard's star" })).toBe("Barnard's star");
    expect(displayName({ name: "* eps Ind B" })).toBe("eps Ind B");
    expect(displayName({ name: "V* R Dra" })).toBe("R Dra");
    expect(displayName({ name: "WISEA J085510.74-071442.5" })).toBe("WISEA J085510.74-071442.5");
    expect(displayName({ name: "269.44600 +4.77070" })).toBe("269.44600 +4.77070");
    expect(displayName({ name: "NAME Barnard's star", label_hint: "Barnard's Star (J2000 position)" })).toBe("Barnard's Star (J2000 position)");
  });
});
