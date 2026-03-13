import { useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowRight,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  CloudDownload,
  FileJson2,
  Layers,
  Loader2,
  RadioTower,
  RefreshCw,
  ShieldAlert,
  Square,
  SquareCheck,
  Upload
} from "lucide-react";

import type { ConnectRegion, DescribeInstance, ExportBundleV1, InstanceSummary, ResourceType } from "../types/connect";
import { RESOURCE_TYPES } from "../types/connect";
import {
  describeInstance,
  exportBundle,
  getRegions,
  importBundle,
  listInstances,
  snapshot
} from "../services/api";

function pillTone(status?: string) {
  if (!status) return "bg-white/10 text-white/70";
  if (status === "ACTIVE") return "bg-emerald-500/15 text-emerald-200 ring-1 ring-emerald-500/30";
  if (status.includes("FAIL")) return "bg-rose-500/15 text-rose-200 ring-1 ring-rose-500/30";
  return "bg-amber-500/15 text-amber-100 ring-1 ring-amber-500/30";
}

function downloadJson(filename: string, obj: unknown) {
  const blob = new Blob([JSON.stringify(obj, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

async function readJsonFile(file: File): Promise<any> {
  const text = await file.text();
  return JSON.parse(text);
}

function ResourceSelector({
  bundle,
  selectedResources,
  setSelectedResources,
}: {
  bundle: ExportBundleV1 | null;
  selectedResources: Set<ResourceType>;
  setSelectedResources: (s: Set<ResourceType>) => void;
}) {
  const [expanded, setExpanded] = useState(true);

  const getCount = (key: ResourceType): number => {
    if (!bundle) return 0;
    const arr = bundle[key];
    return Array.isArray(arr) ? arr.length : 0;
  };

  const availableResources = RESOURCE_TYPES.filter(r => getCount(r.key) > 0);
  const unavailableResources = RESOURCE_TYPES.filter(r => getCount(r.key) === 0);

  const allSelected = availableResources.every(r => selectedResources.has(r.key));
  const noneSelected = availableResources.every(r => !selectedResources.has(r.key));

  const toggleResource = (key: ResourceType) => {
    const next = new Set(selectedResources);
    if (next.has(key)) {
      next.delete(key);
    } else {
      next.add(key);
    }
    setSelectedResources(next);
  };

  const selectAll = () => {
    setSelectedResources(new Set(availableResources.map(r => r.key)));
  };

  const selectNone = () => {
    setSelectedResources(new Set());
  };

  if (!bundle) {
    return (
      <div className="rounded-xl bg-black/20 p-4 text-sm text-white/50 ring-1 ring-white/10">
        <div className="flex items-center gap-2">
          <Layers className="h-4 w-4" />
          Load a bundle to select resources
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-xl bg-black/20 ring-1 ring-white/10 overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium hover:bg-white/5 transition"
      >
        <div className="flex items-center gap-2">
          <Layers className="h-4 w-4 text-cyan-300" />
          <span>Resources to Replicate</span>
          <span className="ml-2 rounded-full bg-cyan-500/20 px-2 py-0.5 text-xs text-cyan-200">
            {selectedResources.size} of {availableResources.length} selected
          </span>
        </div>
        {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
      </button>

      {expanded && (
        <div className="border-t border-white/10 p-4">
          {/* Quick actions */}
          <div className="flex items-center gap-3 mb-4">
            <button
              onClick={selectAll}
              disabled={allSelected}
              className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-500/15 px-3 py-1.5 text-xs text-emerald-200 ring-1 ring-emerald-500/30 transition hover:bg-emerald-500/25 disabled:opacity-40"
            >
              <SquareCheck className="h-3.5 w-3.5" />
              Select All
            </button>
            <button
              onClick={selectNone}
              disabled={noneSelected}
              className="inline-flex items-center gap-1.5 rounded-lg bg-white/10 px-3 py-1.5 text-xs ring-1 ring-white/10 transition hover:bg-white/15 disabled:opacity-40"
            >
              <Square className="h-3.5 w-3.5" />
              Select None
            </button>
          </div>

          {/* Available resources grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
            {availableResources.map((r) => {
              const count = getCount(r.key);
              const isSelected = selectedResources.has(r.key);
              return (
                <button
                  key={r.key}
                  onClick={() => toggleResource(r.key)}
                  className={`group relative flex items-start gap-3 rounded-xl p-3 text-left transition ring-1 ${
                    isSelected
                      ? "bg-cyan-500/15 ring-cyan-500/40 text-cyan-50"
                      : "bg-white/5 ring-white/10 hover:bg-white/10 text-white/80"
                  }`}
                >
                  <div className={`mt-0.5 flex-shrink-0 rounded-md p-1 ${
                    isSelected ? "bg-cyan-500/30" : "bg-white/10"
                  }`}>
                    {isSelected ? (
                      <Check className="h-3.5 w-3.5 text-cyan-200" />
                    ) : (
                      <Square className="h-3.5 w-3.5 text-white/50" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium truncate">{r.label}</span>
                      <span className={`rounded-full px-1.5 py-0.5 text-[10px] font-semibold ${
                        isSelected ? "bg-cyan-500/30 text-cyan-100" : "bg-white/10 text-white/60"
                      }`}>
                        {count}
                      </span>
                    </div>
                    <div className="text-xs text-white/50 mt-0.5 truncate">{r.description}</div>
                  </div>
                </button>
              );
            })}
          </div>

          {/* Unavailable resources (collapsed) */}
          {unavailableResources.length > 0 && (
            <div className="mt-4 pt-4 border-t border-white/10">
              <div className="text-xs text-white/40 mb-2">
                Not in bundle ({unavailableResources.length}):
              </div>
              <div className="flex flex-wrap gap-1.5">
                {unavailableResources.map(r => (
                  <span
                    key={r.key}
                    className="inline-flex items-center rounded-full bg-white/5 px-2 py-0.5 text-[10px] text-white/40 ring-1 ring-white/10"
                  >
                    {r.label}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function ConnectReplicatorPage() {
  const [regions, setRegions] = useState<ConnectRegion[]>([]);

  const [sourceRegion, setSourceRegion] = useState<string>("us-east-1");
  const [sourceInstances, setSourceInstances] = useState<InstanceSummary[]>([]);
  const [sourceId, setSourceId] = useState<string>("");
  const [source, setSource] = useState<DescribeInstance | undefined>(undefined);

  const [targetRegion, setTargetRegion] = useState<string>("us-west-2");
  const [targetInstances, setTargetInstances] = useState<InstanceSummary[]>([]);
  const [targetId, setTargetId] = useState<string>("");
  const [target, setTarget] = useState<DescribeInstance | undefined>(undefined);

  const [bundle, setBundle] = useState<ExportBundleV1 | null>(null);
  const [bundleName, setBundleName] = useState<string>("");
  const [overwrite, setOverwrite] = useState<boolean>(true);
  const [selectedResources, setSelectedResources] = useState<Set<ResourceType>>(new Set());

  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [log, setLog] = useState<string[]>([]);

  const fileRef = useRef<HTMLInputElement | null>(null);

  const sourceOk = source?.InstanceStatus === "ACTIVE";
  const targetOk = target?.InstanceStatus === "ACTIVE";

  const exportFilename = useMemo(() => {
    const safe = (source?.InstanceAlias || sourceId || "connect-instance").replace(/[^a-zA-Z0-9-_]+/g, "-");
    return `${safe}-${sourceRegion}.connect-export.v3.json`;
  }, [source?.InstanceAlias, sourceId, sourceRegion]);

  // Auto-select all available resources when bundle changes
  useEffect(() => {
    if (bundle) {
      const available = RESOURCE_TYPES.filter(r => {
        const arr = bundle[r.key];
        return Array.isArray(arr) && arr.length > 0;
      }).map(r => r.key);
      setSelectedResources(new Set(available));
    } else {
      setSelectedResources(new Set());
    }
  }, [bundle]);

  async function refreshSourceInstances() {
    setError(null);
    setBusy("Loading source instances...");
    try {
      const list = await listInstances(sourceRegion);
      setSourceInstances(list);
      if (!list.find((i) => i.Id === sourceId)) {
        setSourceId("");
        setSource(undefined);
      }
    } catch (e: any) {
      setError(e?.message || String(e));
    } finally {
      setBusy(null);
    }
  }

  async function refreshTargetInstances() {
    setError(null);
    setBusy("Loading target instances...");
    try {
      const list = await listInstances(targetRegion);
      setTargetInstances(list);
      if (!list.find((i) => i.Id === targetId)) {
        setTargetId("");
        setTarget(undefined);
      }
    } catch (e: any) {
      setError(e?.message || String(e));
    } finally {
      setBusy(null);
    }
  }

  async function refreshSourceDetails() {
    if (!sourceId) return;
    setError(null);
    setBusy("Loading source instance details...");
    try {
      setSource(await describeInstance(sourceRegion, sourceId));
    } catch (e: any) {
      setError(e?.message || String(e));
    } finally {
      setBusy(null);
    }
  }

  async function refreshTargetDetails() {
    if (!targetId) return;
    setError(null);
    setBusy("Loading target instance details...");
    try {
      setTarget(await describeInstance(targetRegion, targetId));
    } catch (e: any) {
      setError(e?.message || String(e));
    } finally {
      setBusy(null);
    }
  }

  useEffect(() => {
    getRegions()
      .then(setRegions)
      .catch((e) => setError(e?.message || String(e)));
  }, []);

  useEffect(() => {
    refreshSourceInstances();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sourceRegion]);

  useEffect(() => {
    refreshTargetInstances();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [targetRegion]);

  useEffect(() => {
    refreshSourceDetails();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sourceId]);

  useEffect(() => {
    refreshTargetDetails();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [targetId]);

  async function doExport() {
    if (!sourceId) return;
    setError(null);
    setBusy("Exporting configuration bundle...");
    try {
      const b = await exportBundle(sourceRegion, sourceId);
      setBundle(b);
      setBundleName(exportFilename);
      downloadJson(exportFilename, b);
      
      const counts = RESOURCE_TYPES
        .map(r => ({ key: r.key, count: Array.isArray(b[r.key]) ? b[r.key]!.length : 0 }))
        .filter(x => x.count > 0)
        .map(x => `${x.key}=${x.count}`)
        .join(", ");
      setLog((l) => [`Exported bundle (v${b.version}): ${counts}`, ...l]);
    } catch (e: any) {
      setError(e?.message || String(e));
    } finally {
      setBusy(null);
    }
  }

  async function doImport() {
    if (!targetId) return;
    if (!bundle) {
      setError("No bundle loaded. Export one or choose a JSON bundle file.");
      return;
    }
    if (selectedResources.size === 0) {
      setError("No resources selected. Select at least one resource type to import.");
      return;
    }

    setError(null);
    const resourceList = Array.from(selectedResources);
    setBusy(`Importing ${resourceList.length} resource types...`);
    try {
      const out = await importBundle({
        region: targetRegion,
        instanceId: targetId,
        bundle,
        overwrite,
        selectedResources: resourceList
      });
      
      const summary = Object.entries(out)
        .filter(([k, v]) => typeof v === "number" && v > 0 && !k.startsWith("failed"))
        .map(([k, v]) => `${k}=${v}`)
        .join(", ");
      setLog((l) => [`Import finished (${resourceList.length} types): ${summary || "no changes"}`, ...l]);
      
      // Log any errors
      if (out.errors && Object.keys(out.errors).length > 0) {
        setLog((l) => [`⚠️ Import had errors: ${JSON.stringify(out.errors)}`, ...l]);
      }
    } catch (e: any) {
      setError(e?.message || String(e));
    } finally {
      setBusy(null);
    }
  }

  async function doInstanceSnapshot(region: string, instanceId: string, filename: string) {
    setError(null);
    setBusy("Capturing instance snapshot...");
    try {
      const snap = await snapshot(region, instanceId);
      downloadJson(filename, snap);
      setLog((l) => [`Instance snapshot downloaded: ${filename}`, ...l]);
    } catch (e: any) {
      setError(e?.message || String(e));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="relative min-h-screen noise">
      <div className="mx-auto max-w-7xl px-6 py-10">
        <header className="flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1 text-xs text-white/80 ring-1 ring-white/10">
              <RadioTower className="h-4 w-4" />
              Primitive Connect APIs • v3 Bundle (17 Resource Types)
            </div>
            <h1 className="mt-4 text-3xl font-bold tracking-tight">Amazon Connect Replicator</h1>
            <p className="mt-2 max-w-2xl text-sm text-white/70">
              Best-effort migration using Connect List/Describe/Create/Update APIs. Select which resources to sync from source to target.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={() => {
                refreshSourceInstances();
                refreshTargetInstances();
              }}
              className="inline-flex items-center gap-2 rounded-xl bg-white/10 px-4 py-2 text-sm ring-1 ring-white/10 transition hover:bg-white/15"
            >
              <RefreshCw className="h-4 w-4" />
              Refresh
            </button>
          </div>
        </header>

        <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-12">
          {/* Source Panel */}
          <section className="lg:col-span-5">
            <div className="rounded-2xl bg-white/5 p-5 ring-1 ring-white/10">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold">Source Instance</h2>
                <div className={`rounded-full px-3 py-1 text-xs ${pillTone(source?.InstanceStatus)}`}>
                  {source?.InstanceStatus || "—"}
                </div>
              </div>

              <div className="mt-4">
                <label className="text-xs text-white/70">Region</label>
                <select
                  value={sourceRegion}
                  onChange={(e) => setSourceRegion(e.target.value)}
                  className="mt-1 w-full rounded-xl bg-black/30 px-3 py-2 text-sm ring-1 ring-white/10 outline-none focus:ring-2 focus:ring-white/20"
                >
                  {regions.map((r) => (
                    <option key={r.code} value={r.code}>
                      {r.label} ({r.code})
                    </option>
                  ))}
                </select>
              </div>

              <div className="mt-4">
                <label className="text-xs text-white/70">Instance</label>
                <select
                  value={sourceId}
                  onChange={(e) => setSourceId(e.target.value)}
                  className="mt-1 w-full rounded-xl bg-black/30 px-3 py-2 text-sm ring-1 ring-white/10 outline-none focus:ring-2 focus:ring-white/20"
                >
                  <option value="">Select…</option>
                  {sourceInstances.map((i) => (
                    <option key={i.Id} value={i.Id}>
                      {(i.InstanceAlias || i.Id) ?? ""}
                    </option>
                  ))}
                </select>
              </div>

              <div className="mt-4 flex flex-wrap gap-2">
                <button
                  onClick={doExport}
                  disabled={!sourceId || !!busy}
                  className="inline-flex items-center gap-2 rounded-xl bg-emerald-500/15 px-4 py-2 text-sm text-emerald-100 ring-1 ring-emerald-500/30 transition hover:bg-emerald-500/20 disabled:opacity-40"
                >
                  <CloudDownload className="h-4 w-4" />
                  Export Bundle
                </button>

                <button
                  onClick={() => {
                    if (!sourceId) return;
                    const safe = (source?.InstanceAlias || sourceId || "connect-instance").replace(/[^a-zA-Z0-9-_]+/g, "-");
                    void doInstanceSnapshot(sourceRegion, sourceId, `${safe}-${sourceRegion}.instance.json`);
                  }}
                  disabled={!sourceId || !!busy}
                  className="inline-flex items-center gap-2 rounded-xl bg-white/10 px-4 py-2 text-sm ring-1 ring-white/10 transition hover:bg-white/15 disabled:opacity-40"
                >
                  <FileJson2 className="h-4 w-4" />
                  Instance JSON
                </button>
              </div>

              {!sourceOk && source && (
                <div className="mt-4 rounded-xl bg-amber-500/10 p-4 text-sm text-amber-100 ring-1 ring-amber-500/20">
                  <div className="flex items-start gap-3">
                    <ShieldAlert className="mt-0.5 h-5 w-5" />
                    <div>
                      Source instance is not ACTIVE; exports can still work but you may hit API errors.
                    </div>
                  </div>
                </div>
              )}
            </div>
          </section>

          {/* Target Panel */}
          <section className="lg:col-span-7">
            <div className="rounded-2xl bg-white/5 p-5 ring-1 ring-white/10">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold">Target Instance</h2>
                <div className={`rounded-full px-3 py-1 text-xs ${pillTone(target?.InstanceStatus)}`}>
                  {target?.InstanceStatus || "—"}
                </div>
              </div>

              <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
                <div>
                  <label className="text-xs text-white/70">Region</label>
                  <select
                    value={targetRegion}
                    onChange={(e) => setTargetRegion(e.target.value)}
                    className="mt-1 w-full rounded-xl bg-black/30 px-3 py-2 text-sm ring-1 ring-white/10 outline-none focus:ring-2 focus:ring-white/20"
                  >
                    {regions.map((r) => (
                      <option key={r.code} value={r.code}>
                        {r.label} ({r.code})
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="text-xs text-white/70">Instance</label>
                  <select
                    value={targetId}
                    onChange={(e) => setTargetId(e.target.value)}
                    className="mt-1 w-full rounded-xl bg-black/30 px-3 py-2 text-sm ring-1 ring-white/10 outline-none focus:ring-2 focus:ring-white/20"
                  >
                    <option value="">Select…</option>
                    {targetInstances.map((i) => (
                      <option key={i.Id} value={i.Id}>
                        {(i.InstanceAlias || i.Id) ?? ""}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Bundle load section */}
              <div className="mt-4 rounded-xl bg-black/20 p-4 ring-1 ring-white/10">
                <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                  <div className="text-sm">
                    <div className="font-medium">Bundle</div>
                    <div className="mt-1 text-xs text-white/60">
                      {bundle ? (
                        <span>
                          Loaded <span className="font-medium text-white/80">{bundleName || "bundle"}</span>
                          <span className="ml-2 rounded-full bg-emerald-500/20 px-2 py-0.5 text-emerald-200">
                            v{bundle.version}
                          </span>
                        </span>
                      ) : (
                        <span>No bundle loaded yet.</span>
                      )}
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    <input
                      ref={fileRef}
                      type="file"
                      accept="application/json"
                      className="hidden"
                      onChange={async (e) => {
                        const f = e.target.files?.[0];
                        if (!f) return;
                        setError(null);
                        setBusy("Loading bundle file...");
                        try {
                          const parsed = (await readJsonFile(f)) as ExportBundleV1;
                          if (![1, 2, 3].includes(parsed?.version)) throw new Error("Unsupported bundle version");
                          setBundle(parsed);
                          setBundleName(f.name);
                          setLog((l) => [`Loaded bundle file: ${f.name} (v${parsed.version})`, ...l]);
                        } catch (err: any) {
                          setError(err?.message || String(err));
                        } finally {
                          setBusy(null);
                          e.target.value = "";
                        }
                      }}
                    />

                    <button
                      onClick={() => fileRef.current?.click()}
                      disabled={!!busy}
                      className="inline-flex items-center gap-2 rounded-xl bg-white/10 px-4 py-2 text-sm ring-1 ring-white/10 transition hover:bg-white/15 disabled:opacity-40"
                    >
                      <Upload className="h-4 w-4" />
                      Choose file
                    </button>
                  </div>
                </div>
              </div>

              {/* Resource selector */}
              <div className="mt-4">
                <ResourceSelector
                  bundle={bundle}
                  selectedResources={selectedResources}
                  setSelectedResources={setSelectedResources}
                />
              </div>

              {/* Import controls */}
              <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex items-center gap-4 text-xs text-white/70">
                  <label className="inline-flex select-none items-center gap-2">
                    <input
                      type="checkbox"
                      checked={overwrite}
                      onChange={(e) => setOverwrite(e.target.checked)}
                      className="h-4 w-4 rounded border-white/20 bg-black/30"
                    />
                    Overwrite existing (update if exists)
                  </label>

                  <div className="inline-flex items-center gap-2">
                    {targetOk ? (
                      <>
                        <CheckCircle2 className="h-4 w-4 text-emerald-300" />
                        <span>Target ACTIVE</span>
                      </>
                    ) : (
                      <>
                        <ShieldAlert className="h-4 w-4 text-amber-300" />
                        <span>Target not ACTIVE</span>
                      </>
                    )}
                  </div>
                </div>

                <button
                  onClick={doImport}
                  disabled={!targetId || !!busy || !bundle || selectedResources.size === 0}
                  className="inline-flex items-center justify-center gap-2 rounded-xl bg-cyan-500/20 px-6 py-2.5 text-sm font-medium text-cyan-100 ring-1 ring-cyan-500/40 transition hover:bg-cyan-500/30 disabled:opacity-40"
                >
                  <ArrowRight className="h-4 w-4" />
                  Import {selectedResources.size > 0 ? `(${selectedResources.size} types)` : ""}
                </button>
              </div>

              {busy && (
                <div className="mt-4 inline-flex items-center gap-2 text-sm text-white/70">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  {busy}
                </div>
              )}

              {error && (
                <div className="mt-4 rounded-xl bg-rose-500/10 p-4 text-sm text-rose-100 ring-1 ring-rose-500/20">
                  {error}
                </div>
              )}

              <div className="mt-6">
                <div className="text-xs font-semibold text-white/70">Activity Log</div>
                <div className="mt-2 max-h-[200px] overflow-auto rounded-xl bg-black/30 p-3 text-xs text-white/70 ring-1 ring-white/10 font-mono">
                  {log.length === 0 ? (
                    <div className="text-white/50">No activity yet.</div>
                  ) : (
                    <ul className="space-y-1">
                      {log.map((l, idx) => (
                        <li key={idx}>{l}</li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
