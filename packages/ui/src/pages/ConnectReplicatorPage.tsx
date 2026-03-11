import { useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowRight,
  CheckCircle2,
  CloudDownload,
  FileJson2,
  Loader2,
  RadioTower,
  RefreshCw,
  ShieldAlert,
  Upload
} from "lucide-react";

import type { ConnectRegion, DescribeInstance, ExportBundleV1, InstanceSummary } from "../types/connect";
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
  const [overwrite, setOverwrite] = useState<boolean>(false);

  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [log, setLog] = useState<string[]>([]);

  const fileRef = useRef<HTMLInputElement | null>(null);

  const sourceOk = source?.InstanceStatus === "ACTIVE";
  const targetOk = target?.InstanceStatus === "ACTIVE";

  const exportFilename = useMemo(() => {
    const safe = (source?.InstanceAlias || sourceId || "connect-instance").replace(/[^a-zA-Z0-9-_]+/g, "-");
    return `${safe}-${sourceRegion}.connect-export.v1.json`;
  }, [source?.InstanceAlias, sourceId, sourceRegion]);

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
    setBusy("Exporting contact flows + modules...");
    try {
      const b = await exportBundle(sourceRegion, sourceId);
      setBundle(b);
      setBundleName(exportFilename);
      downloadJson(exportFilename, b);
      setLog((l) => [`Exported bundle: modules=${b.flowModules.length}, flows=${b.contactFlows.length}`, ...l]);
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

    setError(null);
    setBusy("Importing bundle into target instance...");
    try {
      const out = await importBundle({
        region: targetRegion,
        instanceId: targetId,
        bundle,
        overwrite
      });
      setLog((l) => [`Import finished: ${JSON.stringify(out)}`, ...l]);
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
      <div className="mx-auto max-w-6xl px-6 py-10">
        <header className="flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1 text-xs text-white/80 ring-1 ring-white/10">
              <RadioTower className="h-4 w-4" />
              Primitive Connect APIs • Export/Import
            </div>
            <h1 className="mt-4 text-3xl font-bold tracking-tight">Amazon Connect Replicator</h1>
            <p className="mt-2 max-w-2xl text-sm text-white/70">
              Best-effort migration using Connect List/Describe/Create/Update APIs. This does not create a new instance;
              it copies resources between existing instances.
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
          <section className="lg:col-span-5">
            <div className="rounded-2xl bg-white/5 p-5 ring-1 ring-white/10">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold">Source</h2>
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
                  Export bundle
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

              <div className="mt-4 rounded-xl bg-black/20 p-4 text-xs text-white/70 ring-1 ring-white/10">
                <div className="font-semibold text-white/80">What’s included (v1)</div>
                <div className="mt-2">• Contact Flow Modules (describe + content)</div>
                <div>• Contact Flows (describe + content)</div>
                <div className="mt-3 text-white/60">
                  Notes: prompts/queues/routing profiles/etc are not copied yet. Flow JSON may reference resources by ID/ARN.
                </div>
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

          <section className="lg:col-span-7">
            <div className="rounded-2xl bg-white/5 p-5 ring-1 ring-white/10">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold">Target</h2>
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

              <div className="mt-4 rounded-xl bg-black/20 p-4 ring-1 ring-white/10">
                <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                  <div className="text-sm">
                    <div className="font-medium">Bundle</div>
                    <div className="mt-1 text-xs text-white/60">
                      {bundle ? (
                        <span>
                          Loaded <span className="font-medium text-white/80">{bundleName || "bundle"}</span> • modules={bundle.flowModules.length} • flows={bundle.contactFlows.length}
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
                          if (parsed?.version !== 1) throw new Error("Unsupported bundle version");
                          setBundle(parsed);
                          setBundleName(f.name);
                          setLog((l) => [`Loaded bundle file: ${f.name}`, ...l]);
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

                    <button
                      onClick={doImport}
                      disabled={!targetId || !!busy || !bundle}
                      className="inline-flex items-center gap-2 rounded-xl bg-cyan-500/15 px-4 py-2 text-sm text-cyan-100 ring-1 ring-cyan-500/30 transition hover:bg-cyan-500/20 disabled:opacity-40"
                    >
                      <ArrowRight className="h-4 w-4" />
                      Import
                    </button>
                  </div>
                </div>

                <div className="mt-3 flex items-center gap-3 text-xs text-white/70">
                  <label className="inline-flex select-none items-center gap-2">
                    <input
                      type="checkbox"
                      checked={overwrite}
                      onChange={(e) => setOverwrite(e.target.checked)}
                      className="h-4 w-4 rounded border-white/20 bg-black/30"
                    />
                    Overwrite existing flows/modules (by name)
                  </label>

                  <div className="ml-auto inline-flex items-center gap-2">
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

                <div className="mt-3 text-xs text-white/60">
                  Import is best-effort: flow JSON may still reference prompts/queues/routing profiles not present in the target.
                </div>
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
                <div className="text-xs font-semibold text-white/70">Activity</div>
                <div className="mt-2 max-h-[240px] overflow-auto rounded-xl bg-black/30 p-3 text-xs text-white/70 ring-1 ring-white/10">
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
