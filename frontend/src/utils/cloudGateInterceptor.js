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

    // Bridge: local PC is offline
    if (
      status === 503 &&
      detail &&
      typeof detail === "object" &&
      detail.code === "local_pc_offline"
    ) {
      maybeToast(
        detail.message ||
          "Aap ka Krexion PC offline hai. Heavy features tab kaam karte hain jab PC on ho.",
        {
          action: {
            label: "Guide",
            onClick: () => window.open("/guide", "_blank"),
          },
        }
      );
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
