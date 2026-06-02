// ──────────────────────────────────────────────────────────────────
// Krexion — EditableText  (2026-06)
//
// Wraps any piece of public-site text so an admin (with `?edit=1`)
// can click it, get an inline popover with a textarea + Save/Cancel,
// and have the change pushed live via /api/admin/site-content.
//
// USAGE
//   <EditableText section="hero" field="h1_top" value={content.hero.h1_top} />
//
// When NOT in edit mode it just renders `value` (or `children` if
// supplied for fancier rendering — e.g. a gradient span). When in edit
// mode it adds a dashed blue outline + pencil cursor, and clicking
// opens the editor popover anchored under the element.
// ──────────────────────────────────────────────────────────────────
import React, { useEffect, useRef, useState } from "react";
import { Pencil, X, Save } from "lucide-react";
import { useEditMode } from "./EditModeProvider";

export default function EditableText({
  section,
  field,
  value,
  as = "span",
  children,
  multiline = false,
  className = "",
  style = {},
  // 2026-06 — optional custom save handler. When provided, it's used
  // instead of the default `saveField(section, field, value)`. This
  // lets the caller patch list items (features[i].title etc) by
  // sending back the WHOLE updated list to the backend.
  onSave,
}) {
  const { editMode, saveField } = useEditMode();
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState(value || "");
  const [saving, setSaving] = useState(false);
  const ref = useRef(null);

  // Keep draft in sync if the upstream content changes (e.g. another
  // tab edits the same field).
  useEffect(() => { setDraft(value || ""); }, [value]);

  // Click outside to close (without saving).
  useEffect(() => {
    if (!open) return;
    const onDocClick = (e) => {
      if (ref.current && !ref.current.contains(e.target)) {
        setOpen(false);
        setDraft(value || "");
      }
    };
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [open, value]);

  // When NOT in edit mode → render plain.
  if (!editMode) {
    const Comp = as;
    if (children) return <Comp className={className} style={style}>{children}</Comp>;
    return <Comp className={className} style={style}>{value}</Comp>;
  }

  const handleSave = async (e) => {
    e?.stopPropagation?.();
    setSaving(true);
    const ok = onSave
      ? await onSave(draft)
      : await saveField(section, field, draft);
    setSaving(false);
    if (ok) setOpen(false);
  };

  const Comp = as;
  return (
    <span ref={ref} style={{ position: "relative", display: "inline-block" }}>
      <Comp
        onClick={(e) => { e.stopPropagation(); setOpen(true); }}
        className={`${className} krx-editable`}
        style={{
          ...style,
          outline: "1.5px dashed rgba(59,130,246,0.55)",
          outlineOffset: "3px",
          borderRadius: "4px",
          cursor: "pointer",
          transition: "outline-color .15s, background-color .15s",
        }}
        title="Click to edit"
        data-editable-section={section}
        data-editable-field={field}
      >
        {children || value || <span style={{ color: "#888" }}>[empty — click to add]</span>}
      </Comp>
      <Pencil size={11}
        style={{
          position: "absolute", top: -8, right: -8,
          background: "#3B82F6", color: "white",
          padding: 2, borderRadius: 999, zIndex: 5,
          pointerEvents: "none",
        }}
      />
      {open && (
        <div
          onClick={(e) => e.stopPropagation()}
          style={{
            position: "absolute", top: "calc(100% + 8px)", left: 0,
            minWidth: 320, maxWidth: 520, zIndex: 1000,
            background: "#0F0F12", border: "1px solid rgba(255,255,255,0.15)",
            borderRadius: 8, padding: 12,
            boxShadow: "0 12px 40px rgba(0,0,0,0.6)",
          }}
        >
          <div style={{
            fontSize: 11, color: "#60A5FA", textTransform: "uppercase",
            letterSpacing: "0.05em", marginBottom: 6, fontWeight: 600,
          }}>
            {section} · {field}
          </div>
          {multiline ? (
            <textarea
              autoFocus
              rows={4}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              style={{
                width: "100%", background: "#000", color: "white",
                border: "1px solid rgba(255,255,255,0.1)", borderRadius: 6,
                padding: 8, fontSize: 13, fontFamily: "inherit", resize: "vertical",
              }}
              data-testid={`edit-${section}-${field}-textarea`}
            />
          ) : (
            <input
              autoFocus
              type="text"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") handleSave(e); if (e.key === "Escape") setOpen(false); }}
              style={{
                width: "100%", background: "#000", color: "white",
                border: "1px solid rgba(255,255,255,0.1)", borderRadius: 6,
                padding: 8, fontSize: 13,
              }}
              data-testid={`edit-${section}-${field}-input`}
            />
          )}
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 8 }}>
            <button
              onClick={() => { setOpen(false); setDraft(value || ""); }}
              disabled={saving}
              style={{
                padding: "6px 12px", fontSize: 12, borderRadius: 6,
                background: "transparent", color: "#aaa",
                border: "1px solid rgba(255,255,255,0.1)", cursor: "pointer",
              }}
            >
              <X size={12} style={{ display: "inline", marginRight: 4 }} /> Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              style={{
                padding: "6px 12px", fontSize: 12, borderRadius: 6,
                background: "#3B82F6", color: "white", border: "none", cursor: "pointer",
                fontWeight: 500,
              }}
              data-testid={`edit-${section}-${field}-save`}
            >
              <Save size={12} style={{ display: "inline", marginRight: 4 }} />
              {saving ? "Saving…" : "Save"}
            </button>
          </div>
        </div>
      )}
    </span>
  );
}
