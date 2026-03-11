import { useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowRight,
  CheckCircle2,
  CloudDownload,
  Loader2,
  RadioTower,
  RefreshCw,
  ShieldAlert,
  Zap
} from "lucide-react";

import type { ConnectRegion, DescribeInstance, InstanceSummary } from "../types/connect";
import {
  describeInstance,
  getRegions,
  listInstances,
  replicate,
  replicationStatus,
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

export default function ConnectReplicatorPage() {
  const [regions, setRegions] = useState<ConnectRegion[]>([]);
  const [sourceRegion, setSourceRegion] = useState<string>("us-east-1");
  const [instances, setInstances] = useState<InstanceSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string>("");
  const [selected, setSelected] = useState<DescribeInstance | undefined>(undefined);

  const [replicaRegion, setReplicaRegion] = useState<string>("us-west-2");
  const [replicaAlias, setReplicaAlias] = useState<string>("");

  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [log, setLog] = useState<string[]>([]);

  const pollRef = useRef<number | null>(null);

  const sourceOk = selected?.InstanceStatus === "ACTIVE" && selected?.IdentityManagementType === "SAML";

  const selectedName = selected?.InstanceAlias || selectedId || "";

  const replicaFilename = useMemo(() => {
    const safe = (selectedName || "connect-instance").replace(/[^a-zA-Z0-9-_]+/g, "-");
    return `${safe}-${sourceRegion}.snapshot.json`;
  }, [selectedName, sourceRegion]);

  async function refreshInstances() {
    setError(null);
    setBusy("Loading instances...");
    try {
      const list = await listInstances(sourceRegion);
      setInstances(list);
      if (!list.find((i) => i.Id === selectedId)) {
        setSelectedId("");
        setSelected(undefined);
      }
    } catch (e: any) {
      setError(e?.message || String(e));
    } finally {
      setBusy(null);
    }
  }

  async function refreshSelected() {
    if (!selectedId) return;
    setError(null);
    setBusy("Loading instance details...");
    try {
      const inst = await describeInstance(sourceRegion, selectedId);
      setSelected(inst);
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
    refreshInstances();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sourceRegion]);

  useEffect(() => {
    refreshSelected();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId]);

  useEffect(() => {
    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current);
    };
  }, []);

  async function doSnapshot() {
    if (!selectedId) return;
    setError(null);
    setBusy("Capturing snapshot...");
    try {
      const snap = await snapshot(sourceRegion, selectedId);
      downloadJson(replicaFilename, snap);
      setLog((l) => [`Snapshot downloaded: ${replicaFilename}`, ...l]);
    } catch (e: any) {
      setError(e?.message || String(e));
    } finally {
      setBusy(null);
    }
  }

  async function doReplicate() {
    if (!selectedId) return;
    if (!replicaAlias.trim()) {
      setError("Replica alias is required.");
      return;
    }

    setError(null);
    setBusy("Starting replication...");
    setLog((l) => [`ReplicateInstance: ${sourceRegion} -> ${replicaRegion}`, ...l]);

    try {
      await replicate({
        sourceRegion,
        instanceId: selectedId,
        replicaRegion,
        replicaAlias: replicaAlias.trim()
      });

      setLog((l) => [`Replication request accepted. Polling target region...`, ...l]);

      if (pollRef.current) window.clearInterval(pollRef.current);
      pollRef.current = window.setInterval(async () => {
        try {
          const out = await replicationStatus(replicaRegion, selectedId);
          const st = out.status || "UNKNOWN";
          setLog((l) => [`Replica status (${replicaRegion}): ${st}`, ...l].slice(0, 50));
          if (st === "ACTIVE") {
            window.clearInterval(pollRef.current!);
            pollRef.current = null;
            setBusy(null);
          }
        } catch (e: any) {
          setError(e?.message || String(e));
          window.clearInterval(pollRef.current!);
          pollRef.current = null;
          setBusy(null);
        }
      }, 5000);
    } catch (e: any) {
      setError(e?.message || String(e));
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
              Global Resiliency • ReplicateInstance
            </div>
            <h1 className="mt-4 text-3xl font-bold tracking-tight">Amazon Connect Replicator</h1>
            <p className="mt-2 max-w-2xl text-sm text-white/70">
              Pick a source instance, download a JSON snapshot, and trigger cross-region replication.
              AWS credentials are used server-side only.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={refreshInstances}
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
                <div className={`rounded-full px-3 py-1 text-xs ${pillTone(selected?.InstanceStatus)}`}>
                  {selected?.InstanceStatus || "—"}
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
                <label className="text-xs text-white/70">Instances</label>
                <div className="mt-2 max-h-[360px] overflow-auto rounded-xl ring-1 ring-white/10">
                  {instances.length === 0 ? (
                    <div className="p-4 text-sm text-white/60">No instances found in this region.</div>
                  ) : (
                    <ul className="divide-y divide-white/10">
                      {instances.map((i) => (
                        <li key={i.Id}>
                          <button
                            onClick={() => setSelectedId(i.Id || "")}
                            className={`w-full px-4 py-3 text-left transition hover:bg-white/5 ${
                              selectedId === i.Id ? "bg-white/10" : ""
                            }`}
                          >
                            <div className="flex items-center justify-between gap-3">
                              <div>
                                <div className="text-sm font-medium">
                                  {i.InstanceAlias || i.Id}
                                </div>
                                <div className="mt-1 text-xs text-white/60">{i.Arn}</div>
                              </div>
                              <div className={`shrink-0 rounded-full px-3 py-1 text-xs ${pillTone(i.InstanceStatus)}`}>
                                {i.InstanceStatus || "—"}
                              </div>
                            </div>
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>

              <div className="mt-4 flex flex-wrap gap-2">
                <button
                  onClick={doSnapshot}
                  disabled={!selectedId || !!busy}
                  className="inline-flex items-center gap-2 rounded-xl bg-emerald-500/15 px-4 py-2 text-sm text-emerald-100 ring-1 ring-emerald-500/30 transition hover:bg-emerald-500/20 disabled:opacity-40"
                >
                  <CloudDownload className="h-4 w-4" />
                  Snapshot
                </button>
                <button
                  onClick={refreshSelected}
                  disabled={!selectedId || !!busy}
                  className="inline-flex items-center gap-2 rounded-xl bg-white/10 px-4 py-2 text-sm ring-1 ring-white/10 transition hover:bg-white/15 disabled:opacity-40"
                >
                  <RefreshCw className="h-4 w-4" />
                  Details
                </button>
              </div>

              {selected && (
                <div className="mt-4 rounded-xl bg-black/20 p-4 ring-1 ring-white/10">
                  <div className="grid grid-cols-2 gap-3 text-xs">
                    <div>
                      <div className="text-white/60">Identity</div>
                      <div className="mt-1 font-medium">{selected.IdentityManagementType || "—"}</div>
                    </div>
                    <div>
                      <div className="text-white/60">Alias</div>
                      <div className="mt-1 font-medium">{selected.InstanceAlias || "—"}</div>
                    </div>
                    <div className="col-span-2">
                      <div className="text-white/60">ARN</div>
                      <div className="mt-1 break-all font-medium">{selected.Arn || "—"}</div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </section>

          <section className="lg:col-span-7">
            <div className="rounded-2xl bg-white/5 p-5 ring-1 ring-white/10">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold">Replicate</h2>
                <div className="inline-flex items-center gap-2 text-xs text-white/60">
                  <Zap className="h-4 w-4" />
                  Uses Connect ReplicateInstance
                </div>
              </div>

              <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
                <div>
                  <label className="text-xs text-white/70">Target region</label>
                  <select
                    value={replicaRegion}
                    onChange={(e) => setReplicaRegion(e.target.value)}
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
                  <label className="text-xs text-white/70">Replica alias</label>
                  <input
                    value={replicaAlias}
                    onChange={(e) => setReplicaAlias(e.target.value)}
                    placeholder="unique-replica-alias"
                    className="mt-1 w-full rounded-xl bg-black/30 px-3 py-2 text-sm ring-1 ring-white/10 outline-none focus:ring-2 focus:ring-white/20"
                  />
                </div>
              </div>

              <div className="mt-4 rounded-xl bg-black/20 p-4 ring-1 ring-white/10">
                <div className="flex items-start gap-3">
                  {sourceOk ? (
                    <CheckCircle2 className="mt-0.5 h-5 w-5 text-emerald-300" />
                  ) : (
                    <ShieldAlert className="mt-0.5 h-5 w-5 text-amber-300" />
                  )}
                  <div className="text-sm">
                    <div className="font-medium">Preflight</div>
                    <div className="mt-1 text-white/70">
                      Source must be <span className="font-medium">ACTIVE</span> and Identity must be <span className="font-medium">SAML</span>.
                    </div>
                    {selected && !sourceOk && (
                      <div className="mt-2 text-xs text-amber-100/80">
                        Current: status={selected.InstanceStatus || "—"}, identity={selected.IdentityManagementType || "—"}
                      </div>
                    )}
                  </div>
                </div>
              </div>

              <div className="mt-4 flex flex-wrap items-center gap-2">
                <button
                  onClick={doReplicate}
                  disabled={!selectedId || !!busy}
                  className="inline-flex items-center gap-2 rounded-xl bg-cyan-500/15 px-4 py-2 text-sm text-cyan-100 ring-1 ring-cyan-500/30 transition hover:bg-cyan-500/20 disabled:opacity-40"
                >
                  <ArrowRight className="h-4 w-4" />
                  Replicate
                </button>

                {busy && (
                  <div className="inline-flex items-center gap-2 text-sm text-white/70">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    {busy}
                  </div>
                )}
              </div>

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
