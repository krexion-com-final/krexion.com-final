// ──────────────────────────────────────────────────────────────────
// Krexion — EditModeToolbar  (2026-06)
//
// Floating top-strip shown ONLY when edit mode is active. Tells the
// admin they're in edit mode, gives a quick way out, and a shortcut
// to the form-based admin (for things you can't easily inline-edit,
// like adding/reordering FAQ items).
// ──────────────────────────────────────────────────────────────────
import React from "react";
import { useEditMode } from "./EditModeProvider";
import { ExternalLink, Eye, Sparkles, Settings as SettingsIcon } from "lucide-react";

export default function EditModeToolbar() {
  const { editMode } = useEditMode();
  if (!editMode) return null;

  const exit = () => {
    const url = new URL(window.location.href);
    url.searchParams.delete("edit");
    window.location.href = url.toString();
  };

  return (
    <div
      style={{
        position: "fixed", top: 12, left: "50%", transform: "translateX(-50%)",
        zIndex: 99999, background: "#0F0F12",
        border: "1px solid rgba(59,130,246,0.45)",
        borderRadius: 999, padding: "8px 14px",
        boxShadow: "0 8px 32px rgba(0,0,0,0.55), 0 0 0 4px rgba(59,130,246,0.08)",
        display: "flex", alignItems: "center", gap: 12, fontSize: 13,
        backdropFilter: "blur(8px)",
      }}
      data-testid="edit-mode-toolbar"
    >
      <span style={{
        display: "inline-flex", alignItems: "center", gap: 6,
        color: "#60A5FA", fontWeight: 600,
      }}>
        <Sparkles size={14} /> EDIT MODE
      </span>
      <span style={{ color: "#888" }}>•</span>
      <span style={{ color: "#aaa", fontSize: 12 }}>
        Click any text on the page to edit it
      </span>
      <span style={{ color: "#888" }}>•</span>
      <a
        href="/admin/website-content"
        style={{
          color: "#60A5FA", textDecoration: "none", fontSize: 12,
          display: "inline-flex", alignItems: "center", gap: 4,
        }}
        data-testid="advanced-edit-link"
      >
        <SettingsIcon size={12} /> Lists / FAQ / Reorder <ExternalLink size={10} />
      </a>
      <button
        onClick={exit}
        style={{
          marginLeft: 4, background: "transparent",
          border: "1px solid rgba(255,255,255,0.15)",
          color: "white", padding: "5px 12px", borderRadius: 999,
          fontSize: 12, cursor: "pointer",
          display: "inline-flex", alignItems: "center", gap: 4,
        }}
        data-testid="exit-edit-mode"
      >
        <Eye size={12} /> Exit
      </button>
    </div>
  );
}
