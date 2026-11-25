"use client";

import { use, useCallback, useEffect, useState } from "react";
import Shell from "@/components/Shell";
import { api, errorMessage, fmtDate, RANK, type Doc, type Project } from "@/lib/api";
import { useWorkspace, wsBase } from "@/lib/useWorkspace";

const CATEGORIES = ["general", "specification", "contract", "report", "meeting_notes", "design"];
const label = (c: string) => c.replace("_", " ").replace(/^\w/, (x) => x.toUpperCase());

export default function DocumentsPage({ params }: { params: Promise<{ workspaceId: string }> }) {
  const { workspaceId } = use(params);
  const { workspace, error, setError, nameOf } = useWorkspace(workspaceId, true);
  const [docs, setDocs] = useState<Doc[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [category, setCategory] = useState("general");
  const [projectId, setProjectId] = useState("");
  const [busy, setBusy] = useState(false);
  const [filter, setFilter] = useState("");

  const base = wsBase(workspaceId);
  const load = useCallback(() => {
    api<Doc[]>(`${base}/documents`).then(setDocs).catch((e) => setError(errorMessage(e)));
    api<Project[]>(`${base}/projects`).then(setProjects).catch(() => {});
  }, [base, setError]);
  useEffect(load, [load]);

  async function upload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    form.append("category", category);
    if (projectId) form.append("project_id", projectId);
    setBusy(true);
    try { await api(`${base}/documents`, { method: "POST", body: form }); load(); }
    catch (err) { setError(errorMessage(err)); }
    finally { setBusy(false); e.target.value = ""; }
  }

  async function remove(d: Doc) {
    if (!confirm(`Delete “${d.title}”?`)) return;
    try { await api(`${base}/documents/${encodeURIComponent(d.id)}`, { method: "DELETE" }); load(); }
    catch (err) { setError(errorMessage(err)); }
  }

  const canUpload = workspace && RANK[workspace.role] >= RANK.member;
  const canDelete = workspace && RANK[workspace.role] >= RANK.manager;
  const projectName = (id: string | null) => projects.find((p) => p.id === id)?.key ?? "—";
  const shown = docs.filter((d) => !filter || d.category === filter);

  return (
    <Shell workspace={workspace}>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <h1>Documents</h1>
        <select className="input w-auto" value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="Filter by category">
          <option value="">All categories</option>
          {CATEGORIES.map((c) => <option key={c} value={c}>{label(c)}</option>)}
        </select>
      </div>
      {error && <p className="error mb-4" role="alert">{error}</p>}

      {canUpload && (
        <div className="card mb-6 flex flex-wrap items-end gap-3 p-4">
          <div><label className="label" htmlFor="cat">Category</label>
            <select id="cat" className="input w-auto" value={category} onChange={(e) => setCategory(e.target.value)}>
              {CATEGORIES.map((c) => <option key={c} value={c}>{label(c)}</option>)}
            </select></div>
          <div><label className="label" htmlFor="proj">Project</label>
            <select id="proj" className="input w-auto" value={projectId} onChange={(e) => setProjectId(e.target.value)}>
              <option value="">None</option>
              {projects.map((p) => <option key={p.id} value={p.id}>{p.key} · {p.name}</option>)}
            </select></div>
          <label className={`btn cursor-pointer ${busy ? "opacity-50" : ""}`}>
            {busy ? "Uploading…" : "Upload document"}
            <input type="file" className="sr-only" disabled={busy}
                   accept=".png,.jpg,.jpeg,.pdf,.txt,.md,image/png,image/jpeg,application/pdf,text/plain,text/markdown" onChange={upload} />
          </label>
          <p className="text-xs text-slate-500">PNG, JPEG, PDF, text or Markdown. Up to 10 MB.</p>
        </div>
      )}

      <div className="card overflow-x-auto p-0">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-slate-200 text-slate-500">
            <tr><th className="px-4 py-2">Title</th><th className="px-4 py-2">Category</th><th className="px-4 py-2">Project</th>
              <th className="px-4 py-2">Uploaded by</th><th className="px-4 py-2">Date</th><th className="px-4 py-2 text-right">Size</th><th /></tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {shown.map((d) => (
              <tr key={d.id}>
                <td className="px-4 py-2"><a className="font-medium text-indigo-700 hover:underline" href={d.download_url}>{d.title}</a></td>
                <td className="px-4 py-2">{label(d.category)}</td>
                <td className="px-4 py-2 font-mono text-xs">{projectName(d.project_id)}</td>
                <td className="px-4 py-2">{nameOf(d.uploader_id)}</td>
                <td className="px-4 py-2 text-slate-500">{fmtDate(d.created_at)}</td>
                <td className="px-4 py-2 text-right text-slate-500">{Math.max(1, Math.round(d.size / 1024))} KB</td>
                <td className="px-4 py-2 text-right">{canDelete && <button className="btn-quiet text-red-700" onClick={() => remove(d)}>Delete</button>}</td>
              </tr>
            ))}
            {shown.length === 0 && <tr><td colSpan={7} className="px-4 py-6 text-center text-slate-500">No documents.</td></tr>}
          </tbody>
        </table>
      </div>
    </Shell>
  );
}
