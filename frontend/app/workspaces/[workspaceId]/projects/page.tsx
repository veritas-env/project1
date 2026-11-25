"use client";

import Link from "next/link";
import { use, useCallback, useEffect, useState } from "react";
import Shell from "@/components/Shell";
import { api, errorMessage, fmtDate, RANK, type Project } from "@/lib/api";
import { useWorkspace, wsBase } from "@/lib/useWorkspace";

const STATUS_STYLE: Record<string, string> = {
  active: "bg-emerald-50 text-emerald-800",
  on_hold: "bg-amber-50 text-amber-800",
  completed: "bg-slate-100 text-slate-700",
  archived: "bg-slate-100 text-slate-500",
};

export default function ProjectsPage({ params }: { params: Promise<{ workspaceId: string }> }) {
  const { workspaceId } = use(params);
  const { workspace, members, error, setError, nameOf } = useWorkspace(workspaceId, true);
  const [projects, setProjects] = useState<Project[]>([]);
  const [showArchived, setShowArchived] = useState(false);
  const [form, setForm] = useState({ key: "", name: "", description: "", lead_id: "", target_date: "" });
  const [creating, setCreating] = useState(false);

  const load = useCallback(() => {
    api<Project[]>(`${wsBase(workspaceId)}/projects?include_archived=${showArchived}`).then(setProjects).catch((e) => setError(errorMessage(e)));
  }, [workspaceId, showArchived, setError]);
  useEffect(load, [load]);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    try {
      await api(`${wsBase(workspaceId)}/projects`, {
        method: "POST",
        json: { key: form.key, name: form.name, description: form.description, lead_id: form.lead_id || null, target_date: form.target_date || null },
      });
      setForm({ key: "", name: "", description: "", lead_id: "", target_date: "" });
      setCreating(false);
      load();
    } catch (err) { setError(errorMessage(err)); }
  }

  const canManage = workspace && RANK[workspace.role] >= RANK.manager;
  const base = `/workspaces/${encodeURIComponent(workspaceId)}`;

  return (
    <Shell workspace={workspace}>
      <div className="mb-6 flex items-center justify-between">
        <h1>Projects</h1>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-slate-600">
            <input type="checkbox" checked={showArchived} onChange={(e) => setShowArchived(e.target.checked)} /> Show archived
          </label>
          {canManage && <button className="btn" onClick={() => setCreating((v) => !v)}>New project</button>}
        </div>
      </div>
      {error && <p className="error mb-4" role="alert">{error}</p>}

      {creating && (
        <form onSubmit={create} className="card mb-6 grid gap-3 sm:grid-cols-2">
          <div><label className="label" htmlFor="k">Key</label>
            <input id="k" className="input font-mono uppercase" required pattern="[A-Z][A-Z0-9]{1,7}" maxLength={8} placeholder="e.g. WEB"
                   value={form.key} onChange={(e) => setForm({ ...form, key: e.target.value.toUpperCase() })} /></div>
          <div><label className="label" htmlFor="n">Name</label>
            <input id="n" className="input" required maxLength={120} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
          <div className="sm:col-span-2"><label className="label" htmlFor="d">Description</label>
            <textarea id="d" className="input" rows={2} maxLength={5000} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></div>
          <div><label className="label" htmlFor="l">Lead</label>
            <select id="l" className="input" value={form.lead_id} onChange={(e) => setForm({ ...form, lead_id: e.target.value })}>
              <option value="">No lead</option>
              {members.filter((m) => m.role !== "viewer").map((m) => <option key={m.user_id} value={m.user_id}>{m.display_name}</option>)}
            </select></div>
          <div><label className="label" htmlFor="t">Target date</label>
            <input id="t" type="date" className="input" value={form.target_date} onChange={(e) => setForm({ ...form, target_date: e.target.value })} /></div>
          <div className="sm:col-span-2"><button className="btn">Create project</button></div>
        </form>
      )}

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {projects.map((p) => {
          const total = p.open_tasks + p.done_tasks;
          const pct = total ? Math.round((p.done_tasks / total) * 100) : 0;
          return (
            <Link key={p.id} href={`${base}/projects/${encodeURIComponent(p.id)}`} className="card block hover:border-indigo-300">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="font-mono text-xs text-slate-500">{p.key}</div>
                  <div className="font-medium">{p.name}</div>
                </div>
                <span className={`rounded px-2 py-0.5 text-xs ${STATUS_STYLE[p.status]}`}>{p.status.replace("_", " ")}</span>
              </div>
              <p className="mt-2 line-clamp-2 text-sm text-slate-600">{p.description}</p>
              <div className="mt-4 h-1.5 rounded bg-slate-100"><div className="h-1.5 rounded bg-indigo-500" style={{ width: `${pct}%` }} /></div>
              <div className="mt-2 flex justify-between text-xs text-slate-500">
                <span>{p.done_tasks}/{total} tasks done</span>
                <span>Lead: {nameOf(p.lead_id)} · {fmtDate(p.target_date)}</span>
              </div>
            </Link>
          );
        })}
      </div>
      {projects.length === 0 && <p className="text-slate-500">No projects yet.</p>}
    </Shell>
  );
}
