"use client";

import { timeAgo, type ActivityItem } from "@/lib/api";

export function ActivityList({ items }: { items: ActivityItem[] }) {
  if (items.length === 0) return <p className="text-sm text-slate-500">No activity yet.</p>;
  return (
    <ul className="divide-y divide-slate-100 text-sm">
      {items.map((a) => (
        <li key={a.id} className="flex items-start justify-between gap-4 py-2">
          <span>
            <span className="font-medium">{a.actor_name ?? "Someone"}</span>{" "}
            {a.link ? <a href={a.link} className="text-slate-700 hover:underline">{a.summary}</a> : <span className="text-slate-700">{a.summary}</span>}
          </span>
          <time className="shrink-0 text-xs text-slate-500" dateTime={a.at} title={new Date(a.at).toLocaleString()}>{timeAgo(a.at)}</time>
        </li>
      ))}
    </ul>
  );
}
