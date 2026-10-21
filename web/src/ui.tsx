import { useId } from "react";

const PATHS = {
  chat: <path d="M20.5 11.5a8.5 8.5 0 0 1-12.4 7.6L3.5 20.5l1.4-4.4A8.5 8.5 0 1 1 20.5 11.5z" />,
  search: <><circle cx="11" cy="11" r="6.5" /><path d="m20 20-4.2-4.2" /></>,
  notebook: <><rect x="5" y="3" width="14" height="18" rx="2.5" /><path d="M9 3v18M12.5 8h3M12.5 11.5h3" /></>,
  bulb: <path d="M9.5 18h5M10.5 21h3M12 3a6 6 0 0 0-3.6 10.8c.7.5 1.1 1.3 1.1 2.1v.1h5v-.1c0-.8.4-1.6 1.1-2.1A6 6 0 0 0 12 3z" />,
  tasks: <><rect x="4" y="4" width="16" height="16" rx="3.5" /><path d="m8.5 12 2.5 2.5 4.5-5" /></>,
  shapes: <><circle cx="7.5" cy="7.5" r="3.5" /><path d="m16.5 3.8 3.6 6.2h-7.2z" /><rect x="4" y="13.5" width="7" height="7" rx="1.8" /><rect x="13" y="13.5" width="7" height="7" rx="3.5" /></>,
  download: <path d="M12 4v10.5m-4.5-4.5 4.5 4.5 4.5-4.5M5 15.5V18a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-2.5" />,
  menu: <path d="M4.5 9h15M4.5 15h15" />,
  plus: <path d="M12 5v14M5 12h14" />,
  mic: <><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21" /></>,
  up: <path d="M12 19V5.5m-6 6 6-6 6 6" />,
  down: <path d="M12 5v13.5m-6-6 6 6 6-6" />,
  share: <path d="M12 14.5V3.5m-4 4 4-4 4 4M5.5 12v6.5a2 2 0 0 0 2 2h9a2 2 0 0 0 2-2V12" />,
  x: <path d="M6 6l12 12M18 6 6 18" />,
  list: <path d="M9 6.5h11M9 12h11M9 17.5h11M4.5 6.5h.01M4.5 12h.01M4.5 17.5h.01" />,
  shield: <><path d="M12 3.2 19 6v5.6c0 4.3-2.9 7.8-7 9.2-4.1-1.4-7-4.9-7-9.2V6z" /><path d="m9 12 2.2 2.2L15.5 10" /></>,
  clock: <><circle cx="12" cy="12" r="8.5" /><path d="M12 7.5V12l3 2" /></>,
  fingerprint: <path d="M7.2 5A8.6 8.6 0 0 1 20.5 12M4 9.5a8.4 8.4 0 0 0-.5 2.8M6.6 18.6c.6-1.9.9-3.9.9-6a4.5 4.5 0 0 1 9 0c0 1.4-.1 2.8-.4 4.1M12 12.5c0 3.2-.7 6.2-2 8.8M16.2 19.6c.3-.8.6-1.7.8-2.6" />,
  sidebar: <><rect x="3.5" y="4.5" width="17" height="15" rx="3" /><path d="M9.5 4.5v15" /></>,
  check: <><circle cx="12" cy="12" r="8.5" /><path d="m8.5 12 2.5 2.5 4.5-5" /></>,
  alert: <><circle cx="12" cy="12" r="8.5" /><path d="M12 7.5v5M12 16h.01" /></>,
  xcircle: <><circle cx="12" cy="12" r="8.5" /><path d="m9 9 6 6m0-6-6 6" /></>,
  dot: <><circle cx="12" cy="12" r="8.5" /><circle cx="12" cy="12" r="2.5" fill="currentColor" /></>,
};
export type IconName = keyof typeof PATHS;

export function Icon({ name, size = 22 }: { name: IconName; size?: number }) {
  return (
    <svg className="icon" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.7}
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
      {PATHS[name]}
    </svg>
  );
}

/** The assistant's face: a soft, friendly character used for the brand, the profile and the empty chat. */
export function Avatar({ size = 40 }: { size?: number }) {
  const id = useId();
  return (
    <svg className="avatar" width={size} height={size} viewBox="0 0 120 120" aria-hidden="true" focusable="false">
      <defs>
        <radialGradient id={`${id}b`} cx="50%" cy="40%" r="65%"><stop offset="0" stopColor="#fbfaf8" /><stop offset="1" stopColor="#e7e4df" /></radialGradient>
        <radialGradient id={`${id}f`} cx="45%" cy="35%" r="70%"><stop offset="0" stopColor="#fffaf3" /><stop offset="1" stopColor="#efe2cf" /></radialGradient>
      </defs>
      <circle cx="60" cy="60" r="60" fill={`url(#${id}b)`} />
      <path d="M60 16c-24 0-40 20-40 46 0 22 16 42 40 42s40-20 40-42c0-26-16-46-40-46z" fill="#f6f1ea" />
      <ellipse cx="60" cy="66" rx="29" ry="27" fill={`url(#${id}f)`} />
      <circle cx="49" cy="64" r="4.2" fill="#2b2622" /><circle cx="71" cy="64" r="4.2" fill="#2b2622" />
      <circle cx="50.3" cy="62.6" r="1.2" fill="#fff" /><circle cx="72.3" cy="62.6" r="1.2" fill="#fff" />
      <ellipse cx="42" cy="73" rx="5.5" ry="3" fill="#f2b6a6" opacity=".55" /><ellipse cx="78" cy="73" rx="5.5" ry="3" fill="#f2b6a6" opacity=".55" />
      <path d="M55.5 74.5q4.5 3.6 9 0" stroke="#2b2622" strokeWidth="2.2" fill="none" strokeLinecap="round" />
    </svg>
  );
}

const dayFmt = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" });
const timeFmt = new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" });

export function sameDay(a: Date, b: Date) {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

/** "Today", "Yesterday", "Tomorrow" or "Oct 12". */
export function dayLabel(iso: string) {
  const d = new Date(iso);
  const now = new Date();
  if (sameDay(d, now)) return "Today";
  if (sameDay(d, new Date(now.getTime() - 86_400_000))) return "Yesterday";
  if (sameDay(d, new Date(now.getTime() + 86_400_000))) return "Tomorrow";
  return dayFmt.format(d);
}

export const timeLabel = (iso: string) => timeFmt.format(new Date(iso));

/** "Today at 3:19 PM" or "Oct 12 at 3:19 PM". */
export const stamp = (iso: string) => `${dayLabel(iso)} at ${timeLabel(iso)}`;
