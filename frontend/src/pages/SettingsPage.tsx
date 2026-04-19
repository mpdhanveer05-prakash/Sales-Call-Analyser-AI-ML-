import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Save, FileText, AlertCircle } from "lucide-react";
import { fetchScripts, createScript, updateScript } from "@/api/scripts";
import { useAuthStore } from "@/store/authStore";
import type { Script, ScriptRubric } from "@/types";

function emptyRubric(): ScriptRubric {
  return { required_points: [], prohibited_phrases: [], required_disclosures: [] };
}

function TagListEditor({
  label,
  items,
  onChange,
}: {
  label: string;
  items: string[];
  onChange: (v: string[]) => void;
}) {
  const [draft, setDraft] = useState("");

  function add() {
    const trimmed = draft.trim();
    if (trimmed && !items.includes(trimmed)) {
      onChange([...items, trimmed]);
    }
    setDraft("");
  }

  return (
    <div>
      <p className="text-xs font-medium text-gray-600 mb-1">{label}</p>
      <div className="flex gap-1.5 flex-wrap mb-1.5">
        {items.map((item, i) => (
          <span
            key={i}
            className="inline-flex items-center gap-1 bg-blue-50 border border-blue-200 text-blue-700 text-xs px-2 py-0.5 rounded-full"
          >
            {item}
            <button
              type="button"
              onClick={() => onChange(items.filter((_, idx) => idx !== i))}
              className="text-blue-400 hover:text-blue-700 leading-none"
            >
              ×
            </button>
          </span>
        ))}
      </div>
      <div className="flex gap-2">
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), add())}
          placeholder="Add item, then press Enter"
          className="flex-1 px-3 py-1.5 text-xs border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
        />
        <button
          type="button"
          onClick={add}
          className="px-2 py-1.5 text-xs bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
        >
          Add
        </button>
      </div>
    </div>
  );
}

function ScriptEditor({
  script,
  onSaved,
}: {
  script: Script | null;
  onSaved: () => void;
}) {
  const qc = useQueryClient();
  const [name, setName] = useState(script?.name ?? "");
  const [content, setContent] = useState(script?.content ?? "");
  const [rubric, setRubric] = useState<ScriptRubric>(
    script?.rubric ?? emptyRubric(),
  );
  const [saveError, setSaveError] = useState<string | null>(null);

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (script) {
        return updateScript(script.id, { name, content, rubric });
      }
      return createScript({ name, content, rubric, is_active: true });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["scripts"] });
      setSaveError(null);
      onSaved();
    },
    onError: () => setSaveError("Failed to save script. Please try again."),
  });

  return (
    <form
      onSubmit={(e) => { e.preventDefault(); saveMutation.mutate(); }}
      className="space-y-5"
    >
      <div>
        <label className="block text-xs font-medium text-gray-700 mb-1">Script Name</label>
        <input
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          placeholder="e.g. Standard Outbound Script v2"
        />
      </div>

      <div>
        <label className="block text-xs font-medium text-gray-700 mb-1">Script Content</label>
        <textarea
          required
          value={content}
          onChange={(e) => setContent(e.target.value)}
          rows={12}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-brand-500 resize-y"
          placeholder="Paste the full sales script here…"
        />
      </div>

      <div className="bg-gray-50 rounded-xl border border-gray-200 p-4 space-y-4">
        <p className="text-xs font-semibold text-gray-700 uppercase tracking-wide">Scoring Rubric</p>
        <TagListEditor
          label="Required Talking Points"
          items={rubric.required_points}
          onChange={(v) => setRubric((r) => ({ ...r, required_points: v }))}
        />
        <TagListEditor
          label="Prohibited Phrases"
          items={rubric.prohibited_phrases}
          onChange={(v) => setRubric((r) => ({ ...r, prohibited_phrases: v }))}
        />
        <TagListEditor
          label="Required Disclosures"
          items={rubric.required_disclosures}
          onChange={(v) => setRubric((r) => ({ ...r, required_disclosures: v }))}
        />
      </div>

      {saveError && (
        <div className="flex items-center gap-2 text-red-600 text-sm bg-red-50 border border-red-200 rounded-lg px-3 py-2">
          <AlertCircle size={14} /> {saveError}
        </div>
      )}

      <div className="flex justify-end">
        <button
          type="submit"
          disabled={saveMutation.isPending}
          className="flex items-center gap-2 px-4 py-2 bg-brand-600 hover:bg-brand-700 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50"
        >
          <Save size={14} />
          {saveMutation.isPending ? "Saving…" : "Save Script"}
        </button>
      </div>
    </form>
  );
}

export default function SettingsPage() {
  const user = useAuthStore((s) => s.user);
  const isManager = user?.role === "ADMIN" || user?.role === "MANAGER";

  const { data: scripts = [], isLoading } = useQuery({
    queryKey: ["scripts"],
    queryFn: () => fetchScripts(false),
  });

  const [selectedId, setSelectedId] = useState<string | "new" | null>(null);
  const selected = selectedId === "new" ? null : scripts.find((s) => s.id === selectedId) ?? null;

  if (!isManager) {
    return (
      <div className="p-8 max-w-2xl mx-auto">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">Settings</h1>
        <p className="text-sm text-gray-500">You need Manager or Admin access to manage scripts.</p>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 mb-1">Settings</h1>
      <p className="text-sm text-gray-500 mb-6">Manage sales scripts and scoring rubrics.</p>

      <div className="flex gap-6">
        {/* Script list */}
        <div className="w-56 flex-shrink-0">
          <div className="flex items-center justify-between mb-3">
            <p className="text-xs font-semibold text-gray-600 uppercase tracking-wide">Scripts</p>
            <button
              onClick={() => setSelectedId("new")}
              className="flex items-center gap-1 text-xs text-brand-600 hover:text-brand-700 font-medium"
            >
              <Plus size={12} /> New
            </button>
          </div>
          {isLoading ? (
            <p className="text-xs text-gray-400">Loading…</p>
          ) : scripts.length === 0 ? (
            <p className="text-xs text-gray-400">No scripts yet.</p>
          ) : (
            <ul className="space-y-1">
              {scripts.map((s) => (
                <li key={s.id}>
                  <button
                    onClick={() => setSelectedId(s.id)}
                    className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-left transition-colors ${
                      selectedId === s.id
                        ? "bg-brand-50 text-brand-700 font-medium border border-brand-200"
                        : "text-gray-700 hover:bg-gray-100"
                    }`}
                  >
                    <FileText size={13} />
                    <span className="truncate">{s.name}</span>
                    {s.is_active && (
                      <span className="ml-auto flex-shrink-0 w-1.5 h-1.5 rounded-full bg-emerald-500" />
                    )}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Editor panel */}
        <div className="flex-1 bg-white rounded-xl border border-gray-200 p-6">
          {selectedId === null ? (
            <div className="flex flex-col items-center justify-center h-48 text-gray-400 gap-3">
              <FileText size={28} className="opacity-40" />
              <p className="text-sm">Select a script to edit, or create a new one.</p>
              <button
                onClick={() => setSelectedId("new")}
                className="flex items-center gap-1.5 text-sm text-brand-600 hover:text-brand-700 font-medium"
              >
                <Plus size={14} /> Create new script
              </button>
            </div>
          ) : (
            <>
              <h2 className="text-base font-semibold text-gray-900 mb-5">
                {selectedId === "new" ? "New Script" : "Edit Script"}
              </h2>
              <ScriptEditor
                key={selectedId}
                script={selected}
                onSaved={() => setSelectedId(null)}
              />
            </>
          )}
        </div>
      </div>
    </div>
  );
}
