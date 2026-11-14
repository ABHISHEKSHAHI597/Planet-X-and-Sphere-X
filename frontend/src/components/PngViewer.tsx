/**
 * PNG fallback viewer (P0-8, implementation.md §6.4): server-rendered frames with the SHARED limits,
 * blinked as plain <img> elements. Works with WebGL disabled and on any device. All frames of the
 * band are preloaded so blinking is instant. PNGs are top-row-north (standard image orientation).
 */
import { useEffect, useState } from "react";
import { api, getTransport } from "../api/client";

const cache = new Map<string, Promise<string>>();

function srcFor(url: string): Promise<string> {
  let p = cache.get(url);
  if (!p) {
    p = getTransport().kind !== "http" || url.startsWith("mock:")
      ? api.pngBlob(url).then((b) => URL.createObjectURL(b))
      : new Promise<string>((resolve, reject) => {     // preload through the browser cache
        const im = new Image();
        im.onload = () => resolve(url);
        im.onerror = () => reject(new Error(`PNG failed: ${url}`));
        im.src = url;
      });
    p.catch(() => cache.delete(url));
    cache.set(url, p);
  }
  return p;
}

export function usePngSrc(url: string | null): string | null {
  const [src, setSrc] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    if (!url) { setSrc(null); return; }
    srcFor(url).then((s) => { if (live) setSrc(s); }, () => { if (live) setSrc(null); });
    return () => { live = false; };
  }, [url]);
  return src;
}

export function preloadPngs(urls: string[]): void {
  for (const u of urls) void srcFor(u).catch(() => undefined);
}

export function PngViewer({ url, label, onClickPixel, nx, ny }: {
  url: string | null; label: string; nx: number; ny: number;
  onClickPixel?: (p: { col: number; row: number }) => void;
}) {
  const src = usePngSrc(url);
  return (
    <div className="png-viewer">
      {src ? (
        <img
          src={src}
          alt={label}
          draggable={false}
          onClick={(e) => {
            if (!onClickPixel) return;
            const b = (e.target as HTMLImageElement).getBoundingClientRect();
            const col = Math.floor(((e.clientX - b.left) / b.width) * nx);
            const row = ny - 1 - Math.floor(((e.clientY - b.top) / b.height) * ny);   // PNG top row = north
            if (col >= 0 && col < nx && row >= 0 && row < ny) onClickPixel({ col, row });
          }}
        />
      ) : <div className="png-loading" role="status">Loading frame…</div>}
    </div>
  );
}
