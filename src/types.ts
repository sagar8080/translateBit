export type Language = "hi" | "en";
export type Credentials = {
  code: string;
  participant_id: string;
  token: string;
  language: Language;
};
export type Participant = {
  id: string;
  language: Language;
  connected: boolean;
  reconnects: number;
};
export type Segment = {
  origin?: "scripted" | "local";
  asr_ms?: number | null;
  translation_ms?: number | null;
  id: string;
  speaker_id: string;
  language: Language;
  source: string;
  translation: string;
  status: string;
  created_at: number;
  processing_ms: number | null;
  error: string | null;
};
export type RoomState = {
  notices?: Record<string, string>;
  code: string;
  revision: number;
  mode: "scripted_demo";
  participants: Participant[];
  segments: Segment[];
  events: { name: string; at: number; segment_id?: string }[];
};
export type Sample = {
  id: string;
  language: Language;
  source: string;
  translation: string;
  label: string;
};
export const terminal = new Set([
  "completed",
  "cancelled",
  "interrupted",
  "failed",
]);
export const languageName = (language: Language) =>
  language === "hi" ? "Hindi" : "English";
export function nextPlayback(
  room: RoomState | null,
  participantId: string,
  attempted: Set<string>,
) {
  return room?.segments.find(
    (s) =>
      s.speaker_id !== participantId &&
      s.status === "queued" &&
      !attempted.has(s.id),
  );
}
export function acceptSnapshot(
  current: RoomState | null,
  next: RoomState,
): RoomState {
  return current &&
    current.code === next.code &&
    current.revision > next.revision
    ? current
    : next;
}
