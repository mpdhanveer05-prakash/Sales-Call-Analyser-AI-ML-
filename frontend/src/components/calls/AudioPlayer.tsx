import { useEffect, useRef, useState, useImperativeHandle, forwardRef } from "react";
import WaveSurfer from "wavesurfer.js";
import { Play, Pause, Volume2, VolumeX } from "lucide-react";

export interface AudioPlayerHandle {
  seekTo: (ms: number) => void;
}

interface Props {
  audioUrl: string;
  onTimeUpdate?: (ms: number) => void;
}

const AudioPlayer = forwardRef<AudioPlayerHandle, Props>(({ audioUrl, onTimeUpdate }, ref) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WaveSurfer | null>(null);

  const [isPlaying, setIsPlaying] = useState(false);
  const [isReady, setIsReady] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useImperativeHandle(ref, () => ({
    seekTo(ms: number) {
      if (wsRef.current && isReady) {
        wsRef.current.seekTo(ms / 1000 / Math.max(duration, 1));
      }
    },
  }));

  useEffect(() => {
    if (!containerRef.current) return;

    const ws = WaveSurfer.create({
      container: containerRef.current,
      waveColor: "#94a3b8",
      progressColor: "#3b82f6",
      cursorColor: "#1d4ed8",
      barWidth: 2,
      barGap: 1,
      barRadius: 2,
      height: 64,
      normalize: true,
    });

    ws.on("ready", () => {
      setIsReady(true);
      setDuration(ws.getDuration());
    });

    ws.on("timeupdate", (t) => {
      const ms = Math.floor(t * 1000);
      setCurrentTime(t);
      onTimeUpdate?.(ms);
    });

    ws.on("play", () => setIsPlaying(true));
    ws.on("pause", () => setIsPlaying(false));
    ws.on("finish", () => setIsPlaying(false));

    ws.on("error", (err) => {
      setError(typeof err === "string" ? err : "Failed to load audio");
    });

    ws.load(audioUrl);
    wsRef.current = ws;

    return () => {
      ws.destroy();
      wsRef.current = null;
    };
  }, [audioUrl]); // eslint-disable-line react-hooks/exhaustive-deps

  const togglePlay = () => wsRef.current?.playPause();
  const toggleMute = () => {
    if (!wsRef.current) return;
    const next = !isMuted;
    wsRef.current.setMuted(next);
    setIsMuted(next);
  };

  const formatTime = (secs: number) => {
    const m = Math.floor(secs / 60);
    const s = Math.floor(secs % 60);
    return `${m}:${s.toString().padStart(2, "0")}`;
  };

  if (error) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-600">
        Audio unavailable: {error}
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 space-y-3">
      {/* Waveform */}
      <div ref={containerRef} className="w-full" />

      {/* Controls */}
      <div className="flex items-center gap-3">
        <button
          onClick={togglePlay}
          disabled={!isReady}
          className="flex items-center justify-center w-9 h-9 rounded-full bg-blue-600 text-white disabled:opacity-40 hover:bg-blue-700 transition-colors"
        >
          {isPlaying ? <Pause size={16} /> : <Play size={16} />}
        </button>

        <button
          onClick={toggleMute}
          disabled={!isReady}
          className="text-gray-500 hover:text-gray-700 disabled:opacity-40 transition-colors"
        >
          {isMuted ? <VolumeX size={16} /> : <Volume2 size={16} />}
        </button>

        <span className="text-xs text-gray-500 tabular-nums ml-auto">
          {formatTime(currentTime)} / {formatTime(duration)}
        </span>

        {!isReady && (
          <span className="text-xs text-gray-400 animate-pulse">Loading waveform…</span>
        )}
      </div>
    </div>
  );
});

AudioPlayer.displayName = "AudioPlayer";
export default AudioPlayer;
