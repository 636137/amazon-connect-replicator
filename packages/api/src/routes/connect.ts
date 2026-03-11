import {
  ConnectClient,
  CreateContactFlowCommand,
  CreateContactFlowModuleCommand,
  CreateHoursOfOperationCommand,
  CreateQueueCommand,
  DescribeContactFlowCommand,
  DescribeContactFlowModuleCommand,
  DescribeHoursOfOperationCommand,
  DescribeInstanceCommand,
  DescribeQueueCommand,
  ListContactFlowModulesCommand,
  ListContactFlowModulesCommandOutput,
  ListContactFlowsCommand,
  ListContactFlowsCommandOutput,
  ListHoursOfOperationsCommand,
  ListHoursOfOperationsCommandOutput,
  ListInstancesCommand,
  ListQueuesCommand,
  ListQueuesCommandOutput,
  UpdateContactFlowContentCommand,
  UpdateContactFlowModuleContentCommand,
  UpdateHoursOfOperationCommand,
  UpdateQueueHoursOfOperationCommand,
  UpdateQueueMaxContactsCommand,
  UpdateQueueOutboundCallerConfigCommand,
  UpdateQueueStatusCommand
} from "@aws-sdk/client-connect";
import { Router } from "express";
import { z } from "zod";

import { CONNECT_REGIONS } from "../services/connectRegions.js";

function clientFor(region: string) {
  return new ConnectClient({ region });
}

const CONTACT_FLOW_TYPES = [
  "CONTACT_FLOW",
  "CUSTOMER_QUEUE",
  "CUSTOMER_HOLD",
  "CUSTOMER_WHISPER",
  "AGENT_HOLD",
  "AGENT_WHISPER",
  "OUTBOUND_WHISPER",
  "AGENT_TRANSFER",
  "QUEUE_TRANSFER",
  "CAMPAIGN"
] as const;

type ExportedFlowModule = {
  id?: string;
  arn?: string;
  name: string;
  description?: string;
  state?: string;
  status?: string;
  content?: string;
  settings?: string;
  tags?: Record<string, string>;
};

type ExportedContactFlow = {
  id?: string;
  arn?: string;
  name: string;
  type: string;
  description?: string;
  state?: string;
  status?: string;
  content?: string;
  tags?: Record<string, string>;
};

type ExportedHoursOfOperation = {
  id?: string;
  arn?: string;
  name: string;
  description?: string;
  timeZone?: string;
  config?: any;
  tags?: Record<string, string>;
};

type ExportedQueue = {
  id?: string;
  arn?: string;
  name: string;
  description?: string;
  status?: string;
  maxContacts?: number;
  hoursOfOperationId?: string;
  hoursOfOperationName?: string;
  outboundCallerConfig?: any;
  tags?: Record<string, string>;
};

type ExportBundleV1 = {
  version: 1;
  exportedAt: string;
  source: { region: string; instanceId: string };
  hoursOfOperations?: ExportedHoursOfOperation[];
  queues?: ExportedQueue[];
  flowModules: ExportedFlowModule[];
  contactFlows: ExportedContactFlow[];
};

function applyReplacements(content: string, replacements: Array<[string, string]>): string {
  let out = content;
  const sorted = [...replacements].sort((a, b) => (b?.[0]?.length || 0) - (a?.[0]?.length || 0));
  for (const [from, to] of sorted) {
    if (!from || from === to) continue;
    out = out.split(from).join(to);
  }
  return out;
}

function omitNil<T extends Record<string, any>>(obj: T): Partial<T> {
  return Object.fromEntries(Object.entries(obj).filter(([, v]) => v !== undefined && v !== null)) as Partial<T>;
}

async function listAllContactFlowModules(region: string, instanceId: string) {
  const c = clientFor(region);
  const out: Array<{ Id?: string; Arn?: string; Name?: string; State?: string }> = [];
  let nextToken: string | undefined = undefined;
  do {
    const page: ListContactFlowModulesCommandOutput = await c.send(
      new ListContactFlowModulesCommand({
        InstanceId: instanceId,
        MaxResults: 100,
        NextToken: nextToken
      })
    );
    out.push(...(page.ContactFlowModulesSummaryList || []));
    nextToken = page.NextToken;
  } while (nextToken);
  return out;
}

async function listAllContactFlows(region: string, instanceId: string) {
  const c = clientFor(region);
  const out: Array<{ Id?: string; Arn?: string; Name?: string; ContactFlowType?: string }> = [];
  let nextToken: string | undefined = undefined;
  do {
    const page: ListContactFlowsCommandOutput = await c.send(
      new ListContactFlowsCommand({
        InstanceId: instanceId,
        ContactFlowTypes: [...CONTACT_FLOW_TYPES],
        MaxResults: 100,
        NextToken: nextToken
      })
    );
    out.push(...(page.ContactFlowSummaryList || []));
    nextToken = page.NextToken;
  } while (nextToken);
  return out;
}

async function listAllHoursOfOperations(region: string, instanceId: string) {
  const c = clientFor(region);
  const out: Array<{ Id?: string; Arn?: string; Name?: string }> = [];
  let nextToken: string | undefined = undefined;
  do {
    const page: ListHoursOfOperationsCommandOutput = await c.send(
      new ListHoursOfOperationsCommand({
        InstanceId: instanceId,
        MaxResults: 100,
        NextToken: nextToken
      })
    );
    out.push(...(page.HoursOfOperationSummaryList || []));
    nextToken = page.NextToken;
  } while (nextToken);
  return out;
}

async function listAllQueues(region: string, instanceId: string) {
  const c = clientFor(region);
  const out: Array<{ Id?: string; Arn?: string; Name?: string; QueueType?: string }> = [];
  let nextToken: string | undefined = undefined;
  do {
    const page: ListQueuesCommandOutput = await c.send(
      new ListQueuesCommand({
        InstanceId: instanceId,
        MaxResults: 100,
        NextToken: nextToken
      })
    );
    out.push(...(page.QueueSummaryList || []));
    nextToken = page.NextToken;
  } while (nextToken);
  return out;
}

export const connectRouter = Router();

connectRouter.get("/regions", (_req, res) => {
  res.status(200).json({ regions: CONNECT_REGIONS });
});

connectRouter.get("/instances", async (req, res) => {
  const q = z.object({ region: z.string().min(1) }).safeParse(req.query);
  if (!q.success) return res.status(400).json({ error: "Missing or invalid region" });

  try {
    const c = clientFor(q.data.region);
    const out = await c.send(new ListInstancesCommand({ MaxResults: 100 }));
    return res.status(200).json({ instances: out.InstanceSummaryList || [] });
  } catch (e: any) {
    return res.status(500).json({ error: e?.message || String(e) });
  }
});

connectRouter.get("/instance", async (req, res) => {
  const q = z
    .object({ region: z.string().min(1), instanceId: z.string().min(1) })
    .safeParse(req.query);
  if (!q.success) return res.status(400).json({ error: "Missing region or instanceId" });

  try {
    const c = clientFor(q.data.region);
    const out = await c.send(new DescribeInstanceCommand({ InstanceId: q.data.instanceId }));
    return res.status(200).json({ instance: out.Instance });
  } catch (e: any) {
    return res.status(500).json({ error: e?.message || String(e) });
  }
});

connectRouter.post("/snapshot", async (req, res) => {
  const body = z.object({ region: z.string().min(1), instanceId: z.string().min(1) }).safeParse(req.body);
  if (!body.success) return res.status(400).json({ error: "Missing region or instanceId" });

  try {
    const c = clientFor(body.data.region);
    const out = await c.send(new DescribeInstanceCommand({ InstanceId: body.data.instanceId }));
    return res.status(200).json({
      capturedAt: new Date().toISOString(),
      region: body.data.region,
      instanceId: body.data.instanceId,
      instance: out.Instance
    });
  } catch (e: any) {
    return res.status(500).json({ error: e?.message || String(e) });
  }
});

connectRouter.post("/export", async (req, res) => {
  const body = z.object({ region: z.string().min(1), instanceId: z.string().min(1) }).safeParse(req.body);
  if (!body.success) return res.status(400).json({ error: "Missing region or instanceId" });

  const { region, instanceId } = body.data;

  try {
    const c = clientFor(region);

    const hours = await listAllHoursOfOperations(region, instanceId);
    const queues = await listAllQueues(region, instanceId);
    const modules = await listAllContactFlowModules(region, instanceId);
    const flows = await listAllContactFlows(region, instanceId);

    const hoursOfOperations: ExportedHoursOfOperation[] = [];
    for (const h of hours) {
      if (!h.Id || !h.Name) continue;
      const d = await c.send(new DescribeHoursOfOperationCommand({ InstanceId: instanceId, HoursOfOperationId: h.Id }));
      const ho = d.HoursOfOperation;
      if (!ho?.Name) continue;
      hoursOfOperations.push({
        id: (ho as any).HoursOfOperationId,
        arn: (ho as any).HoursOfOperationArn,
        name: ho.Name,
        description: ho.Description,
        timeZone: (ho as any).TimeZone,
        config: (ho as any).Config,
        tags: (ho as any).Tags
      });
    }

    const hoursById = new Map<string, string>();
    for (const h of hoursOfOperations) {
      if (h.id && h.name) hoursById.set(h.id, h.name);
    }

    const exportedQueues: ExportedQueue[] = [];
    for (const q of queues) {
      if (!q.Id || !q.Name) continue;
      const d = await c.send(new DescribeQueueCommand({ InstanceId: instanceId, QueueId: q.Id }));
      const qq = d.Queue as any;
      if (!qq?.Name) continue;
      const hoursName = qq.HoursOfOperationId ? hoursById.get(qq.HoursOfOperationId) : undefined;
      exportedQueues.push({
        id: qq.QueueId,
        arn: qq.QueueArn,
        name: qq.Name,
        description: qq.Description,
        status: qq.Status,
        maxContacts: qq.MaxContacts,
        hoursOfOperationId: qq.HoursOfOperationId,
        hoursOfOperationName: hoursName,
        outboundCallerConfig: qq.OutboundCallerConfig,
        tags: qq.Tags
      });
    }

    const flowModules: ExportedFlowModule[] = [];
    for (const m of modules) {
      if (!m.Id || !m.Name) continue;
      const d = await c.send(
        new DescribeContactFlowModuleCommand({ InstanceId: instanceId, ContactFlowModuleId: m.Id })
      );
      const mod = d.ContactFlowModule;
      if (!mod?.Name) continue;
      flowModules.push({
        id: mod.Id,
        arn: mod.Arn,
        name: mod.Name,
        description: mod.Description,
        state: mod.State,
        status: mod.Status,
        content: mod.Content,
        settings: mod.Settings,
        tags: mod.Tags
      });
    }

    const contactFlows: ExportedContactFlow[] = [];
    for (const f of flows) {
      if (!f.Id || !f.Name || !f.ContactFlowType) continue;
      const d = await c.send(
        new DescribeContactFlowCommand({ InstanceId: instanceId, ContactFlowId: f.Id })
      );
      const flow = d.ContactFlow;
      if (!flow?.Name || !flow?.Type) continue;
      contactFlows.push({
        id: flow.Id,
        arn: flow.Arn,
        name: flow.Name,
        type: flow.Type,
        description: flow.Description,
        state: flow.State,
        status: flow.Status,
        content: flow.Content,
        tags: flow.Tags
      });
    }

    const bundle: ExportBundleV1 = {
      version: 1,
      exportedAt: new Date().toISOString(),
      source: { region, instanceId },
      hoursOfOperations,
      queues: exportedQueues,
      flowModules,
      contactFlows
    };

    return res.status(200).json(bundle);
  } catch (e: any) {
    return res.status(500).json({ error: e?.message || String(e) });
  }
});

connectRouter.post("/import", async (req, res) => {
  const body = z
    .object({
      region: z.string().min(1),
      instanceId: z.string().min(1),
      overwrite: z.boolean().optional().default(false),
      dryRun: z.boolean().optional().default(false),
      bundle: z.any()
    })
    .safeParse(req.body);

  if (!body.success) return res.status(400).json({ error: "Missing required fields" });

  const { region, instanceId, overwrite, dryRun } = body.data;

  const bundle = body.data.bundle as ExportBundleV1;
  if (bundle?.version !== 1 || !Array.isArray(bundle.contactFlows) || !Array.isArray(bundle.flowModules)) {
    return res.status(400).json({ error: "Invalid bundle format" });
  }

  try {
    const c = clientFor(region);

    const hoursByName = new Map<string, { Id?: string; Arn?: string; Name?: string }>();
    const queueByName = new Map<string, { Id?: string; Arn?: string; Name?: string }>();

    // Build target lookup tables (hours + queues)
    const existingHours = await listAllHoursOfOperations(region, instanceId);
    for (const h of existingHours) {
      if (h.Name) hoursByName.set(h.Name, h);
    }

    const existingQueues = await listAllQueues(region, instanceId);
    for (const q of existingQueues) {
      if (q.Name) queueByName.set(q.Name, q);
    }

    const hoursReplacements: Array<[string, string]> = [];
    const queueReplacements: Array<[string, string]> = [];

    let createdHours = 0;
    let updatedHours = 0;
    let skippedHours = 0;

    let createdQueues = 0;
    let updatedQueues = 0;
    let skippedQueues = 0;

    // 0) Upsert hours of operation
    for (const h of bundle.hoursOfOperations || []) {
      if (!h?.name) continue;
      const existing = hoursByName.get(h.name);

      if (existing?.Id) {
        if (!overwrite) {
          skippedHours++;
        } else {
          if (!dryRun) {
            await c.send(
              new UpdateHoursOfOperationCommand(
                omitNil({
                  InstanceId: instanceId,
                  HoursOfOperationId: existing.Id,
                  Name: h.name,
                  Description: h.description,
                  TimeZone: h.timeZone,
                  Config: h.config
                }) as any
              )
            );
          }
          updatedHours++;
        }
        if (h.id && existing.Id) hoursReplacements.push([h.id, existing.Id]);
        if (h.arn && existing.Arn) hoursReplacements.push([h.arn, existing.Arn]);
        continue;
      }

      if (dryRun) {
        createdHours++;
        continue;
      }

      const created = await c.send(
        new CreateHoursOfOperationCommand(
          omitNil({
            InstanceId: instanceId,
            Name: h.name,
            Description: h.description,
            TimeZone: h.timeZone,
            Config: h.config,
            Tags: h.tags
          }) as any
        )
      );
      createdHours++;

      const createdId = (created as any).HoursOfOperationId;
      const createdArn = (created as any).HoursOfOperationArn;

      if (h.id && createdId) hoursReplacements.push([h.id, createdId]);
      if (h.arn && createdArn) hoursReplacements.push([h.arn, createdArn]);

      hoursByName.set(h.name, { Id: createdId, Arn: createdArn, Name: h.name });
    }

    // 0b) Upsert queues
    for (const q of bundle.queues || []) {
      if (!q?.name) continue;
      const existing = queueByName.get(q.name);

      // Resolve hours-of-operation in the target (by name preferred)
      let targetHoursId: string | undefined = undefined;
      if (q.hoursOfOperationName) {
        targetHoursId = hoursByName.get(q.hoursOfOperationName)?.Id;
      }
      if (!targetHoursId && q.hoursOfOperationId) {
        // fallback: if the bundle hours were imported, replacements may already contain the mapping
        const repl = hoursReplacements.find(([from]) => from === q.hoursOfOperationId);
        targetHoursId = repl?.[1];
      }

      if (existing?.Id) {
        if (!overwrite) {
          skippedQueues++;
        } else {
          if (!dryRun) {
            if (typeof q.maxContacts === "number") {
              await c.send(
                new UpdateQueueMaxContactsCommand({
                  InstanceId: instanceId,
                  QueueId: existing.Id,
                  MaxContacts: q.maxContacts
                } as any)
              );
            }
            if (targetHoursId) {
              await c.send(
                new UpdateQueueHoursOfOperationCommand({
                  InstanceId: instanceId,
                  QueueId: existing.Id,
                  HoursOfOperationId: targetHoursId
                } as any)
              );
            }
            if (q.outboundCallerConfig) {
              await c.send(
                new UpdateQueueOutboundCallerConfigCommand({
                  InstanceId: instanceId,
                  QueueId: existing.Id,
                  OutboundCallerConfig: q.outboundCallerConfig
                } as any)
              );
            }
            if (q.status) {
              await c.send(
                new UpdateQueueStatusCommand({
                  InstanceId: instanceId,
                  QueueId: existing.Id,
                  Status: q.status
                } as any)
              );
            }
          }
          updatedQueues++;
        }
        if (q.id && existing.Id) queueReplacements.push([q.id, existing.Id]);
        if (q.arn && existing.Arn) queueReplacements.push([q.arn, existing.Arn]);
        continue;
      }

      if (dryRun) {
        createdQueues++;
        continue;
      }

      if (!targetHoursId) {
        throw new Error(`Queue '${q.name}' is missing a resolvable hoursOfOperationId/name`);
      }

      const created = await c.send(
        new CreateQueueCommand(
          omitNil({
            InstanceId: instanceId,
            Name: q.name,
            Description: q.description,
            HoursOfOperationId: targetHoursId,
            MaxContacts: q.maxContacts,
            OutboundCallerConfig: q.outboundCallerConfig || undefined,
            Tags: q.tags
          }) as any
        )
      );
      createdQueues++;

      const createdId = (created as any).QueueId;
      const createdArn = (created as any).QueueArn;

      if (q.id && createdId) queueReplacements.push([q.id, createdId]);
      if (q.arn && createdArn) queueReplacements.push([q.arn, createdArn]);

      queueByName.set(q.name, { Id: createdId, Arn: createdArn, Name: q.name });
    }

    // Build target lookup tables (modules)
    const existingModules = await listAllContactFlowModules(region, instanceId);
    const moduleByName = new Map<string, { Id?: string; Arn?: string; Name?: string }>();
    for (const m of existingModules) {
      if (m.Name) moduleByName.set(m.Name, m);
    }

    const moduleReplacements: Array<[string, string]> = [];

    let createdModules = 0;
    let updatedModules = 0;
    let skippedModules = 0;

    // 1) Upsert flow modules
    for (const m of bundle.flowModules) {
      if (!m.name) continue;
      const existing = moduleByName.get(m.name);
      const baseContent =
        typeof m.content === "string" ? applyReplacements(m.content, [...hoursReplacements, ...queueReplacements]) : "{}";

      if (existing?.Id) {
        if (!overwrite) {
          skippedModules++;
          continue;
        }
        if (!dryRun && typeof baseContent === "string") {
          await c.send(
            new UpdateContactFlowModuleContentCommand(
              omitNil({
                InstanceId: instanceId,
                ContactFlowModuleId: existing.Id,
                Content: baseContent,
                Settings: m.settings
              }) as any
            )
          );
        }
        updatedModules++;
        if (m.id && existing.Id) moduleReplacements.push([m.id, existing.Id]);
        if (m.arn && existing.Arn) moduleReplacements.push([m.arn, existing.Arn]);
        continue;
      }

      if (dryRun) {
        createdModules++;
        continue;
      }

      const created = await c.send(
        new CreateContactFlowModuleCommand(
          omitNil({
            InstanceId: instanceId,
            Name: m.name,
            Description: m.description,
            Content: baseContent || "{}",
            Tags: m.tags,
            Settings: m.settings
          }) as any
        )
      );
      createdModules++;

      if (m.id && created.Id) moduleReplacements.push([m.id, created.Id]);
      if (m.arn && created.Arn) moduleReplacements.push([m.arn, created.Arn]);

      moduleByName.set(m.name, { Id: created.Id, Arn: created.Arn, Name: m.name });
    }

    // Flow replacements are only known after creating/updating flows.
    const flowReplacements: Array<[string, string]> = [];

    // Build target flow lookup tables
    const existingFlows = await listAllContactFlows(region, instanceId);
    const flowByNameType = new Map<string, { Id?: string; Arn?: string; Name?: string; ContactFlowType?: string }>();
    for (const f of existingFlows) {
      if (f.Name && f.ContactFlowType) flowByNameType.set(`${f.ContactFlowType}|${f.Name}`, f);
    }

    // Pre-populate flow replacements for flows that already exist in the target instance.
    for (const f0 of bundle.contactFlows) {
      if (!f0?.name || !f0?.type) continue;
      const existing0 = flowByNameType.get(`${f0.type}|${f0.name}`);
      if (!existing0?.Id) continue;
      if (f0.id) flowReplacements.push([f0.id, existing0.Id]);
      if (f0.arn && existing0.Arn) flowReplacements.push([f0.arn, existing0.Arn]);
    }

    let createdFlows = 0;
    let updatedFlows = 0;
    let skippedFlows = 0;

    const importedFlowTargets: Array<{ source: ExportedContactFlow; targetId: string }> = [];

    // 2) Upsert flows (first pass: replace modules)
    for (const f of bundle.contactFlows) {
      if (!f.name || !f.type) continue;

      const key = `${f.type}|${f.name}`;
      const existing = flowByNameType.get(key);
      const content1 =
        typeof f.content === "string"
          ? applyReplacements(
              applyReplacements(
                applyReplacements(f.content, [...hoursReplacements, ...queueReplacements]),
                moduleReplacements
              ),
              flowReplacements
            )
          : "{}";

      if (existing?.Id) {
        if (!overwrite) {
          skippedFlows++;
          continue;
        }
        if (!dryRun) {
          await c.send(
            new UpdateContactFlowContentCommand({
              InstanceId: instanceId,
              ContactFlowId: existing.Id,
              Content: content1
            })
          );
        }
        updatedFlows++;

        if (f.id) flowReplacements.push([f.id, existing.Id]);
        if (f.arn && existing.Arn) flowReplacements.push([f.arn, existing.Arn]);

        importedFlowTargets.push({ source: f, targetId: existing.Id });
        continue;
      }

      if (dryRun) {
        createdFlows++;
        continue;
      }

      const created = await c.send(
        new CreateContactFlowCommand(
          omitNil({
            InstanceId: instanceId,
            Name: f.name,
            Type: f.type as any,
            Description: f.description,
            Content: content1,
            Tags: f.tags
          }) as any
        )
      );
      createdFlows++;

      if (f.id && created.ContactFlowId) flowReplacements.push([f.id, created.ContactFlowId]);
      if (f.arn && created.ContactFlowArn) flowReplacements.push([f.arn, created.ContactFlowArn]);

      if (created.ContactFlowId) {
        importedFlowTargets.push({ source: f, targetId: created.ContactFlowId });
      }

      flowByNameType.set(key, {
        Id: created.ContactFlowId,
        Arn: created.ContactFlowArn,
        Name: f.name,
        ContactFlowType: f.type
      });
    }

    // 3) Second pass: update imported flows to replace flow-to-flow references too
    if (!dryRun && overwrite) {
      for (const { source, targetId } of importedFlowTargets) {
        if (!overwrite && createdFlows === 0 && updatedFlows === 0) break;
        if (typeof source.content !== "string") continue;

        const content2 = applyReplacements(
          applyReplacements(
            applyReplacements(source.content, [...hoursReplacements, ...queueReplacements]),
            moduleReplacements
          ),
          flowReplacements
        );

        await c.send(
          new UpdateContactFlowContentCommand({
            InstanceId: instanceId,
            ContactFlowId: targetId,
            Content: content2
          })
        );
      }
    }

    return res.status(200).json({
      createdHours,
      updatedHours,
      skippedHours,
      createdQueues,
      updatedQueues,
      skippedQueues,
      createdModules,
      updatedModules,
      skippedModules,
      createdFlows,
      updatedFlows,
      skippedFlows,
      dryRun,
      overwrite
    });
  } catch (e: any) {
    return res.status(500).json({ error: e?.message || String(e) });
  }
});
