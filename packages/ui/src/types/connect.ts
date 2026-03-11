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
