import { describe, expect, it } from "vitest";
import { PLAY_PICK_EVENT, resolveNodeClick } from "./playPick";

describe("resolveNodeClick", () => {
  it("selects in edit mode and emits node_picked in play", () => {
    expect(resolveNodeClick(true, "piece_e2")).toEqual({ type: "select", nodeId: "piece_e2" });
    expect(resolveNodeClick(false, "piece_e2")).toEqual({
      type: "pick",
      name: PLAY_PICK_EVENT,
      nodeId: "piece_e2",
    });
  });
});
