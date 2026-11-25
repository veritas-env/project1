"use client";

import { use, useCallback, useEffect, useState } from "react";
import Shell from "@/components/Shell";
import { ActivityList } from "@/components/ActivityList";
import { api, errorMessage, type ActivityItem } from "@/lib/api";
import { useWorkspace, wsBase } from "@/lib/useWorkspace";

const PAGE = 50;

export default function ActivityPage({ params }: { params: Promise<{ workspaceId: string }> }) {
  const { workspaceId } = use(params);
  const { workspace, error, setError } = useWorkspace(workspaceId);
  const [items, setItems] = useState<ActivityItem[]>([]);
  const [more, setMore] = useState(true);

  const loadMore = useCallback(async (before?: number) => {
    try {
      const page = await api<ActivityItem[]>(`${wsBase(workspaceId)}/activity?limit=${PAGE}${before ? `&before=${before}` : ""}`);
      setItems((prev) => (before ? [...prev, ...page] : page));
      setMore(page.length === PAGE);
    } catch (e) { setError(errorMessage(e)); }
  }, [workspaceId, setError]);

  useEffect(() => { loadMore(); }, [loadMore]);

  return (
    <Shell workspace={workspace}>
      <h1 className="mb-6">Activity</h1>
      {error && <p className="error mb-4">{error}</p>}
      <section className="card">
        <ActivityList items={items} />
        {more && items.length > 0 && (
          <button className="btn-quiet mt-4" onClick={() => loadMore(items[items.length - 1]?.id)}>Load older</button>
        )}
      </section>
    </Shell>
  );
}
