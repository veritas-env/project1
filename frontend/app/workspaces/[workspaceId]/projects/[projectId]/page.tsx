"use client";

import { use, useCallback, useEffect, useState } from "react";
import Shell from "@/components/Shell";
import {
  api, errorMessage, fmtDate, RANK, STATUS_LABEL,
  type Doc, type Milestone, type Priority, type Project, type Task, type TaskStatus,
} from "@/lib/api";
import { useMe, useWorkspace, wsBase } from "@/lib/useWorkspace";

const COLUMNS: TaskStatus[] = ["todo", "in_progress", "review", "done"];
const PRIORITY_STYLE: Record<Priority, string> = {
  urgent: "bg-red-100 text-red-800", high: "bg-orange-100 text-orange-800", medium: "bg-slate-100 text-slate-700", low: "bg-slate-50 text-slate-500",
};

export default function ProjectBoard({ params }: { params: Promise<{ workspaceId: string; projectId: string }> }) {
  const { workspaceId, projectId } = use(params);
  const { workspace, members, error, setError, nameOf } = useWorkspace(workspaceId, true);
  const [project, setProject] = useState<Project | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [milestones, setMilestones] = useState<Milestone[]>([]);
  const [docs, setDocs] = useState<Doc[]>([]);
  const [filter, setFilter] = useState<{ assignee: string; q: string }>({ assignee: "", q: "" });
  const [draft, setDraft] = useState({ title: "", priority: "medium" as Priority, assignee_id: "", milestone_id: "", due_date: "" });
  const [selected, setSelected] = useState<Task | null>(null);
  const [newMilestone, setNewMilestone] = useState({ name: "", due_date: "" });

  const base = wsBase(workspaceId);
  const pid = encodeURIComponent(projectId);

  const load = useCallback(async () => {
    try {
      const qs = new URLSearchParams();
      if (filter.assignee) qs.set("assignee", filter.assignee);
      if (filter.q) qs.set("q", filter.q);
      const [p, t, m, d] = await Promise.all([
        api<Project>(`${base}/projects/${pid}`),
        api<Task[]>(`${base}/projects/${pid}/tasks?${qs}`),
        api<Milestone[]>(`${base}/projects/${pid}/milestones`),
        api<Doc[]>(`${base}/documents?project_id=${pid}`),
      ]);
      setProject(p); setTasks(t); setMilestones(m); setDocs(d);
    } catch (e) { setError(errorMessage(e)); }
  }, [base, pid, filter, setError]);
  useEffect(() => { load(); }, [load]);

  const session = useMe();
  const role = workspace?.role;
  const canCreate = role && RANK[role] >= RANK.member && project?.status !== "archived";
  const canManage = role && RANK[role] >= RANK.manager;
  const canEdit = (t: Task) => canManage || (role === "member" && session && [t.created_by, t.assignee_id].includes(session.user.id));

  async function addTask(e: React.FormEvent) {
    e.preventDefault();
    try {
      await api(`${base}/projects/${pid}/tasks`, { method: "POST", json: {
        title: draft.title, priority: draft.priority, assignee_id: draft.assignee_id || null,
        milestone_id: draft.milestone_id || null, due_date: draft.due_date || null } });
      setDraft({ ...draft, title: "", due_date: "" });
      load();
    } catch (err) { setError(errorMessage(err)); }
  }

  async function patchTask(t: Task, changes: Partial<Task>) {
    try {
      const updated = await api<Task>(`${base}/tasks/${encodeURIComponent(t.id)}`, { method: "PATCH", json: changes });
      setSelected((s) => (s?.id === t.id ? updated : s));
      load();
    } catch (err) { setError(errorMessage(err)); }
  }

  async function deleteTask(t: Task) {
    if (!confirm(`Delete ${t.ref}?`)) return;
    try { await api(`${base}/tasks/${encodeURIComponent(t.id)}`, { method: "DELETE" }); setSelected(null); load(); }
    catch (err) { setError(errorMessage(err)); }
  }

  async function addMilestone(e: React.FormEvent) {
    e.preventDefault();
    try {
      await api(`${base}/projects/${pid}/milestones`, { method: "POST", json: { name: newMilestone.name, due_date: newMilestone.due_date || null } });
      setNewMilestone({ name: "", due_date: "" });
      load();
    } catch (err) { setError(errorMessage(err)); }
  }

  async function setProjectStatus(status: string) {
    try { await api(`${base}/projects/${pid}`, { method: "PATCH", json: { status } }); load(); }
    catch (err) { setError(errorMessage(err)); }
  }

  const doers = members.filter((m) => m.role !== "viewer");

  return (
    <Shell workspace={workspace}>
      {error && <p className="error mb-4" role="alert">{error}</p>}
      {project && (
        <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="font-mono text-sm text-slate-500">{project.key}</div>
            <h1>{project.name}</h1>
            <p className="mt-1 max-w-2xl text-sm text-slate-600">{project.description}</p>
            <p className="mt-1 text-xs text-slate-500">Lead: {nameOf(project.lead_id)} · {fmtDate(project.start_date)} → {fmtDate(project.target_date)}</p>
          </div>
          {canManage && (
            <select className="input w-auto" value={project.status} onChange={(e) => setProjectStatus(e.target.value)} aria-label="Project status">
              {["active", "on_hold", "completed", "archived"].map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}
            </select>
          )}
        </div>
      )}

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <input className="input max-w-56" placeholder="Search tasks" maxLength={100} value={filter.q}
               onChange={(e) => setFilter({ ...filter, q: e.target.value })} aria-label="Search tasks" />
        <select className="input w-auto" value={filter.assignee} onChange={(e) => setFilter({ ...filter, assignee: e.target.value })} aria-label="Filter by assignee">
          <option value="">Everyone</option>
          <option value="me">Assigned to me</option>
          <option value="none">Unassigned</option>
          {doers.map((m) => <option key={m.user_id} value={m.user_id}>{m.display_name}</option>)}
        </select>
      </div>

      {canCreate && (
        <form onSubmit={addTask} className="card mb-6 flex flex-wrap items-end gap-3 p-4">
          <div className="min-w-64 flex-1"><label className="label" htmlFor="tt">New task</label>
            <input id="tt" className="input" required maxLength={200} placeholder="What needs doing?" value={draft.title}
                   onChange={(e) => setDraft({ ...draft, title: e.target.value })} /></div>
          <select className="input w-auto" value={draft.priority} onChange={(e) => setDraft({ ...draft, priority: e.target.value as Priority })} aria-label="Priority">
            {(["low", "medium", "high", "urgent"] as Priority[]).map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
          <select className="input w-auto" value={draft.assignee_id} onChange={(e) => setDraft({ ...draft, assignee_id: e.target.value })} aria-label="Assignee">
            <option value="">Unassigned</option>
            {doers.map((m) => <option key={m.user_id} value={m.user_id}>{m.display_name}</option>)}
          </select>
          <select className="input w-auto" value={draft.milestone_id} onChange={(e) => setDraft({ ...draft, milestone_id: e.target.value })} aria-label="Milestone">
            <option value="">No milestone</option>
            {milestones.filter((m) => m.status === "open").map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
          </select>
          <input type="date" className="input w-auto" value={draft.due_date} onChange={(e) => setDraft({ ...draft, due_date: e.target.value })} aria-label="Due date" />
          <button className="btn">Add task</button>
        </form>
      )}

      <div className="grid gap-4 lg:grid-cols-4">
        {COLUMNS.map((col) => (
          <section key={col} className="rounded-lg bg-slate-100 p-3">
            <h2 className="mb-3 flex justify-between text-sm">{STATUS_LABEL[col]}<span className="text-slate-500">{tasks.filter((t) => t.status === col).length}</span></h2>
            <ul className="space-y-2">
              {tasks.filter((t) => t.status === col).map((t) => (
                <li key={t.id}>
                  <button onClick={() => setSelected(t)} className="w-full rounded-md border border-slate-200 bg-white p-3 text-left text-sm shadow-sm hover:border-indigo-300">
                    <div className="flex justify-between gap-2 text-xs">
                      <span className="font-mono text-slate-500">{t.ref}</span>
                      <span className={`rounded px-1.5 ${PRIORITY_STYLE[t.priority]}`}>{t.priority}</span>
                    </div>
                    <div className="mt-1 font-medium">{t.title}</div>
                    <div className="mt-2 flex justify-between text-xs text-slate-500">
                      <span>{nameOf(t.assignee_id)}</span><span>{t.due_date ? fmtDate(t.due_date) : ""}</span>
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>

      <div className="mt-8 grid gap-6 lg:grid-cols-2">
        <section className="card">
          <h2 className="mb-3">Milestones</h2>
          <ul className="space-y-2 text-sm">
            {milestones.map((m) => (
              <li key={m.id} className="flex items-center justify-between gap-2">
                <span className={m.status === "closed" ? "text-slate-400 line-through" : ""}>{m.name}</span>
                <span className="text-slate-500">{m.done_tasks}/{m.open_tasks + m.done_tasks} · {fmtDate(m.due_date)}</span>
              </li>
            ))}
            {milestones.length === 0 && <li className="text-slate-500">No milestones.</li>}
          </ul>
          {canManage && (
            <form onSubmit={addMilestone} className="mt-4 flex gap-2">
              <input className="input" required maxLength={120} placeholder="Milestone name" value={newMilestone.name}
                     onChange={(e) => setNewMilestone({ ...newMilestone, name: e.target.value })} />
              <input type="date" className="input w-auto" value={newMilestone.due_date} onChange={(e) => setNewMilestone({ ...newMilestone, due_date: e.target.value })} aria-label="Milestone due date" />
              <button className="btn">Add</button>
            </form>
          )}
        </section>
        <section className="card">
          <h2 className="mb-3">Project documents</h2>
          <ul className="space-y-2 text-sm">
            {docs.map((d) => (
              <li key={d.id} className="flex justify-between gap-2">
                <a className="truncate underline" href={d.download_url}>{d.title}</a>
                <span className="shrink-0 text-slate-500">{fmtDate(d.created_at)}</span>
              </li>
            ))}
            {docs.length === 0 && <li className="text-slate-500">No documents linked to this project.</li>}
          </ul>
        </section>
      </div>

      {selected && (
        <div className="fixed inset-0 z-10 flex justify-end bg-slate-900/30" onClick={() => setSelected(null)}>
          <aside className="h-full w-full max-w-md overflow-y-auto bg-white p-6 shadow-xl" onClick={(e) => e.stopPropagation()} aria-label="Task details">
            <div className="mb-4 flex items-start justify-between gap-2">
              <div><div className="font-mono text-xs text-slate-500">{selected.ref}</div><h2>{selected.title}</h2></div>
              <button className="btn-quiet" onClick={() => setSelected(null)} aria-label="Close">✕</button>
            </div>
            {selected.description && <p className="mb-4 whitespace-pre-wrap text-sm text-slate-700">{selected.description}</p>}
            <dl className="space-y-3 text-sm">
              <Field label="Status">
                <select className="input" disabled={!canEdit(selected)} value={selected.status} onChange={(e) => patchTask(selected, { status: e.target.value as TaskStatus })}>
                  {COLUMNS.map((c) => <option key={c} value={c}>{STATUS_LABEL[c]}</option>)}
                </select>
              </Field>
              <Field label="Priority">
                <select className="input" disabled={!canEdit(selected)} value={selected.priority} onChange={(e) => patchTask(selected, { priority: e.target.value as Priority })}>
                  {(["low", "medium", "high", "urgent"] as Priority[]).map((p) => <option key={p} value={p}>{p}</option>)}
                </select>
              </Field>
              <Field label="Assignee">
                <select className="input" disabled={!canEdit(selected)} value={selected.assignee_id ?? ""} onChange={(e) => patchTask(selected, { assignee_id: e.target.value || null })}>
                  <option value="">Unassigned</option>
                  {doers.map((m) => <option key={m.user_id} value={m.user_id}>{m.display_name}</option>)}
                </select>
              </Field>
              <Field label="Due">{fmtDate(selected.due_date)}</Field>
              <Field label="Milestone">{milestones.find((m) => m.id === selected.milestone_id)?.name ?? "—"}</Field>
            </dl>
            {canManage && <button className="btn-quiet mt-6 text-red-700" onClick={() => deleteTask(selected)}>Delete task</button>}
          </aside>
        </div>
      )}
    </Shell>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (<div><dt className="mb-1 text-xs uppercase tracking-wide text-slate-500">{label}</dt><dd>{children}</dd></div>);
}
