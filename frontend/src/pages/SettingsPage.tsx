import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Save, FileText, AlertCircle, Bell, Trash2, ToggleLeft, ToggleRight } from "lucide-react";
import { fetchScripts, createScript, updateScript } from "@/api/scripts";
import { fetchKeywordAlerts, createKeywordAlert, updateKeywordAlert, deleteKeywordAlert } from "@/api/keyword_alerts";
import { useAuthStore } from "@/store/authStore";
import type { Script, ScriptRubric, KeywordAlert } from "@/types";

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

const KEYWORD_CATEGORIES = ["COMPETITOR", "PROHIBITED", "COMPLIANCE", "CUSTOM"];

function KeywordAlertsPanel() {
  const qc = useQueryClient();
  const [newKeyword, setNewKeyword] = useState("");
  const [newCategory, setNewCategory] = useState("CUSTOM");
  const [addError, setAddError] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["keyword-alerts"],
    queryFn: fetchKeywordAlerts,
  });
  const keywords = data?.data ?? [];

  const addMutation = useMutation({
    mutationFn: () => createKeywordAlert(newKeyword.trim(), newCategory),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["keyword-alerts"] });
      setNewKeyword("");
      setAddError(null);
    },
    onError: (e: { response?: { data?: { detail?: string } } }) =>
      setAddError(e?.response?.data?.detail ?? "Failed to add keyword."),
  });

  const toggleMutation = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      updateKeywordAlert(id, { is_active }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["keyword-alerts"] }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteKeywordAlert(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["keyword-alerts"] }),
  });

  return (
    <div className="space-y-4">
      {/* Add new */}
      <div className="bg-gray-50 rounded-xl border border-gray-200 p-4">
        <p className="text-xs font-semibold text-gray-700 uppercase tracking-wide mb-3">Add Keyword</p>
        <div className="flex gap-2">
          <input
            value={newKeyword}
            onChange={(e) => setNewKeyword(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && newKeyword.trim() && addMutation.mutate()}
            placeholder="e.g. competitor name, prohibited phrase…"
            className="flex-1 px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
          <select
            value={newCategory}
            onChange={(e) => setNewCategory(e.target.value)}
            className="px-3 py-2 text-sm border border-gray-300 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-brand-500"
          >
            {KEYWORD_CATEGORIES.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
          <button
            onClick={() => newKeyword.trim() && addMutation.mutate()}
            disabled={addMutation.isPending || !newKeyword.trim()}
            className="flex items-center gap-1.5 px-3 py-2 bg-brand-600 hover:bg-brand-700 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50"
          >
            <Plus size={13} />
            Add
          </button>
        </div>
        {addError && (
          <p className="text-xs text-red-600 mt-2 flex items-center gap-1">
            <AlertCircle size={11} /> {addError}
          </p>
        )}
      </div>

      {/* List */}
      {isLoading ? (
        <p className="text-sm text-gray-400">Loading keywords…</p>
      ) : keywords.length === 0 ? (
        <p className="text-sm text-gray-400">No keyword alerts configured. Add one above.</p>
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200">
                <th className="text-left px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase tracking-wider">Keyword</th>
                <th className="text-left px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase tracking-wider">Category</th>
                <th className="text-center px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase tracking-wider">Active</th>
                <th className="px-4 py-2.5 w-10"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {keywords.map((kw: KeywordAlert) => (
                <tr key={kw.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-2.5 font-medium text-gray-900">{kw.keyword}</td>
                  <td className="px-4 py-2.5">
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                      kw.category === "COMPETITOR" ? "bg-orange-100 text-orange-700" :
                      kw.category === "PROHIBITED" ? "bg-red-100 text-red-700" :
                      kw.category === "COMPLIANCE" ? "bg-blue-100 text-blue-700" :
                      "bg-gray-100 text-gray-700"
                    }`}>
                      {kw.category}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-center">
                    <button
                      onClick={() => toggleMutation.mutate({ id: kw.id, is_active: !kw.is_active })}
                      className="text-gray-500 hover:text-brand-600 transition-colors"
                    >
                      {kw.is_active
                        ? <ToggleRight size={20} className="text-emerald-500" />
                        : <ToggleLeft size={20} className="text-gray-400" />}
                    </button>
                  </td>
                  <td className="px-4 py-2.5">
                    <button
                      onClick={() => {
                        if (window.confirm(`Delete keyword "${kw.keyword}"?`)) {
                          deleteMutation.mutate(kw.id);
                        }
                      }}
                      className="p-1 rounded text-gray-400 hover:text-red-600 hover:bg-red-50 transition-colors"
                    >
                      <Trash2 size={13} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

type SettingsTab = "scripts" | "keywords";

export default function SettingsPage() {
  const user = useAuthStore((s) => s.user);
  const isManager = user?.role === "ADMIN" || user?.role === "MANAGER";
  const [settingsTab, setSettingsTab] = useState<SettingsTab>("scripts");

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
      <p className="text-sm text-gray-500 mb-4">Manage sales scripts and keyword alerts.</p>

      {/* Tab switcher */}
      <div className="flex gap-1 mb-6 border-b border-gray-200">
        <button
          onClick={() => setSettingsTab("scripts")}
          className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
            settingsTab === "scripts" ? "border-brand-600 text-brand-600" : "border-transparent text-gray-500 hover:text-gray-700"
          }`}
        >
          <FileText size={14} /> Scripts
        </button>
        <button
          onClick={() => setSettingsTab("keywords")}
          className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
            settingsTab === "keywords" ? "border-brand-600 text-brand-600" : "border-transparent text-gray-500 hover:text-gray-700"
          }`}
        >
          <Bell size={14} /> Keyword Alerts
        </button>
      </div>

      {settingsTab === "keywords" && <KeywordAlertsPanel />}

      {settingsTab === "scripts" && <div className="flex gap-6">
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
      </div>}
    </div>
  );
}
