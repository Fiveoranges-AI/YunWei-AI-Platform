// Slice ④ — real in-browser voice capture.
//
// Replaces the old "语音 = file picker" stub with MediaRecorder: tap 语音,
// record, stop, and the clip is staged like any other upload (sourceHint
// "voice"). Degrades honestly — if the browser can't record or mic access is
// denied, it shows why and offers a file-upload fallback.

import { useEffect, useRef, useState } from "react";
import { I } from "../icons";

type Props = {
  onRecorded: (file: File) => void;
  onClose: () => void;
  onUseFile?: () => void;
};

const MIME_CANDIDATES = [
  "audio/webm;codecs=opus",
  "audio/webm",
  "audio/mp4",
  "audio/ogg;codecs=opus",
];

function pickMime(): string {
  if (typeof MediaRecorder === "undefined") return "";
  for (const m of MIME_CANDIDATES) {
    try {
      if (MediaRecorder.isTypeSupported(m)) return m;
    } catch {
      /* ignore */
    }
  }
  return "";
}

function extForMime(mime: string): string {
  if (mime.includes("mp4")) return "m4a";
  if (mime.includes("ogg")) return "ogg";
  return "webm";
}

function fmtDuration(total: number): string {
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function stamp(): string {
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, "0");
  return `${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}`;
}

export function VoiceRecorder({ onRecorded, onClose, onUseFile }: Props) {
  const [phase, setPhase] = useState<"starting" | "recording" | "error">("starting");
  const [seconds, setSeconds] = useState(0);
  const [errMsg, setErrMsg] = useState<string | null>(null);

  const recRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<BlobPart[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const timerRef = useRef<number | undefined>(undefined);
  const settledRef = useRef(false);

  useEffect(() => {
    let cancelled = false;

    function clearTimer() {
      if (timerRef.current) {
        window.clearInterval(timerRef.current);
        timerRef.current = undefined;
      }
    }
    function stopStream() {
      clearTimer();
      streamRef.current?.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }

    async function begin() {
      const supported =
        typeof navigator !== "undefined" &&
        !!navigator.mediaDevices?.getUserMedia &&
        typeof MediaRecorder !== "undefined";
      if (!supported) {
        setErrMsg("当前浏览器不支持录音");
        setPhase("error");
        return;
      }
      const mime = pickMime();
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
        streamRef.current = stream;
        const rec = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
        recRef.current = rec;
        rec.ondataavailable = (e) => {
          if (e.data && e.data.size > 0) chunksRef.current.push(e.data);
        };
        rec.onstop = () => {
          const type = rec.mimeType || mime || "audio/webm";
          const blob = new Blob(chunksRef.current, { type });
          stopStream();
          if (!settledRef.current && blob.size > 0) {
            settledRef.current = true;
            onRecorded(new File([blob], `录音-${stamp()}.${extForMime(type)}`, { type }));
          }
        };
        rec.start();
        setPhase("recording");
        timerRef.current = window.setInterval(() => setSeconds((s) => s + 1), 1000);
      } catch (e) {
        const name = (e as DOMException)?.name;
        setErrMsg(
          name === "NotAllowedError"
            ? "麦克风权限被拒绝，请在浏览器允许后重试"
            : name === "NotFoundError"
              ? "未检测到麦克风"
              : "无法开始录音",
        );
        setPhase("error");
        stopStream();
      }
    }

    void begin();
    return () => {
      cancelled = true;
      clearTimer();
      streamRef.current?.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function stopAndUse() {
    const rec = recRef.current;
    if (rec && rec.state !== "inactive") {
      rec.stop(); // onstop stages the clip + closes via onRecorded
    } else {
      onClose();
    }
  }

  function cancel() {
    settledRef.current = true; // suppress staging
    const rec = recRef.current;
    if (rec && rec.state !== "inactive") {
      try {
        rec.stop();
      } catch {
        /* ignore */
      }
    }
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    onClose();
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      onClick={cancel}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 1000,
        background: "rgba(11,18,32,0.45)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 16,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: "100%",
          maxWidth: 380,
          background: "var(--surface)",
          borderRadius: 16,
          boxShadow: "var(--shadow-pop)",
          padding: 22,
          textAlign: "center",
        }}
      >
        {phase === "error" ? (
          <>
            <div style={{ color: "var(--warn-600)", display: "flex", justifyContent: "center", marginBottom: 10 }}>
              {I.warn(26)}
            </div>
            <div style={{ fontSize: 15, fontWeight: 700, color: "var(--ink-900)" }}>无法录音</div>
            <div style={{ fontSize: 13, color: "var(--ink-500)", marginTop: 6, lineHeight: 1.6 }}>{errMsg}</div>
            <div style={{ display: "flex", gap: 8, justifyContent: "center", marginTop: 18 }}>
              <button className="btn btn-secondary" style={{ height: 38 }} onClick={cancel}>
                关闭
              </button>
              {onUseFile && (
                <button className="btn btn-primary" style={{ height: 38 }} onClick={onUseFile}>
                  改用文件上传
                </button>
              )}
            </div>
          </>
        ) : (
          <>
            <div
              className={phase === "recording" ? "glint" : undefined}
              style={{
                width: 72,
                height: 72,
                borderRadius: 36,
                margin: "4px auto 14px",
                background: phase === "recording" ? "var(--risk-100)" : "var(--ai-100)",
                color: phase === "recording" ? "var(--risk-500)" : "var(--ai-600)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              {I.mic(30)}
            </div>
            <div style={{ fontSize: 15, fontWeight: 700, color: "var(--ink-900)" }}>
              {phase === "starting" ? "正在开启麦克风…" : "正在录音"}
            </div>
            <div className="num" style={{ fontSize: 26, fontWeight: 700, color: "var(--ink-900)", marginTop: 8, letterSpacing: "0.02em" }}>
              {fmtDuration(seconds)}
            </div>
            <div style={{ fontSize: 12, color: "var(--ink-400)", marginTop: 4 }}>
              说完点「停止并使用」，AI 会转写并识别
            </div>
            <div style={{ display: "flex", gap: 8, justifyContent: "center", marginTop: 18 }}>
              <button className="btn btn-secondary" style={{ height: 40 }} onClick={cancel}>
                取消
              </button>
              <button
                className="btn btn-primary"
                style={{ height: 40 }}
                onClick={stopAndUse}
                disabled={phase !== "recording"}
              >
                {I.check(15, "#fff")} 停止并使用
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
