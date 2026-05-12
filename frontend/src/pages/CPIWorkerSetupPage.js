import { useState } from "react";
import { Copy, CheckCircle2, Download, Smartphone, Apple, Cpu, ExternalLink, AlertCircle } from "lucide-react";
import { Button } from "../components/ui/button";
import { toast } from "sonner";

export default function CPIWorkerSetupPage() {
  const [copied, setCopied] = useState(false);

  const token = localStorage.getItem("token") || "";
  const backend = process.env.REACT_APP_BACKEND_URL || "";

  const onCopy = () => {
    navigator.clipboard.writeText(token);
    setCopied(true);
    toast.success("JWT copied to clipboard — paste into config.yaml");
    setTimeout(() => setCopied(false), 2500);
  };

  const Step = ({ n, title, children }) => (
    <div className="border rounded-lg p-5 space-y-3" data-testid={`cpi-setup-step-${n}`}>
      <div className="flex items-center gap-3">
        <div className="h-8 w-8 rounded-full bg-primary/10 text-primary font-bold flex items-center justify-center text-sm">
          {n}
        </div>
        <h3 className="text-lg font-semibold">{title}</h3>
      </div>
      <div className="text-sm text-muted-foreground space-y-2 ml-11">
        {children}
      </div>
    </div>
  );

  const Code = ({ children }) => (
    <pre className="bg-muted p-3 rounded text-xs font-mono overflow-x-auto my-2">{children}</pre>
  );

  return (
    <div className="space-y-6 max-w-4xl" data-testid="cpi-worker-setup-page">
      <div>
        <h1 className="text-2xl font-bold">CPI Worker Setup</h1>
        <p className="text-sm text-muted-foreground">
          One-time setup for your home PC to start running CPI installs on connected phones.
        </p>
      </div>

      <div className="border rounded-lg p-5 bg-amber-500/5 border-amber-500/30 space-y-2">
        <div className="flex items-center gap-2 text-amber-500 font-medium">
          <AlertCircle className="h-4 w-4" /> Prerequisites
        </div>
        <ul className="text-sm text-muted-foreground list-disc ml-6 space-y-1">
          <li>Windows 11 home PC, 16GB+ RAM, always-on, stable internet</li>
          <li>RealFlow already deployed (this site you are viewing)</li>
          <li>Android phone (rooted preferred) and/or iPhone (jailbroken preferred)</li>
          <li>Proxy Jet (or similar mobile residential 4G) account</li>
        </ul>
      </div>

      <Step n={1} title="Pull the latest worker code on your home PC">
        Open PowerShell on your home PC and run:
        <Code>{`cd C:\\realflow
.\\REALFLOW-UPDATE.bat`}</Code>
        This pulls the latest CPI module + worker code from the repo.
      </Step>

      <Step n={2} title="Run one-click installer (Administrator PowerShell)">
        Right-click PowerShell → "Run as Administrator", then:
        <Code>{`Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\\deployment\\cpi\\REALFLOW-CPI-SETUP.ps1`}</Code>
        Installs Python, Node, Appium, ADB, libimobiledevice, Apple drivers (~10-15 min first run).
      </Step>

      <Step n={3} title="Copy your JWT and paste into config.yaml">
        <p>Click the button below to copy your authentication token, then open <code className="bg-muted px-1 py-0.5 rounded text-xs">C:\realflow\realflow-cpi-worker\config.yaml</code> and paste it under <code className="bg-muted px-1 py-0.5 rounded text-xs">api.token</code>.</p>
        <div className="flex items-center gap-2 mt-3">
          <Button onClick={onCopy} data-testid="cpi-setup-copy-jwt">
            {copied ? <CheckCircle2 className="h-4 w-4 mr-2" /> : <Copy className="h-4 w-4 mr-2" />}
            {copied ? "Copied!" : "Copy My JWT"}
          </Button>
          <span className="text-xs text-muted-foreground">Token is sensitive — never share or commit to git.</span>
        </div>
        <Code>{`api:
  base_url: "${backend}"
  token: "(paste here)"
  poll_interval_seconds: 5`}</Code>
      </Step>

      <Step n={4} title="Connect phones via USB">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-2">
          <div className="border rounded-lg p-3 space-y-2">
            <div className="flex items-center gap-2 font-medium">
              <Smartphone className="h-4 w-4" /> Android
            </div>
            <ol className="list-decimal ml-5 text-xs space-y-1">
              <li>Settings → About → Tap Build Number 7 times</li>
              <li>Settings → Developer Options → USB Debugging ON</li>
              <li>Connect via USB → "Allow USB debugging?" → Always allow</li>
              <li>(Optional but recommended) Magisk root for full anti-detect</li>
            </ol>
          </div>
          <div className="border rounded-lg p-3 space-y-2">
            <div className="flex items-center gap-2 font-medium">
              <Apple className="h-4 w-4" /> iPhone
            </div>
            <ol className="list-decimal ml-5 text-xs space-y-1">
              <li>Connect via USB → "Trust This Computer?" → Trust + passcode</li>
              <li>Settings → WiFi → (i) → Configure Proxy → Manual → set Proxy Jet</li>
              <li>Apple ID logged in (App Store works)</li>
              <li>(Optional) palera1n jailbreak for iPhone 7/8</li>
            </ol>
          </div>
        </div>
      </Step>

      <Step n={5} title="Verify everything works (Doctor)">
        <Code>{`.\\deployment\\cpi\\REALFLOW-CPI-DOCTOR.ps1`}</Code>
        All checks should be green. Connected devices will be listed.
      </Step>

      <Step n={6} title="Start the worker">
        <p className="font-medium">Option A — Manual (foreground):</p>
        <Code>{`.\\deployment\\cpi\\REALFLOW-CPI-WORKER-START.bat`}</Code>
        <p className="font-medium">Option B — Auto-start as Windows service (recommended):</p>
        <Code>{`.\\deployment\\cpi\\INSTALL-WORKER-AS-SERVICE.ps1`}</Code>
        Worker connects to <code className="bg-muted px-1 py-0.5 rounded text-xs">{backend}</code>, registers your phones, and starts polling for jobs.
      </Step>

      <Step n={7} title="You're done — devices appear in CPI Devices page">
        <p>Open <a href="/cpi/devices" className="text-blue-500 underline">CPI Devices</a> — your phones should show as <span className="text-green-500">online</span> within 30 seconds.</p>
        <p>Then create offers, paste proxies/UAs/leads, and click Start. Workflow runs automatically.</p>
      </Step>

      <div className="border rounded-lg p-5 space-y-3 bg-blue-500/5 border-blue-500/30">
        <div className="flex items-center gap-2 font-medium text-blue-500">
          <Cpu className="h-4 w-4" /> Reference docs (on your home PC)
        </div>
        <ul className="text-sm space-y-1">
          <li>• <code className="bg-muted px-1 py-0.5 rounded text-xs">CPI-SETUP-URDU.md</code> — full Urdu setup guide</li>
          <li>• <code className="bg-muted px-1 py-0.5 rounded text-xs">CPI-FAQ-URDU.md</code> — common issues + fixes</li>
          <li>• <code className="bg-muted px-1 py-0.5 rounded text-xs">deployment/cpi/README.txt</code> — script reference</li>
          <li>• <code className="bg-muted px-1 py-0.5 rounded text-xs">realflow-cpi-worker/README.md</code> — worker architecture</li>
        </ul>
      </div>
    </div>
  );
}
