export const PLAY_PICK_EVENT = "node_picked";

export function resolveNodeClick(
  editMode: boolean,
  nodeId: string,
): { type: "select"; nodeId: string } | { type: "pick"; name: "node_picked"; nodeId: string } {
  if (editMode) {
    return { type: "select", nodeId };
  }
  return { type: "pick", name: PLAY_PICK_EVENT, nodeId };
}
