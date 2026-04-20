import { useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useDropzone, type FileRejection } from "react-dropzone";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { UploadCloud, FileAudio, X, CheckCircle, Loader2, AlertCircle } from "lucide-react";
import { uploadCall } from "@/api/calls";
import { useAgents } from "@/hooks/useAgents";
import { useAuthStore } from "@/store/authStore";
import { cn } from "@/lib/utils";

const ALLOWED_EXTS = [".wav", ".mp3", ".m4a", ".mp4", ".ogg", ".flac"];
const MAX_SIZE_MB = 500;

const schema = z.object({
  agent_id: z.string().min(1, "Select an agent"),
  call_date: z.string().min(1, "Select a call date"),
});

type FormValues = z.infer<typeof schema>;

function formatBytes(bytes: number) {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function UploadPage() {
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const { data: agents = [], isLoading: agentsLoading } = useAgents();

  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [uploadProgress, setUploadProgress] = useState<"idle" | "uploading" | "success" | "error">("idle");
  const [uploadedCallId, setUploadedCallId] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors },
    setValue,
    watch,
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      call_date: new Date().toISOString().split("T")[0],
    },
  });

  // Pre-select agent for AGENT role
  const agentUser = agents.find((a) => a.user_id === user?.id);
  if (agentUser && !watch("agent_id")) {
    setValue("agent_id", agentUser.id);
  }

  const onDrop = useCallback((accepted: File[], rejected: FileRejection[]) => {
    setFileError(null);
    if (rejected.length > 0) {
      setFileError(`Rejected: ${rejected.map((r) => r.file.name).join(", ")}. Only ${ALLOWED_EXTS.join(", ")} files up to ${MAX_SIZE_MB} MB.`);
      return;
    }
    if (accepted.length > 0) {
      const f = accepted[0];
      const ext = "." + f.name.split(".").pop()?.toLowerCase();
      if (!ALLOWED_EXTS.includes(ext)) {
        setFileError(`File type '${ext}' is not allowed.`);
        return;
      }
      if (f.size > MAX_SIZE_MB * 1024 * 1024) {
        setFileError(`File exceeds ${MAX_SIZE_MB} MB limit.`);
        return;
      }
      setFile(f);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "audio/*": ALLOWED_EXTS },
    maxFiles: 1,
    maxSize: MAX_SIZE_MB * 1024 * 1024,
  });

  async function onSubmit(values: FormValues) {
    if (!file) {
      setFileError("Please select an audio file.");
      return;
    }

    setUploadProgress("uploading");
    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("agent_id", values.agent_id);
      formData.append("call_date", values.call_date);

      const result = await uploadCall(formData);
      setUploadedCallId(result.id);
      setUploadProgress("success");
    } catch {
      setUploadProgress("error");
    }
  }

  if (uploadProgress === "success") {
    return (
      <div className="p-8 max-w-lg mx-auto mt-16 text-center">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-green-100 mb-4">
          <CheckCircle className="text-green-600" size={32} />
        </div>
        <h2 className="text-xl font-semibold text-gray-900 mb-2">Upload successful</h2>
        <p className="text-sm text-gray-500 mb-1">
          Call ID: <span className="font-mono text-xs">{uploadedCallId}</span>
        </p>
        <p className="text-sm text-gray-500 mb-6">Processing has started. The call will appear in your calls list.</p>
        <div className="flex gap-3 justify-center">
          <button
            onClick={() => navigate("/calls")}
            className="px-4 py-2 rounded-lg bg-brand-600 text-white text-sm font-medium hover:bg-brand-700 transition-colors"
          >
            View calls list
          </button>
          <button
            onClick={() => {
              setFile(null);
              setUploadProgress("idle");
              setUploadedCallId(null);
            }}
            className="px-4 py-2 rounded-lg border border-gray-300 text-gray-700 text-sm font-medium hover:bg-gray-50 transition-colors"
          >
            Upload another
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 mb-1">Upload Call</h1>
      <p className="text-sm text-gray-500 mb-8">Upload an audio recording from 3CX to start analysis.</p>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        {/* Dropzone */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Audio file</label>
          <div
            {...getRootProps()}
            className={cn(
              "border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors",
              isDragActive ? "border-brand-500 bg-brand-50" : "border-gray-300 hover:border-gray-400 bg-white",
              file && "border-green-400 bg-green-50"
            )}
          >
            <input {...getInputProps()} />
            {file ? (
              <div className="flex items-center justify-center gap-3">
                <FileAudio size={24} className="text-green-600 flex-shrink-0" />
                <div className="text-left min-w-0">
                  <p className="text-sm font-medium text-gray-900 truncate">{file.name}</p>
                  <p className="text-xs text-gray-500">{formatBytes(file.size)}</p>
                </div>
                <button
                  type="button"
                  onClick={(e) => { e.stopPropagation(); setFile(null); }}
                  className="ml-2 text-gray-400 hover:text-gray-600"
                >
                  <X size={16} />
                </button>
              </div>
            ) : (
              <div>
                <UploadCloud size={32} className="mx-auto text-gray-400 mb-3" />
                <p className="text-sm font-medium text-gray-700">
                  {isDragActive ? "Drop the file here" : "Drag & drop audio file, or click to browse"}
                </p>
                <p className="text-xs text-gray-400 mt-1">
                  {ALLOWED_EXTS.join(", ")} — up to {MAX_SIZE_MB} MB
                </p>
              </div>
            )}
          </div>
          {fileError && (
            <p className="mt-1.5 text-xs text-red-600 flex items-center gap-1">
              <AlertCircle size={12} /> {fileError}
            </p>
          )}
        </div>

        {/* Agent selector */}
        <div>
          <label htmlFor="agent_id" className="block text-sm font-medium text-gray-700 mb-1.5">
            Agent
          </label>
          <select
            id="agent_id"
            {...register("agent_id")}
            disabled={user?.role === "AGENT" || agentsLoading}
            className="w-full px-3.5 py-2.5 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent bg-white disabled:bg-gray-50 disabled:text-gray-500"
          >
            <option value="">
              {agentsLoading ? "Loading agents…" : "Select agent"}
            </option>
            {agents.map((a) => (
              <option key={a.id} value={a.id}>
                {a.full_name} {a.employee_id ? `(${a.employee_id})` : ""}
              </option>
            ))}
          </select>
          {errors.agent_id && (
            <p className="mt-1.5 text-xs text-red-600">{errors.agent_id.message}</p>
          )}
        </div>

        {/* Call date */}
        <div>
          <label htmlFor="call_date" className="block text-sm font-medium text-gray-700 mb-1.5">
            Call date
          </label>
          <input
            id="call_date"
            type="date"
            {...register("call_date")}
            max={new Date().toISOString().split("T")[0]}
            className="w-full px-3.5 py-2.5 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
          />
          {errors.call_date && (
            <p className="mt-1.5 text-xs text-red-600">{errors.call_date.message}</p>
          )}
        </div>

        {uploadProgress === "error" && (
          <div className="flex items-center gap-2 px-3.5 py-2.5 rounded-lg bg-red-50 border border-red-200 text-xs text-red-700">
            <AlertCircle size={14} />
            Upload failed. Please try again.
          </div>
        )}

        <button
          type="submit"
          disabled={uploadProgress === "uploading"}
          className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-brand-600 hover:bg-brand-700 text-white text-sm font-semibold transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {uploadProgress === "uploading" ? (
            <>
              <Loader2 size={16} className="animate-spin" />
              Uploading…
            </>
          ) : (
            <>
              <UploadCloud size={16} />
              Upload and start analysis
            </>
          )}
        </button>
      </form>
    </div>
  );
}
