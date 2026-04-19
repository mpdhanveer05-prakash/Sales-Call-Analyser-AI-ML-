import { X, CheckCircle, AlertCircle, Info, AlertTriangle } from "lucide-react";
import { clsx } from "clsx";
import { useToastStore, type Toast } from "@/store/toastStore";

const META = {
  success: { icon: CheckCircle, cls: "bg-emerald-50 border-emerald-300 text-emerald-800" },
  error:   { icon: AlertCircle, cls: "bg-red-50 border-red-300 text-red-800" },
  warning: { icon: AlertTriangle, cls: "bg-amber-50 border-amber-300 text-amber-800" },
  info:    { icon: Info, cls: "bg-blue-50 border-blue-300 text-blue-800" },
};

function ToastItem({ toast }: { toast: Toast }) {
  const remove = useToastStore((s) => s.remove);
  const { icon: Icon, cls } = META[toast.type];
  return (
    <div className={clsx("flex items-start gap-3 px-4 py-3 rounded-xl border shadow-lg text-sm max-w-sm animate-fade-in", cls)}>
      <Icon size={16} className="flex-shrink-0 mt-0.5" />
      <span className="flex-1 leading-snug">{toast.message}</span>
      <button onClick={() => remove(toast.id)} className="flex-shrink-0 opacity-60 hover:opacity-100 transition-opacity">
        <X size={14} />
      </button>
    </div>
  );
}

export default function ToastContainer() {
  const toasts = useToastStore((s) => s.toasts);
  if (toasts.length === 0) return null;
  return (
    <div className="fixed bottom-5 right-5 z-50 flex flex-col gap-2">
      {toasts.map((t) => <ToastItem key={t.id} toast={t} />)}
    </div>
  );
}
