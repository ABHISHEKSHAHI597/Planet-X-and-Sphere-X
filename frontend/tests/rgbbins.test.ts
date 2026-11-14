import { describe, expect, it } from "vitest";
import { channelBins } from "../src/lib/rgbBins";

describe("RGB channel bins", () => {
  const bins = {
    "4": [{ id: "B3", mjd_mean: 100 }, { id: "B5", mjd_mean: 128 }],
    "5": [{ id: "B4", mjd_mean: 110 }],
    "6": [{ id: "B0", mjd_mean: 60 }, { id: "B3", mjd_mean: 101 }],
  };
  it("uses the same bin where it exists, else the nearest within 14 days", () => {
    expect(channelBins(bins, "B3", [4, 5, 6])).toEqual(["B3", "B4", "B3"]);
  });
  it("gives null when no band stack is close enough", () => {
    expect(channelBins(bins, "B5", [4, 5, 6])).toEqual(["B5", null, null]);
  });
});
