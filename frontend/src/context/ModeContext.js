import React, { createContext, useContext, useEffect, useState } from "react";
import axios from "axios";

const ModeContext = createContext({
  mode: "local",
  isCloud: false,
  isNative: false,
  downloadUrl: null,
  loaded: false,
});

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/* ── isNative detection rules ────────────────────────────────────────
   Native shell activates when ANY of the following is true:
     1. Backend reports `mode: "native"` (production: set on the
        customer's PC by Inno Setup via the NSSM service AppEnvironmentExtra).
     2. Query string `?ui=native` is present (preview/QA testing).
     3. localStorage flag `krexion_force_native_ui` is "1" (sticky preview
        testing toggle).
   Cloud (`mode: "cloud"`) and dev (`mode: "local"`) get the existing
   DashboardLayout untouched. ──────────────────────────────────────── */
function detectForceNative() {
  try {
    if (typeof window === "undefined") return false;
    const params = new URLSearchParams(window.location.search);
    if (params.get("ui") === "native") return true;
    if (localStorage.getItem("krexion_force_native_ui") === "1") return true;
    return false;
  } catch (e) {
    return false;
  }
}

export function ModeProvider({ children }) {
  const [state, setState] = useState({
    mode: "local",
    isCloud: false,
    isNative: detectForceNative(),
    downloadUrl: null,
    loaded: false,
  });

  useEffect(() => {
    const forced = detectForceNative();
    axios
      .get(`${API}/mode`)
      .then((r) =>
        setState({
          mode: r.data.mode,
          isCloud: !!r.data.is_cloud,
          isNative: forced || r.data.mode === "native",
          downloadUrl: r.data.download_url,
          loaded: true,
        })
      )
      .catch(() =>
        setState((s) => ({ ...s, isNative: forced || s.isNative, loaded: true }))
      );
  }, []);

  return <ModeContext.Provider value={state}>{children}</ModeContext.Provider>;
}

export const useMode = () => useContext(ModeContext);
