import { useState } from "react";
import { RefreshCw, ScrollText } from "lucide-react";

import { DataTablePage } from "@/components/layout/data-table-page";
import {
  Badge,
  Button,
  ColumnToggle,
  DataTable,
  EmptyState,
  ErrorState,
  Pagination,
  Select,
  useColumnVisibility,
  type DataTableColumn,
} from "@/components/ui";
import type { AuditEvent } from "@/features/audit/types";
import { api } from "@/lib/api";
import { formatAuditAction, formatDateTime } from "@/lib/format";
import type { Page } from "@/lib/types";
import { useResource } from "@/lib/use-resource";

const PAGE_SIZE = 50;
const OUTCOME_TONE = { success: "success", failure: "danger", denied: "warning" } as const;

const COLUMNS: DataTableColumn<AuditEvent>[] = [
  {
    id: "when",
    header: "When",
    hideable: false,
    className: "whitespace-nowrap text-[#888] tabular-nums",
    cell: (event) => formatDateTime(event.created_at),
  },
  {
    id: "event",
    header: "Event",
    hideable: false,
    cell: (event) => (
      <>
        <span className="font-medium text-[#ddd]">{formatAuditAction(event.action)}</span>
        <span className="ml-2 font-mono text-[10px] text-[#5f5f5f]">{event.action}</span>
      </>
    ),
  },
  { id: "actor", header: "Actor", cell: (event) => event.actor_email ?? "—" },
  {
    id: "outcome",
    header: "Outcome",
    cell: (event) => <Badge tone={OUTCOME_TONE[event.outcome] ?? "neutral"}>{event.outcome}</Badge>,
  },
  {
    id: "ip",
    header: "IP address",
    className: "font-mono text-[11px]",
    cell: (event) => event.ip_address ?? "—",
  },
  {
    id: "target",
    header: "Target",
    defaultHidden: true,
    className: "font-mono text-[11px] text-[#777]",
    cell: (event) => (event.target_type ? `${event.target_type}:${event.target_id ?? ""}` : "—"),
  },
  {
    id: "details",
    header: "Details",
    className: "max-w-64 truncate font-mono text-[10px] text-[#777]",
    cell: (event) => (event.detail ? JSON.stringify(event.detail) : ""),
  },
];

export function AuditLogPage() {
  const [action, setAction] = useState("");
  const [outcome, setOutcome] = useState("");
  const [page, setPage] = useState(1);
  const columnState = useColumnVisibility("audit", COLUMNS);
  const { data, error, loading, reload } = useResource(
    () => api.get<Page<AuditEvent>>("/audit", { action, outcome, page, page_size: PAGE_SIZE }),
    [action, outcome, page],
  );

  return (
    <DataTablePage
      eyebrow="Security"
      title="Audit log"
      description="Every sign-in, account change and administrative action, newest first."
      toolbar={
        <>
          <div className="w-44">
            <Select
              aria-label="Filter by event type"
              value={action}
              onChange={(e) => {
                setAction(e.target.value);
                setPage(1);
              }}
            >
              <option value="">All events</option>
              <option value="auth.">Authentication</option>
              <option value="user.">User changes</option>
              <option value="role.">Role changes</option>
              <option value="session.">Sessions</option>
            </Select>
          </div>
          <div className="w-36">
            <Select
              aria-label="Filter by outcome"
              value={outcome}
              onChange={(e) => {
                setOutcome(e.target.value);
                setPage(1);
              }}
            >
              <option value="">Any outcome</option>
              <option value="success">Success</option>
              <option value="failure">Failure</option>
              <option value="denied">Denied</option>
            </Select>
          </div>
          {data && <span className="text-xs text-[#777] tabular-nums">{data.total} events</span>}
        </>
      }
      actions={
        <>
          <ColumnToggle state={columnState} />
          <Button onClick={() => void reload()} loading={loading && !!data}>
            {!(loading && data) && <RefreshCw size={13} />} Refresh
          </Button>
        </>
      }
    >
      {error ? (
        <ErrorState description={error.message} onRetry={reload} />
      ) : (
        <DataTable
          label="Audit events"
          columns={columnState.visibleColumns}
          rows={data?.items ?? []}
          rowKey={(event) => event.id}
          loading={loading && !data}
          minWidth={760}
          empty={<EmptyState icon={<ScrollText size={22} />} title="No events" description="Nothing matches these filters." />}
          footer={
            data && data.total > PAGE_SIZE ? (
              <Pagination page={page} pageSize={PAGE_SIZE} total={data.total} onPageChange={setPage} />
            ) : undefined
          }
        />
      )}
    </DataTablePage>
  );
}
