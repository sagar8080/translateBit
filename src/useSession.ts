import { useCallback, useEffect, useRef, useState } from "react";
import { acceptSnapshot, type Credentials, type RoomState } from "./types";

export function useSession(credentials: Credentials | null) {
  const [room, setRoom] = useState<RoomState | null>(null);
  const [connection, setConnection] = useState("connecting");
  const [error, setError] = useState("");
  const socket = useRef<WebSocket | null>(null);
  const [retry, setRetry] = useState(0);
  const reconnect = useCallback(() => setRetry((n) => n + 1), []);
  const send = useCallback((message: object) => {
    if (socket.current?.readyState !== WebSocket.OPEN) {
      setError(
        "Connection unavailable. Wait for reconnection before trying again.",
      );
      return false;
    }
    socket.current.send(JSON.stringify(message));
    return true;
  }, []);

  useEffect(() => {
    if (!credentials) return;
    let disposed = false;
    let timer: ReturnType<typeof setTimeout>;
    let failures = 0;
    let active: WebSocket;
    const connect = () => {
      setConnection(failures ? "reconnecting" : "connecting");
      active = new WebSocket(
        `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/api/rooms/${credentials.code}/events`,
      );
      socket.current = active;
      active.onopen = () =>
        active.send(JSON.stringify({ token: credentials.token }));
      active.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === "snapshot") {
          failures = 0;
          setConnection("connected");
          setRoom((current) => acceptSnapshot(current, data.room));
        } else if (data.type === "error") setError(data.message);
      };
      active.onclose = (event) => {
        if (disposed) return;
        window.speechSynthesis?.cancel();
        if ([4001, 4003, 4004, 4009].includes(event.code)) {
          setConnection("closed");
          setError(
            event.code === 4009
              ? "This participant is already connected in another tab."
              : "This room is unavailable or has expired. Leave and start a new room.",
          );
          return;
        }
        setConnection("reconnecting");
        failures += 1;
        timer = setTimeout(connect, Math.min(1000 * 2 ** (failures - 1), 8000));
      };
    };
    connect();
    return () => {
      disposed = true;
      clearTimeout(timer);
      active.onclose = null;
      active.close();
      socket.current = null;
    };
  }, [credentials, retry]);

  return { room, connection, error, setError, send, reconnect };
}
