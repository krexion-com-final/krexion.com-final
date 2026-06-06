/* ════════════════════════════════════════════════════════════════════════
   CustomerLayout.js — Picks the right shell for the logged-in customer
   ════════════════════════════════════════════════════════════════════════

   ❗ SAFETY NOTE
   This is a thin SWITCH wrapper. It does NOT add or remove any logic;
   it just decides which of the two existing layouts to render:

     • If `mode === "native"`  (customer's PC install OR ?ui=native preview)
       → wrap children in <NativeShell> (new AdsPower-style window).
     • Otherwise (cloud customer login, dev preview)
       → wrap children in <DashboardLayout> (the existing UI, untouched).

   Admin routes (`/admin/*`) never reach this file — they are mounted
   outside the PrivateRoute block in App.js, so they keep their own
   independent shell exactly as before.

   While the mode is still being fetched we render <DashboardLayout> to
   avoid a flash; once `useMode().loaded === true` we settle on the
   correct shell. Customers will never see a layout swap because the
   /api/mode call resolves in <50 ms on the same machine in native
   installs.
   ════════════════════════════════════════════════════════════════════════ */

import { useMode } from "../context/ModeContext";
import DashboardLayout from "./DashboardLayout";
import NativeShell from "./NativeShell";

export default function CustomerLayout({ children }) {
  const { isNative, loaded } = useMode();
  if (loaded && isNative) {
    return <NativeShell>{children}</NativeShell>;
  }
  return <DashboardLayout>{children}</DashboardLayout>;
}
