/**
 * Cloud-Gate Axios Interceptor
 * ----------------------------
 * When the backend is running in `cloud` mode (krexion.com edge), heavy
 * endpoints reply 423 with a friendly explanation. We intercept that
 * response globally and show a sonner toast pointing to /download — so
 * every page gets the behaviour for free.
 */
import axios from "axios";
import { toast } from "sonner";

let lastToastAt = 0;

axios.interceptors.response.use(
  (r) => r,
  (err) => {
    const status = err?.response?.status;
    if (status === 423) {
      const detail =
        err.response?.data?.detail ||
        "This feature runs on your own PC. Install the Krexion desktop app.";
      const now = Date.now();
      // Throttle so a parallel batch of failed requests doesn't spam.
      if (now - lastToastAt > 2500) {
        lastToastAt = now;
        toast.error(detail, {
          duration: 9000,
          action: {
            label: "Download",
            onClick: () => window.open("https://krexion.com/download", "_blank"),
          },
        });
      }
    }
    return Promise.reject(err);
  }
);
