/**
 * Where the app is mounted. "/" on our own host; "/<repository>/" on GitHub Pages (vite `base`, set with
 * VITE_BASE at build time). Every in-app link and the route test go through here, so the same build works at
 * the root of a domain and under a sub-path (ParallaX Lite, optimisation.md item 0.3).
 */
export const BASE: string = import.meta.env.BASE_URL || "/";

/** An in-app link: `href()` is the home page, `href("about")` the credits page. */
export function href(path = ""): string {
  return BASE + path.replace(/^\/+/, "");
}

/** The route with the mount point removed: "/", "/embed", "/about" or "/f14". */
export function routePath(pathname: string = location.pathname, base: string = BASE): string {
  const rest = pathname.startsWith(base) ? `/${pathname.slice(base.length)}` : pathname;
  return rest.replace(/\/+$/, "") || "/";
}
