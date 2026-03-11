export type ConnectRegion = { code: string; label: string };

export type InstanceSummary = {
  Id?: string;
  Arn?: string;
  IdentityManagementType?: string;
  InstanceAlias?: string;
  InstanceStatus?: string;
  InboundCallsEnabled?: boolean;
  OutboundCallsEnabled?: boolean;
};

export type DescribeInstance = InstanceSummary & {
  CreatedTime?: string;
  ServiceRole?: string;
};

export type ExportedFlowModule = {
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

export type ExportedContactFlow = {
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

export type ExportedHoursOfOperation = {
  id?: string;
  arn?: string;
  name: string;
  description?: string;
  timeZone?: string;
  config?: any;
  tags?: Record<string, string>;
};

export type ExportedQueue = {
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

export type ExportBundleV1 = {
  version: 1;
  exportedAt: string;
  source: { region: string; instanceId: string };
  hoursOfOperations?: ExportedHoursOfOperation[];
  queues?: ExportedQueue[];
  flowModules: ExportedFlowModule[];
  contactFlows: ExportedContactFlow[];
};
