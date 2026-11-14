// Minimal typing for the parts of Aladin Lite v3 (npm "aladin-lite", pinned) that SkyContext uses.
declare module "aladin-lite" {
  export interface AladinInstance {
    gotoRaDec(ra: number, dec: number): void;
    setFoV(deg: number): void;
    setImageSurvey(id: string): void;
    addOverlay(o: unknown): void;
    addCatalog(c: unknown): void;
    removeLayers?(): void;
  }
  export interface Overlay { add(x: unknown): void; removeAll(): void }
  export interface Catalog { addSources(x: unknown[]): void; removeAll(): void }
  const A: {
    init: Promise<void>;
    aladin(el: HTMLElement | string, opts: Record<string, unknown>): AladinInstance;
    graphicOverlay(opts: Record<string, unknown>): Overlay;
    polygon(pts: [number, number][], opts?: Record<string, unknown>): unknown;
    catalog(opts: Record<string, unknown>): Catalog;
    source(ra: number, dec: number, data?: Record<string, unknown>): unknown;
  };
  export default A;
}
