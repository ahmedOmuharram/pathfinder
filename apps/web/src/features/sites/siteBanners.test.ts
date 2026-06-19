import { describe, expect, it } from "vitest";

import { getSiteBanner } from "./siteBanners";

describe("getSiteBanner", () => {
  it("returns the site-specific banner path for a known site", () => {
    expect(getSiteBanner("plasmodb")).toEqual({
      imagePath: "/banners/plasmodb.jpg",
    });
    expect(getSiteBanner("tritrypdb")).toEqual({
      imagePath: "/banners/tritrypdb.jpg",
    });
  });

  it("is case-insensitive on the site id", () => {
    expect(getSiteBanner("ToxoDB")).toEqual({ imagePath: "/banners/toxodb.jpg" });
  });

  it("falls back to the VEuPathDB portal banner for an unknown site", () => {
    expect(getSiteBanner("notasite")).toEqual({
      imagePath: "/banners/veupathdb.jpg",
    });
  });
});
