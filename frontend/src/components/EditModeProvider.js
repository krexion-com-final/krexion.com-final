// ──────────────────────────────────────────────────────────────────
// Krexion — Edit Mode Context  (2026-06)
//
// Activated when the URL has `?edit=1` AND the user has an admin token
// in localStorage. Provides a `useEditMode()` hook to any component on
// the public site so they can render an editable shell instead of plain
// text and ship saves through `saveField(section, field, value)`.
//
// Why a context instead of prop drilling? The public HomePage tree is
// deep (hero → CTAs → features → FAQ → footer) and almost every leaf
// node needs the edit-mode flag. Pulling it from a context keeps the
// HomePage refactor surgical.
// ──────────────────────────────────────────────────────────────────
import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import axios from "axios";
import { toast } from "sonner";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const EditModeContext = createContext({
  editMode: false,
  setEditMode: () => {},
  saveField: async () => {},
  saveList: async () => {},
  content: null,
  setContent: () => {},
});

export function EditModeProvider({ children, content, setContent }) {
  const [editMode, setEditMode] = useState(false);

  // Activate edit mode if `?edit=1` is in the URL AND we have an admin
  // token. The admin token check prevents a random anonymous visitor
  // from poking around in edit mode (the API rejects them anyway, but
  // it'd be confusing UX). The localStorage key matches AdminLoginPage
  // (`adminToken`, camelCase) — DO NOT change it to admin_token, that
  // breaks production deploys that already have logged-in admins.
  useEffect(() => {
    try {
      const params = new URLSearchParams(window.location.search);
      const wantsEdit = params.get("edit") === "1";
      const hasAdmin = !!(localStorage.getItem("adminToken") || localStorage.getItem("token"));
      setEditMode(wantsEdit && hasAdmin);
    } catch {
      setEditMode(false);
    }
  }, []);

  const token = () => localStorage.getItem("adminToken") || localStorage.getItem("token");

  const saveField = useCallback(async (section, field, value) => {
    // Build a body that only patches the one section. The backend
    // shallow-merges so other untouched fields in that section are
    // preserved (see `_merge` in backend/site_content_module.py).
    const sectionPatch = { [field]: value };
    try {
      const r = await axios.put(`${API}/admin/site-content`, { [section]: sectionPatch }, {
        headers: { Authorization: `Bearer ${token()}` },
      });
      setContent?.(r.data);
      toast.success("Saved");
      return true;
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Save failed");
      return false;
    }
  }, [setContent]);

  // For lists (features, faqs, stats): the caller sends the WHOLE
  // updated list back. Replacement is intentional — simpler than
  // diffing on the server.
  const saveList = useCallback(async (listKey, list) => {
    try {
      const r = await axios.put(`${API}/admin/site-content`, { [listKey]: list }, {
        headers: { Authorization: `Bearer ${token()}` },
      });
      setContent?.(r.data);
      toast.success("Saved");
      return true;
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Save failed");
      return false;
    }
  }, [setContent]);

  const value = useMemo(() => ({
    editMode, setEditMode, saveField, saveList, content, setContent,
  }), [editMode, saveField, saveList, content, setContent]);

  return (
    <EditModeContext.Provider value={value}>
      {children}
    </EditModeContext.Provider>
  );
}

export function useEditMode() {
  return useContext(EditModeContext);
}
