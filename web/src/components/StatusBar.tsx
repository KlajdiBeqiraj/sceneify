import { CircleDot, Cpu, Radio } from "lucide-react";

export function StatusBar({
  status,
  protocol,
  revision,
  selectedId,
  syncMode,
}: {
  status: string;
  protocol: { version: number; compatible: boolean };
  revision?: number;
  selectedId: string | null;
  syncMode?: string | null;
}) {
  return (
    <>
      <span><CircleDot size={12} />{status || "Ready"}</span>
      <span className="status-spacer" />
      {selectedId && <span>Selected: {selectedId}</span>}
      {syncMode && <span className="sync-badge">Sync {syncMode}</span>}
      <span><Radio size={12} />Protocol v{protocol.version}{protocol.compatible ? "" : " incompatible"}</span>
      <span><Cpu size={12} />Revision {revision ?? "legacy"}</span>
    </>
  );
}
