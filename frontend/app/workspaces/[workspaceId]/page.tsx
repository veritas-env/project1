"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";
import Shell from "@/components/Shell";
import { ActivityList } from "@/components/ActivityList";
import { api, errorMessage, fmtDate, STATUS_LABEL, type Dashboard, type TaskStatus } from "@/lib/api";
import { useWorkspace, wsBase } from "@/lib/useWorkspace";

export default function OverviewPage({ params }: { params: Promise<{ workspaceId: string }> }) {
  const { workspaceId } = use(params);
  const { workspace, error, setError } = useWorkspace(workspaceId);
  const [d, setD] = useState<Dashboard | null>(null);

  useEffect(() => {
    api<Dashboard>(`${wsBase(workspaceId)}/dashboard`).then(setD).catch((e) => setError(errorMessage(e)));
  }, [workspaceId, setError]);

  const base = `/workspaces/${encodeURIComponent(workspaceId)}`;
  return (
    <Shell workspace={workspace}>
      {error && <p className="error mb-4">{error}</p>}
      <h1 className="mb-6">Overview</h1>
      {d && (
        <>
          <div className="mb-6 grid gap-4 sm:grid-cols-3 lg:grid-cols-6">
            <Stat label="Active projects" value={d.projects_active} />
            {(Object.keys(STATUS_LABEL) as TaskStatus[]).map((s) => <Stat key={s} label={STATUS_LABEL[s]} value={d.tasks_by_status[s] ?? 0} />)}
            <Stat label="Overdue" value={d.overdue_tasks} warn={d.overdue_tasks > 0} />
          </div>
          <div className="grid gap-6 lg:grid-cols-3">
            <section className="card lg:col-span-2">
              <h2 className="mb-3">My open tasks</h2>
              {d.my_open_tasks.length === 0 && <p className="text-sm text-slate-500">Nothing assigned to you. 🎉</p>}
              <ul className="divide-y divide-slate-100">
                {d.my_open_tasks.map((t) => (
                  <li key={t.id} className="flex items-center justify-between gap-3 py-2 text-sm">
                    <Link href={`${base}/projects/${encodeURIComponent(t.project_id)}`} className="hover:underline">
                      <span className="mr-2 font-mono text-xs text-slate-500">{t.ref}</span>{t.title}
                    </Link>
                    <span className="shrink-0 text-slate-500">{STATUS_LABEL[t.status]} · due {fmtDate(t.due_date)}</span>
                  </li>
                ))}
              </ul>
            </section>
            <section className="card">
              <h2 className="mb-3">Upcoming milestones</h2>
              {d.upcoming_milestones.length === 0 && <p className="text-sm text-slate-500">None in the next 45 days.</p>}
              <ul className="space-y-2 text-sm">
                {d.upcoming_milestones.map((m) => (
                  <li key={m.id} className="flex justify-between gap-2">
                    <Link href={`${base}/projects/${encodeURIComponent(m.project_id)}`} className="hover:underline">{m.name}</Link>
                    <span className="shrink-0 text-slate-500">{fmtDate(m.due_date)}</span>
                  </li>
                ))}
              </ul>
            </section>
            <section className="card lg:col-span-3">
              <div className="mb-3 flex items-center justify-between">
                <h2>Recent activity</h2>
                <Link href={`${base}/activity`} className="text-sm text-indigo-700 hover:underline">View all</Link>
              </div>
              <ActivityList items={d.recent_activity} />
            </section>
          </div>
        </>
      )}
    </Shell>
  );
}

function Stat({ label, value, warn }: { label: string; value: number; warn?: boolean }) {
  return (
    <div className="card p-4">
      <div className={`text-2xl font-semibold ${warn ? "text-red-700" : ""}`}>{value}</div>
      <div className="text-xs text-slate-500">{label}</div>
    </div>
  );
}
