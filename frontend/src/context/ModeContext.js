import React, { createContext, useContext, useEffect, useState } from "react";
import axios from "axios";

const ModeContext = createContext({
  mode: "local",
  isCloud: false,
  downloadUrl: null,
  loaded: false,
});

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export function ModeProvider({ children }) {
  const [state, setState] = useState({
    mode: "local",
    isCloud: false,
    downloadUrl: null,
    loaded: false,
  });

  useEffect(() => {
    axios
      .get(`${API}/mode`)
      .then((r) =>
        setState({
          mode: r.data.mode,
          isCloud: !!r.data.is_cloud,
          downloadUrl: r.data.download_url,
          loaded: true,
        })
      )
      .catch(() =>
        setState((s) => ({ ...s, loaded: true }))
      );
  }, []);

  return <ModeContext.Provider value={state}>{children}</ModeContext.Provider>;
}

export const useMode = () => useContext(ModeContext);
