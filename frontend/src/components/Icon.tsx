/**
 * One small stroke icon set (24-unit grid, 1.75 stroke, round joins) so every control speaks the same
 * visual language. Icons are decorative: the control that holds one always carries its own text or
 * aria-label, so each svg is aria-hidden.
 */
const PATHS = {
  play: <path d="M7 4.5v15l12-7.5z" fill="currentColor" stroke="none" />,
  pause: <><rect x="6" y="4.5" width="4" height="15" rx="1" fill="currentColor" stroke="none" /><rect x="14" y="4.5" width="4" height="15" rx="1" fill="currentColor" stroke="none" /></>,
  prev: <><path d="M18 5v14L8 12z" fill="currentColor" stroke="none" /><path d="M6 5v14" /></>,
  next: <><path d="M6 5v14l10-7z" fill="currentColor" stroke="none" /><path d="M18 5v14" /></>,
  search: <><circle cx="10.5" cy="10.5" r="6" /><path d="m15 15 5 5" /></>,
  close: <path d="M6 6l12 12M18 6 6 18" />,
  alert: <><path d="M12 3.5 2.5 20h19z" /><path d="M12 10v4.5M12 17.2v.1" /></>,
  info: <><circle cx="12" cy="12" r="9" /><path d="M12 11v6M12 7.6v.1" /></>,
  share: <><path d="M12 15V3.5M7.5 8 12 3.5 16.5 8" /><path d="M5 12v7.5h14V12" /></>,
  keyboard: <><rect x="2.5" y="6" width="19" height="12" rx="2" /><path d="M6.5 10h.01M10 10h.01M13.5 10h.01M17 10h.01M8 14h8" /></>,
  arrow: <path d="M4.5 12h15M13.5 6l6 6-6 6" />,
  external: <><path d="M14 4.5h5.5V10M19.5 4.5 11 13" /><path d="M17 14v5.5H4.5V7H10" /></>,
  copy: <><rect x="8.5" y="8.5" width="11" height="11" rx="1.5" /><path d="M15.5 8.5v-4h-11v11h4" /></>,
  check: <path d="m4.5 12.5 5 5 10-11" />,
  chevron: <path d="m9 6 6 6-6 6" />,
  target: <><circle cx="12" cy="12" r="7" /><path d="M12 2.5v4M12 17.5v4M2.5 12h4M17.5 12h4" /></>,
  layers: <><path d="m12 3.5 9 5-9 5-9-5z" /><path d="m3 13.5 9 5 9-5" /></>,
  back: <path d="M19.5 12h-15M10.5 6l-6 6 6 6" />,
  expand: <path d="M14 4.5h5.5V10M10 19.5H4.5V14M19.5 4.5 13.5 10.5M4.5 19.5l6-6" />,
} as const;

export type IconName = keyof typeof PATHS;

export function Icon({ name, size = 16, className }: { name: IconName; size?: number; className?: string }) {
  return (
    <svg className={`icon${className ? ` ${className}` : ""}`} width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
      {PATHS[name]}
    </svg>
  );
}
