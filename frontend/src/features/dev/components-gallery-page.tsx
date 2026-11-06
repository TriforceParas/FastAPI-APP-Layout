/**
 * Living reference of every UI component. Hidden in production
 * (APP_ENV=production). When building a new screen, copy patterns from here.
 */
import { useState, type ReactNode } from "react";
import { Bell, ChevronDown, Inbox, Plus, Settings, Trash2, Users } from "lucide-react";

import { PageHeader } from "@/components/layout/page-header";
import {
  Accordion,
  Alert,
  AlertDialog,
  Avatar,
  Badge,
  Breadcrumb,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
  Checkbox,
  CommandMenu,
  CurrencyInput,
  DateInput,
  DescriptionList,
  Dialog,
  Drawer,
  DropdownItem,
  DropdownMenu,
  EmptyState,
  ErrorState,
  ErrorSummary,
  Field,
  IconButton,
  Input,
  Kbd,
  LoadingState,
  Pagination,
  PasswordInput,
  Progress,
  RadioGroup,
  SearchInput,
  Select,
  Separator,
  Skeleton,
  Slider,
  StatCard,
  StatGrid,
  SuccessState,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  Tabs,
  Textarea,
  Toggle,
  ToggleGroup,
  Tooltip,
  useToast,
  ColumnToggle,
  DataTable,
  useColumnVisibility,
  type DataTableColumn,
  CardSkeleton,
  SkeletonText,
  TableSkeleton,
} from "@/components/ui";

function Section({ title, code, children }: { title: string; code?: string; children: ReactNode }) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-3">
        <CardTitle>{title}</CardTitle>
        {code && <code className="truncate font-mono text-[10px] text-[#666]">{code}</code>}
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

type DemoRow = { id: number; name: string; team: string; status: "Active" | "Invited" | "Suspended"; joined: string };

const DEMO_ROWS: DemoRow[] = Array.from({ length: 24 }, (_, i) => ({
  id: i + 1,
  name: ["Ada Lovelace", "Grace Hopper", "Alan Turing", "Katherine Johnson", "Linus Torvalds", "Margaret Hamilton"][i % 6]!,
  team: ["Platform", "Finance", "Operations", "Sales"][i % 4]!,
  status: (["Active", "Invited", "Suspended"] as const)[i % 3]!,
  joined: `${String((i % 28) + 1).padStart(2, "0")}/0${(i % 9) + 1}/2026`,
}));

const DEMO_COLUMNS: DataTableColumn<DemoRow>[] = [
  { id: "name", header: "Name", hideable: false, cell: (r) => <span className="font-medium text-[#ddd]">{r.name}</span> },
  { id: "team", header: "Team", cell: (r) => r.team },
  {
    id: "status",
    header: "Status",
    cell: (r) => (
      <Badge tone={r.status === "Active" ? "success" : r.status === "Invited" ? "info" : "danger"}>{r.status}</Badge>
    ),
  },
  { id: "joined", header: "Joined", defaultHidden: true, className: "tabular-nums", cell: (r) => r.joined },
];

function DataTableDemo() {
  const columns = useColumnVisibility("gallery-demo", DEMO_COLUMNS);
  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <ColumnToggle state={columns} />
      </div>
      {/* Standalone use: give the container a height. On list pages, use <DataTablePage> instead. */}
      <div className="flex h-72 flex-col">
        <DataTable label="Demo" columns={columns.visibleColumns} rows={DEMO_ROWS} rowKey={(r) => r.id} />
      </div>
    </div>
  );
}

export function ComponentsGalleryPage() {
  const toast = useToast();
  const [page, setPage] = useState(2);
  const [bold, setBold] = useState(true);
  const [controlled, setControlled] = useState(false);

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="Developer reference"
        title="Components"
        description='Every building block in "@/components/ui". Import from there; never restyle ad hoc.'
      />

      <div className="grid gap-5 xl:grid-cols-2">
        <Section title="Buttons" code="<Button variant size loading />">
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="primary">Primary</Button>
            <Button>Secondary</Button>
            <Button variant="ghost">Ghost</Button>
            <Button variant="danger">
              <Trash2 size={13} /> Danger
            </Button>
            <Button variant="primary" loading>
              Saving
            </Button>
            <Button disabled>Disabled</Button>
            <Button size="sm">Small</Button>
            <Button size="lg">Large</Button>
            <IconButton aria-label="Settings">
              <Settings size={15} />
            </IconButton>
          </div>
        </Section>

        <Section title="Badges & avatars" code='<Badge tone="success" />'>
          <div className="flex flex-wrap items-center gap-2">
            <Badge>Neutral</Badge>
            <Badge tone="success">Success</Badge>
            <Badge tone="warning">Warning</Badge>
            <Badge tone="danger">Danger</Badge>
            <Badge tone="info">Info</Badge>
            <Separator className="my-2" />
            <Avatar name="Ada Lovelace" size="sm" />
            <Avatar name="Grace Hopper" />
            <Avatar name="Alan Turing" size="lg" />
            <Kbd>⌘ K</Kbd>
            <Tooltip label="Native tooltip">
              <span className="text-xs text-[#888] underline decoration-dotted">Hover me</span>
            </Tooltip>
          </div>
        </Section>

        <Section title="Form fields" code="<Field label><Input /></Field>">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Text input" hint="Helper text">
              <Input placeholder="Placeholder" />
            </Field>
            <Field label="With error" error="This field is required">
              <Input aria-invalid />
            </Field>
            <Field label="Select">
              <Select defaultValue="b">
                <option value="a">Option A</option>
                <option value="b">Option B</option>
              </Select>
            </Field>
            <Field label="Date (DD/MM/YYYY)">
              <DateInput name="date" defaultValue="2026-11-05" />
            </Field>
            <Field label="Currency">
              <CurrencyInput symbol="$" placeholder="0.00" />
            </Field>
            <Field label="Search">
              <SearchInput placeholder="Search…" />
            </Field>
            <Field label="Password" className="sm:col-span-2">
              <PasswordInput name="demo-password" showStrength />
            </Field>
            <Field label="Textarea" className="sm:col-span-2">
              <Textarea placeholder="Longer text…" />
            </Field>
          </div>
        </Section>

        <Section title="Choices" code="<Checkbox /> <Switch /> <RadioGroup />">
          <div className="space-y-4">
            <div className="flex flex-wrap gap-5">
              <Checkbox label="Checkbox" defaultChecked />
              <Switch label="Switch" defaultChecked />
              <Switch label="Off" />
            </div>
            <RadioGroup
              name="plan"
              defaultValue="pro"
              options={[
                { value: "free", label: "Free", description: "For individuals" },
                { value: "pro", label: "Pro", description: "For small teams" },
              ]}
            />
            <Slider defaultValue={40} aria-label="Slider" />
            <ToggleGroup>
              <Toggle pressed={bold} onClick={() => setBold(!bold)}>
                Bold
              </Toggle>
              <Toggle pressed={!bold} onClick={() => setBold(!bold)}>
                Regular
              </Toggle>
            </ToggleGroup>
          </div>
        </Section>

        <Section title="Alerts & feedback" code='<Alert tone title /> · useToast()'>
          <div className="space-y-3">
            <Alert tone="info" title="Information">Supporting copy goes here.</Alert>
            <Alert tone="success" title="Saved successfully" />
            <Alert tone="warning" title="Check your input" />
            <Alert tone="danger" title="Something failed">Explain what to do next.</Alert>
            <ErrorSummary errors={["Email is required", "Password is too short"]} />
            <div className="flex flex-wrap gap-2">
              <Button onClick={() => toast.success("Changes saved", "Everything is up to date.")}>Success toast</Button>
              <Button onClick={() => toast.error("Request failed", "Try again in a moment.")}>Error toast</Button>
              <Button onClick={() => toast.toast({ title: "Heads up", tone: "warning" })}>Warning toast</Button>
            </div>
            <Progress value={64} />
            <div className="flex gap-2">
              <Skeleton className="h-8 w-8 rounded-full" />
              <Skeleton className="h-8 flex-1" />
            </div>
          </div>
        </Section>

        <Section title="Overlays" code="<Dialog trigger | open onOpenChange />">
          <div className="flex flex-wrap gap-2">
            <Dialog trigger={<Button>Open dialog</Button>} title="Dialog title" description="Optional description.">
              {(close) => (
                <div className="space-y-4">
                  <Field label="Name">
                    <Input autoFocus />
                  </Field>
                  <div className="flex justify-end gap-2">
                    <Button onClick={close}>Cancel</Button>
                    <Button variant="primary" onClick={close}>
                      Save
                    </Button>
                  </div>
                </div>
              )}
            </Dialog>
            <Button onClick={() => setControlled(true)}>Controlled dialog</Button>
            <Dialog open={controlled} onOpenChange={setControlled} title="Controlled" size="sm">
              Open state lives in the parent component.
            </Dialog>
            <AlertDialog
              trigger={<Button variant="danger">Confirm action</Button>}
              title="Delete project?"
              description="This cannot be undone."
              confirmLabel="Delete"
              onConfirm={async () => {
                await new Promise((r) => setTimeout(r, 600));
                toast.success("Deleted");
              }}
            />
            <Drawer trigger={<Button>Open drawer</Button>} title="Drawer">
              <p className="text-xs text-[#888]">Side panels for detail views and filters.</p>
            </Drawer>
            <DropdownMenu
              className="h-8 gap-1.5 border border-white/[0.1] bg-white/[0.04] px-3 text-xs hover:bg-white/[0.075]"
              trigger={
                <>
                  Dropdown <ChevronDown size={13} />
                </>
              }
            >
              <DropdownItem>
                <Plus size={13} /> New item
              </DropdownItem>
              <DropdownItem>
                <Bell size={13} /> Notify
              </DropdownItem>
              <DropdownItem className="text-rose-300">
                <Trash2 size={13} /> Delete
              </DropdownItem>
            </DropdownMenu>
          </div>
        </Section>

        <Section title="Navigation" code="<Tabs /> <Breadcrumb /> <Accordion />">
          <div className="space-y-4">
            <Breadcrumb items={[{ label: "Home", href: "/dashboard" }, { label: "Users", href: "/users" }, { label: "Ada" }]} />
            <Tabs
              items={[
                { value: "one", label: "Overview", content: <p className="text-xs text-[#888]">First tab content.</p> },
                { value: "two", label: "Activity", content: <p className="text-xs text-[#888]">Second tab content.</p> },
              ]}
            />
            <Accordion
              items={[
                { title: "What is this?", content: "A disclosure built on <details>." },
                { title: "Is it accessible?", content: "Yes, keyboard and screen-reader friendly." },
              ]}
            />
          </div>
        </Section>

        <Section title="Command menu" code="<CommandMenu commands />  (⌘K opens the palette)">
          <CommandMenu
            commands={[
              { label: "Go to dashboard", section: "Navigation" },
              { label: "Invite user", section: "Actions", icon: <Users size={14} /> },
              { label: "Open settings", section: "Navigation", icon: <Settings size={14} /> },
            ]}
          />
        </Section>
      </div>

      <Section title="Stats" code="<StatGrid><StatCard /></StatGrid>">
        <StatGrid>
          <StatCard label="Revenue" value="$12,400" note="+8% vs last month" icon={Inbox} />
          <StatCard label="Users" value="1,204" note="34 new this week" icon={Users} />
          <StatCard label="Tickets" value="18" note="3 overdue" icon={Bell} />
          <StatCard label="Uptime" value="99.98%" note="Last 30 days" icon={Settings} />
        </StatGrid>
      </Section>

      <Section
        title="Skeletons (use these while content loads)"
        code="<Skeleton/> <SkeletonText/> <CardSkeleton/> <TableSkeleton/> <PageSkeleton variant/> <AppShellSkeleton/>"
      >
        <div className="grid gap-5 xl:grid-cols-2">
          <div className="space-y-4">
            <div className="flex items-center gap-3">
              <Skeleton className="size-8 rounded-full" />
              <div className="flex-1 space-y-2">
                <Skeleton className="h-3 w-40" />
                <Skeleton className="h-3 w-24" />
              </div>
            </div>
            <SkeletonText lines={3} />
            <CardSkeleton lines={2} />
          </div>
          <TableSkeleton rows={4} columns={4} />
        </div>
      </Section>

      <Section
        title="Data table"
        code="<DataTablePage> + <DataTable columns rows /> + useColumnVisibility + <ColumnToggle />"
      >
        <DataTableDemo />
      </Section>

      <Section title="Table" code="<Table><TableHeader/><TableBody/></Table> + <Pagination />">
        <Card className="overflow-hidden">
          <Table>
            <TableHeader>
              <tr>
                <TableHead>Name</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Amount</TableHead>
              </tr>
            </TableHeader>
            <TableBody>
              {[
                ["Invoice #1042", "success", "Paid", "$420.00"],
                ["Invoice #1043", "warning", "Pending", "$1,280.00"],
                ["Invoice #1044", "danger", "Overdue", "$96.50"],
              ].map(([name, tone, label, amount]) => (
                <TableRow key={name}>
                  <TableCell className="font-medium text-[#ddd]">{name}</TableCell>
                  <TableCell>
                    <Badge tone={tone as "success"}>{label}</Badge>
                  </TableCell>
                  <TableCell className="text-right tabular-nums">{amount}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <Pagination page={page} pageSize={3} total={14} onPageChange={setPage} />
        </Card>
      </Section>

      <div className="grid gap-5 xl:grid-cols-2">
        <Section title="Card anatomy" code="<Card><CardHeader/><CardContent/><CardFooter/></Card>">
          <Card>
            <CardHeader>
              <CardTitle>Card title</CardTitle>
              <CardDescription>Card description text.</CardDescription>
            </CardHeader>
            <CardContent>
              <DescriptionList
                items={[
                  { label: "Owner", value: "Ada Lovelace" },
                  { label: "Created", value: "05/11/2026" },
                ]}
              />
            </CardContent>
            <CardFooter className="justify-end gap-2">
              <Button>Cancel</Button>
              <Button variant="primary">Save</Button>
            </CardFooter>
          </Card>
        </Section>

        <Section title="States" code="<EmptyState/> <ErrorState/> <LoadingState/> <SuccessState/>">
          <div className="space-y-3">
            <EmptyState
              icon={<Inbox size={22} />}
              title="No items yet"
              description="Create your first item to get started."
              action={<Button variant="primary">Create item</Button>}
            />
            <LoadingState label="Loading data…" />
            <ErrorState description="The request failed." onRetry={() => toast.toast({ title: "Retrying…" })} />
            <SuccessState title="All done" description="Your changes were saved." />
          </div>
        </Section>
      </div>
    </div>
  );
}
