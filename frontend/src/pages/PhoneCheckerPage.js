import { useState, useRef } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Textarea } from "../components/ui/textarea";
import { Badge } from "../components/ui/badge";
import { Progress } from "../components/ui/progress";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { toast } from "sonner";
import {
  Upload,
  Phone,
  PhoneOff,
  Download,
  RefreshCw,
  Copy,
  Trash2,
  FileSpreadsheet,
  File as FileIcon,
  CheckCircle,
  XCircle,
  Globe,
} from "lucide-react";

const API_URL = process.env.REACT_APP_BACKEND_URL;

/* Roman-Urdu friendly free phone validator (libphonenumber-powered).
   Backend: /api/phones/* — NO paid API, fully offline. */
export default function PhoneCheckerPage() {
  const [phoneInput, setPhoneInput] = useState("");
  const [defaultRegion, setDefaultRegion] = useState("US");
  const [checking, setChecking] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [results, setResults] = useState(null);
  const [valid, setValid] = useState([]);
  const [invalid, setInvalid] = useState([]);

  // Preserved upload context for export
  const [originalRows, setOriginalRows] = useState([]);
  const [originalColumns, setOriginalColumns] = useState([]);
  const [phoneColumn, setPhoneColumn] = useState(null);
  const [uploadedFilename, setUploadedFilename] = useState(null);

  const fileInputRef = useRef(null);

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const valid = [".xlsx", ".xls", ".csv", ".txt"];
    const ext = file.name.toLowerCase().substring(file.name.lastIndexOf("."));
    if (!valid.includes(ext)) {
      toast.error("Please upload .xlsx, .xls, .csv, or .txt");
      return;
    }

    setUploading(true);
    const token = localStorage.getItem("token");
    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch(`${API_URL}/api/phones/upload-file`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });
      const data = await response.json();
      if (response.ok) {
        setPhoneInput(data.phones.join("\n"));
        setOriginalRows(data.rows || []);
        setOriginalColumns(data.columns || []);
        setPhoneColumn(data.phone_column || null);
        setUploadedFilename(data.filename || file.name);
        toast.success(
          `Loaded ${data.count} phone numbers from ${file.name}` +
            (data.phone_column ? ` (column: ${data.phone_column})` : "")
        );
      } else {
        toast.error(data.detail || "Failed to parse file");
      }
    } catch (err) {
      toast.error("Error uploading file: " + err.message);
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const checkPhones = async () => {
    const phones = phoneInput
      .split(/[\n,;]+/)
      .map((p) => p.trim())
      .filter((p) => p);

    if (phones.length === 0) {
      toast.error("Please enter at least one phone number");
      return;
    }

    setChecking(true);
    setProgress(0);
    setValid([]);
    setInvalid([]);

    const token = localStorage.getItem("token");

    try {
      const response = await fetch(`${API_URL}/api/phones/check`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          phones,
          default_region: (defaultRegion || "").trim().toUpperCase(),
        }),
      });

      if (!response.ok) throw new Error("Check failed");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let validList = [];
      let invalidList = [];

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const text = decoder.decode(value);
        for (const line of text.split("\n").filter((l) => l.trim())) {
          try {
            const data = JSON.parse(line);
            if (data.type === "progress") {
              setProgress(Math.round((data.processed / data.total) * 100));
            } else if (data.type === "result") {
              if (data.valid) {
                validList.push(data);
                setValid([...validList]);
              } else {
                invalidList.push(data);
                setInvalid([...invalidList]);
              }
            } else if (data.type === "complete") {
              setResults({
                total: data.total,
                valid: data.valid,
                invalid: data.invalid,
              });
            }
          } catch (_) {
            /* skip bad lines */
          }
        }
      }
      toast.success(`Checked ${phones.length} phone numbers!`);
    } catch (err) {
      toast.error("Error checking phones: " + err.message);
    } finally {
      setChecking(false);
      setProgress(100);
    }
  };

  const copyPhones = (list, label) => {
    const text = list.map((r) => r.e164 || r.input).join("\n");
    navigator.clipboard.writeText(text);
    toast.success(`Copied ${list.length} ${label} phone numbers!`);
  };

  const downloadCSV = (list, filename) => {
    const head = "Input,Valid,E164,National,Country,Carrier,Line Type,Region";
    const body = list
      .map(
        (r) =>
          [
            r.input,
            r.valid,
            r.e164,
            r.national,
            r.country_name,
            r.carrier,
            r.line_type,
            r.region,
          ]
            .map((v) => `"${String(v || "").replace(/"/g, '""')}"`)
            .join(",")
      )
      .join("\n");
    const blob = new Blob([head + "\n" + body], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  const downloadExcel = async () => {
    const token = localStorage.getItem("token");
    // Build keyed result map (digits-only digits key matches backend
    // normalisation so the export joins correctly to original rows).
    const resultsDict = {};
    for (const r of [...valid, ...invalid]) {
      const key = (r.input || "").replace(/\D/g, "");
      if (key) resultsDict[key] = r;
    }
    try {
      const response = await fetch(
        `${API_URL}/api/phones/download-results`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            rows: originalRows,
            columns: originalColumns,
            phone_column: phoneColumn,
            results: resultsDict,
            default_region: defaultRegion,
          }),
        }
      );
      if (!response.ok) throw new Error("Failed to generate Excel");
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const baseName = uploadedFilename
        ? uploadedFilename.replace(/\.[^.]+$/, "")
        : "phone_check_results";
      a.download = `${baseName}_checked.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success("Excel file downloaded!");
    } catch (err) {
      toast.error("Error downloading: " + err.message);
    }
  };

  const clearAll = () => {
    setPhoneInput("");
    setResults(null);
    setValid([]);
    setInvalid([]);
    setProgress(0);
    setOriginalRows([]);
    setOriginalColumns([]);
    setPhoneColumn(null);
    setUploadedFilename(null);
  };

  const detected = phoneInput.split(/[\n,;]+/).filter((p) => p.trim()).length;

  return (
    <div className="space-y-6" data-testid="phone-checker-page">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Phone Checker</h1>
          <p className="text-zinc-400">
            Free offline phone validator — uses Google&apos;s libphonenumber.
            Detects country, carrier, line type (mobile/landline/VoIP) &amp;
            time zone. No paid API needed.
          </p>
        </div>
        {(valid.length > 0 || invalid.length > 0) && (
          <div className="flex gap-2">
            <Button
              onClick={downloadExcel}
              className="bg-green-600 hover:bg-green-700"
              data-testid="phone-download-excel-btn"
            >
              <FileSpreadsheet className="w-4 h-4 mr-2" />
              Download Excel
            </Button>
            <Button
              variant="outline"
              onClick={clearAll}
              className="border-zinc-700 text-zinc-300"
              data-testid="phone-clear-all-btn"
            >
              <Trash2 className="w-4 h-4 mr-2" />
              Clear All
            </Button>
          </div>
        )}
      </div>

      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader>
          <CardTitle className="text-white flex items-center gap-2">
            <Upload className="w-5 h-5 text-blue-500" />
            Upload or paste phone numbers
          </CardTitle>
          <CardDescription>
            Excel/CSV file <em>or</em> paste numbers below. Hint: numbers
            starting with <code>+</code> are detected automatically; for plain
            digits, set the default country below.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-4 flex-wrap items-center">
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileUpload}
              accept=".xlsx,.xls,.csv,.txt"
              className="hidden"
              id="phone-file-upload"
            />
            <Button
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              className="bg-purple-600 hover:bg-purple-700"
              data-testid="phone-upload-file-btn"
            >
              {uploading ? (
                <>
                  <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                  Uploading...
                </>
              ) : (
                <>
                  <FileSpreadsheet className="w-4 h-4 mr-2" />
                  Upload Excel/CSV
                </>
              )}
            </Button>
            <div className="flex items-center gap-2 text-zinc-500 text-sm">
              <FileIcon className="w-4 h-4" /> .xlsx, .xls, .csv, .txt
            </div>
            {uploadedFilename && (
              <Badge className="bg-zinc-700">
                {uploadedFilename}
                {phoneColumn ? ` · column: ${phoneColumn}` : ""}
                {originalRows.length ? ` · ${originalRows.length} rows` : ""}
              </Badge>
            )}
          </div>

          <div className="flex items-end gap-3 flex-wrap">
            <div>
              <Label
                htmlFor="default-region"
                className="text-zinc-300 text-xs"
              >
                <Globe className="w-3 h-3 inline mr-1" />
                Default country (ISO code)
              </Label>
              <Input
                id="default-region"
                value={defaultRegion}
                onChange={(e) =>
                  setDefaultRegion(e.target.value.toUpperCase().slice(0, 2))
                }
                className="bg-zinc-800 border-zinc-700 text-white w-24"
                placeholder="US"
                data-testid="phone-default-region"
              />
              <p className="text-xs text-zinc-500 mt-1">
                Used when number has no <code>+</code> prefix
              </p>
            </div>
          </div>

          <Textarea
            value={phoneInput}
            onChange={(e) => setPhoneInput(e.target.value)}
            placeholder={
              "Paste phone numbers (one per line):\n\n+14155552671\n+923001234567\n+44 20 7946 0958\n5551234567   (will use the default country above)"
            }
            className="bg-zinc-800 border-zinc-700 text-white h-40 font-mono text-sm"
            data-testid="phone-input"
          />

          <div className="flex items-center justify-between">
            <span className="text-zinc-400 text-sm">
              {detected} numbers detected
            </span>
            <Button
              onClick={checkPhones}
              disabled={checking || phoneInput.trim() === ""}
              className="bg-blue-600 hover:bg-blue-700"
              data-testid="phone-check-btn"
            >
              {checking ? (
                <>
                  <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                  Checking... {progress}%
                </>
              ) : (
                <>
                  <Phone className="w-4 h-4 mr-2" />
                  Check Phone Numbers
                </>
              )}
            </Button>
          </div>

          {checking && <Progress value={progress} className="h-2" />}
        </CardContent>
      </Card>

      {results && (
        <div className="grid grid-cols-3 gap-4">
          <Card className="bg-zinc-900 border-zinc-800">
            <CardContent className="pt-6 text-center">
              <div className="text-3xl font-bold text-white">
                {results.total}
              </div>
              <div className="text-zinc-400 text-sm">Total Checked</div>
              <Badge className="mt-2 bg-blue-700 text-xs">libphonenumber</Badge>
            </CardContent>
          </Card>
          <Card className="bg-green-900/30 border-green-700">
            <CardContent className="pt-6 text-center">
              <div className="text-3xl font-bold text-green-400">
                {results.valid}
              </div>
              <div className="text-green-300 text-sm flex items-center justify-center gap-1">
                <CheckCircle className="w-4 h-4" />
                Valid
              </div>
            </CardContent>
          </Card>
          <Card className="bg-red-900/30 border-red-700">
            <CardContent className="pt-6 text-center">
              <div className="text-3xl font-bold text-red-400">
                {results.invalid}
              </div>
              <div className="text-red-300 text-sm flex items-center justify-center gap-1">
                <XCircle className="w-4 h-4" />
                Invalid
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {(valid.length > 0 || invalid.length > 0) && (
        <div className="grid grid-cols-2 gap-6">
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-green-400 flex items-center gap-2">
                  <Phone className="w-5 h-5" />
                  Valid ({valid.length})
                </CardTitle>
                {valid.length > 0 && (
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => copyPhones(valid, "valid")}
                      className="text-zinc-400 hover:text-white"
                      title="Copy E.164 numbers"
                      data-testid="phone-copy-valid-btn"
                    >
                      <Copy className="w-4 h-4" />
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => downloadCSV(valid, "valid_phones.csv")}
                      className="text-zinc-400 hover:text-white"
                      title="Download CSV"
                    >
                      <Download className="w-4 h-4" />
                    </Button>
                  </div>
                )}
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {valid.length === 0 ? (
                  <p className="text-zinc-500 text-center py-8">
                    No results yet
                  </p>
                ) : (
                  valid.map((r, i) => (
                    <div
                      key={i}
                      className="p-2 bg-zinc-800 rounded-lg hover:bg-zinc-700"
                    >
                      <div className="flex items-center gap-2">
                        <span className="text-white font-mono text-sm flex-1 truncate">
                          {r.e164 || r.input}
                        </span>
                        <Badge className="bg-green-600 text-[10px] uppercase">
                          {r.line_type || "unknown"}
                        </Badge>
                      </div>
                      <div className="text-zinc-400 text-xs mt-1 flex gap-2 flex-wrap">
                        {r.country_name && (
                          <span>
                            <Globe className="w-3 h-3 inline mr-1" />
                            {r.country_name}
                            {r.region ? ` (${r.region})` : ""}
                          </span>
                        )}
                        {r.carrier && <span>· {r.carrier}</span>}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>

          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-red-400 flex items-center gap-2">
                  <PhoneOff className="w-5 h-5" />
                  Invalid ({invalid.length})
                </CardTitle>
                {invalid.length > 0 && (
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => copyPhones(invalid, "invalid")}
                      className="text-zinc-400 hover:text-white"
                      title="Copy inputs"
                    >
                      <Copy className="w-4 h-4" />
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() =>
                        downloadCSV(invalid, "invalid_phones.csv")
                      }
                      className="text-zinc-400 hover:text-white"
                      title="Download CSV"
                    >
                      <Download className="w-4 h-4" />
                    </Button>
                  </div>
                )}
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {invalid.length === 0 ? (
                  <p className="text-zinc-500 text-center py-8">
                    No invalid numbers
                  </p>
                ) : (
                  invalid.map((r, i) => (
                    <div
                      key={i}
                      className="p-2 bg-zinc-800 rounded-lg hover:bg-zinc-700"
                    >
                      <div className="flex items-center gap-2">
                        <span className="text-white font-mono text-sm flex-1 truncate">
                          {r.input}
                        </span>
                        <Badge className="bg-red-600 text-[10px]">
                          INVALID
                        </Badge>
                      </div>
                      {(r.error || r.country_name) && (
                        <div className="text-zinc-500 text-xs mt-1 truncate">
                          {r.error
                            ? `Reason: ${r.error}`
                            : `Detected: ${r.country_name || r.region}`}
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
