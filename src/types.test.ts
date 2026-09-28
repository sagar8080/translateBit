import { describe, expect, it } from "vitest";
import {
  acceptSnapshot,
  nextPlayback,
  type RoomState,
  type Segment,
} from "./types";

function segment(id: string, status: string, speaker_id = "hindi"): Segment {
  return {
    id,
    status,
    speaker_id,
    language: "hi",
    source: "source",
    translation: "translation",
    created_at: 1,
    processing_ms: 1,
    error: null,
  };
}
function room(segments: Segment[], revision = 1): RoomState {
  return {
    code: "TEST",
    mode: "scripted_demo",
    revision,
    segments,
    participants: [],
    events: [],
  };
}
describe("listener playback selection", () => {
  it("never selects own, cancelled, completed, or already attempted speech", () => {
    const state = room([
      segment("own", "queued", "english"),
      segment("done", "completed"),
      segment("cancel", "cancelled"),
      segment("attempted", "queued"),
      segment("valid", "queued"),
    ]);
    expect(nextPlayback(state, "english", new Set(["attempted"]))?.id).toBe(
      "valid",
    );
  });
  it("preserves segment order", () => {
    expect(
      nextPlayback(
        room([segment("first", "queued"), segment("second", "queued")]),
        "english",
        new Set(),
      )?.id,
    ).toBe("first");
  });
  it("does not roll back a room to an older snapshot", () => {
    const current = room([segment("first", "completed")], 10);
    expect(acceptSnapshot(current, room([segment("first", "queued")], 9))).toBe(
      current,
    );
  });
});
