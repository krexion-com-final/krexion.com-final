/**
 * Cloud-Gate Axios Interceptor (v2 — Bridge-aware)
 * ------------------------------------------------
 * Behavior depends on the backend response:
 *   503 + detail.code === 'local_pc_offline'
 *      -> User is on the cloud dashboard and their PC is offline.
 *         Show a friendly toast asking them to turn it on.
 *   423
 *      -> Legacy hard-gate (still present on a few endpoints not yet
 *         wired through the bridge). Same toast.
 *
 * When the PC IS online, heavy endpoints transparently return a normal
 * 200 response (the bridge waited inline up to ~25s for the local PC to
 * execute), so the UI feels exactly like running locally.
 */
import axios from "axios";
import { toast } from "sonner";

let lastToastAt = 0;

function maybeToast(message, opts = {}) {
  const now = Date.now();
  if (now - lastToastAt < 2500) return;
  lastToastAt = now;
  toast.error(message, {
    duration: 9000,
    ...opts,
  });
}

axios.interceptors.response.use(
  (r) => r,
  (err) => {
    const status = err?.response?.status;
    const detail = err?.response?.data?.detail;

    // Bridge: cloud edge refused a heavy feature.
    // The backend tells us via detail.local_status whether the user's
    // desktop PC is actually online — show different copy + action for
    // each case so the user knows exactly what to do.
    if (
      status === 503 &&
      detail &&
      typeof detail === "object" &&
      detail.code === "local_pc_offline"
    ) {
      const localOnline = !!(detail.local_status && detail.local_status.online);
      const hint = detail.actionable_hint || (localOnline ? "open_desktop_app" : "install_desktop_app");

      // 2026-05: Dispatch a global event so the LocalPCOfflineDialog
      // component (mounted once in App.js) can show a PROMINENT modal.
      // The toast below still fires as a non-blocking confirmation for
      // repeat attempts after the modal is dismissed. The combination
      // (modal + toast) ensures the customer can NEVER accidentally
      // bypass the "your PC is off" warning and dump load on the VPS.
      try {
        window.dispatchEvent(
          new CustomEvent("krexion:local-pc-offline", { detail })
        );
      } catch (_e) {
        // Browsers without CustomEvent support — graceful no-op,
        // toast below still fires.
      }

      let msg;
      let actionLabel = "Download";
      let actionHref = detail.download_url || "/download";
      if (hint === "open_desktop_app" || localOnline) {
        msg =
          "Yeh heavy feature aap ke desktop app pe chalti hai (cloud nahi). " +
          "Apne computer pe Krexion kholein aur wahaan se job submit karein — " +
          "data automatically sync ho jata hai.";
        actionLabel = "How to";
        actionHref = "/guide";
      } else if (hint === "turn_on_pc") {
        msg =
          "Aap ka Krexion desktop app offline lag raha hai. Apne computer pe " +
          "Krexion start karein — kuch seconds mein cloud reconnect ho jayega, " +
          "phir job submit karein.";
        actionLabel = "Guide";
        actionHref = "/guide";
      } else {
        msg =
          detail.message ||
          "Heavy features sirf desktop app pe chalti hain. Install karein " +
          "(license ke sath free).";
      }
      maybeToast(msg, {
        action: {
          label: actionLabel,
          onClick: () => window.open(actionHref, "_blank"),
        },
      });
      return Promise.reject(err);
    }

    // Bridge: job timed out waiting for local PC
    if (
      status === 200 &&
      err?.response?.data?.timeout &&
      err?.response?.data?.job_id
    ) {
      maybeToast(
        "Job aap ke PC pe abhi process ho raha hai. Thodi der mein result aa jayega — page refresh karein."
      );
      return Promise.reject(err);
    }

    // Legacy 423 (a few endpoints not yet bridge-wired)
    if (status === 423) {
      const msg =
        (typeof detail === "string" && detail) ||
        "This feature runs on your own PC. Install the Krexion desktop app.";
      maybeToast(msg, {
        action: {
          label: "Download",
          onClick: () => window.open("/download", "_blank"),
        },
      });
    }
    return Promise.reject(err);
  }
);
