// ──────────────────────────────────────────────────────────────────
// Krexion — Site Content (Website CMS) Admin Page  (2026-06)
//
// Edits every text on the public website (HomePage) from one screen:
//   • Hero (badge, headline, subtitle, CTA labels)
//   • Stats strip (4 numbers)
//   • Features section intro + cards (icon, title, description)
//   • Pricing section intro
//   • FAQ section intro + Q/A list
//   • Footer copy
//   • Nav labels
//
// API:
//   GET  /api/admin/site-content        — load
//   PUT  /api/admin/site-content        — patch any subset
//   POST /api/admin/site-content/reset  — back to defaults
// ──────────────────────────────────────────────────────────────────
import React, { useEffect, useState } from "react";
import axios from "axios";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import {
  ArrowLeft, Save, RotateCcw, Plus, Trash2, GripVertical,
  Sparkles, Layout, MessageCircle, ListChecks, Tag, Menu as MenuIcon, Quote,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const ICON_OPTIONS = [
  "Globe", "Activity", "Layers", "Cpu", "Shield", "MailCheck",
  "Zap", "Lock", "Sparkles", "Check", "Server", "Database",
  "BarChart", "Users", "TrendingUp", "Rocket", "Settings",
];

export default function SiteContentAdminPage() {
  const navigate = useNavigate();
  const [content, setContent] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const token = () => localStorage.getItem("adminToken") || localStorage.getItem("token");

  const load = async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/admin/site-content`, {
        headers: { Authorization: `Bearer ${token()}` },
      });
      setContent(r.data);
    } catch (e) {
      toast.error("Could not load site content");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const save = async (section, payload) => {
    setSaving(true);
    try {
      const body = section ? { [section]: payload } : payload;
      const r = await axios.put(`${API}/admin/site-content`, body, {
        headers: { Authorization: `Bearer ${token()}` },
      });
      setContent(r.data);
      toast.success("Saved — changes live on the public site");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const resetAll = async () => {
    if (!window.confirm("Reset ALL website content to defaults? This cannot be undone.")) return;
    setSaving(true);
    try {
      const r = await axios.post(`${API}/admin/site-content/reset`, {}, {
        headers: { Authorization: `Bearer ${token()}` },
      });
      setContent(r.data);
      toast.success("Reset to defaults");
    } catch (e) {
      toast.error("Reset failed");
    } finally {
      setSaving(false);
    }
  };

  if (loading || !content) {
    return (
      <div className="min-h-screen bg-black text-white flex items-center justify-center">
        <div className="text-zinc-400 text-sm">Loading website content…</div>
      </div>
    );
  }

  // Local edit helper — patches the in-state copy. Tabs save individually.
  const patch = (section, key, value) => {
    setContent(c => ({ ...c, [section]: { ...c[section], [key]: value } }));
  };
  const patchList = (key, list) => {
    setContent(c => ({ ...c, [key]: list }));
  };

  return (
    <div className="min-h-screen bg-black text-white" data-testid="site-content-admin">
      <div className="max-w-6xl mx-auto p-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <Button
              variant="ghost"
              onClick={() => navigate("/admin/dashboard")}
              className="text-zinc-400 hover:text-white"
              data-testid="back-to-admin"
            >
              <ArrowLeft size={16} className="mr-1" /> Back to Admin
            </Button>
          </div>
          <Button
            variant="outline"
            onClick={resetAll}
            disabled={saving}
            className="border-red-500/40 text-red-400 hover:bg-red-500/10"
            data-testid="reset-all-content"
          >
            <RotateCcw size={14} className="mr-1.5" /> Reset all to defaults
          </Button>
        </div>

        <div className="mb-6">
          <h1 className="text-2xl font-bold mb-1">Website Content</h1>
          <p className="text-sm text-zinc-400">
            Edit any text on krexion.com — saves live, no redeploy. Pricing plans are managed under
            <a href="/admin/licenses" className="text-blue-400 hover:underline mx-1">License & Pricing</a>.
          </p>
        </div>

        <Tabs defaultValue="hero" className="w-full">
          <TabsList className="bg-[#0F0F12] border border-white/10 overflow-x-auto flex justify-start w-full no-scrollbar">
            <TabsTrigger value="hero" data-testid="tab-hero"><Sparkles size={14} className="mr-1.5" />Hero</TabsTrigger>
            <TabsTrigger value="stats" data-testid="tab-stats"><Quote size={14} className="mr-1.5" />Stats</TabsTrigger>
            <TabsTrigger value="features" data-testid="tab-features"><Layout size={14} className="mr-1.5" />Features</TabsTrigger>
            <TabsTrigger value="pricing" data-testid="tab-pricing"><Tag size={14} className="mr-1.5" />Pricing intro</TabsTrigger>
            <TabsTrigger value="faq" data-testid="tab-faq"><MessageCircle size={14} className="mr-1.5" />FAQ</TabsTrigger>
            <TabsTrigger value="nav" data-testid="tab-nav"><MenuIcon size={14} className="mr-1.5" />Nav</TabsTrigger>
            <TabsTrigger value="footer" data-testid="tab-footer"><ListChecks size={14} className="mr-1.5" />Footer</TabsTrigger>
          </TabsList>

          {/* HERO */}
          <TabsContent value="hero">
            <SectionCard title="Hero Section" onSave={() => save("hero", content.hero)} saving={saving}>
              <Field label="Badge text (top pill)" testid="hero-badge"
                value={content.hero.badge} onChange={v => patch("hero","badge",v)} />
              <Field label="Headline (top line)" testid="hero-h1-top"
                value={content.hero.h1_top} onChange={v => patch("hero","h1_top",v)} />
              <Field label="Headline (bottom line, blue gradient)" testid="hero-h1-bottom"
                value={content.hero.h1_bottom} onChange={v => patch("hero","h1_bottom",v)} />
              <Field area label="Subtitle paragraph" testid="hero-subtitle"
                value={content.hero.subtitle} onChange={v => patch("hero","subtitle",v)} />
              <Field label="Primary CTA button label" testid="hero-cta"
                value={content.hero.cta_label} onChange={v => patch("hero","cta_label",v)} />
              <Field label="Secondary CTA label" testid="hero-cta2"
                value={content.hero.cta_secondary_label} onChange={v => patch("hero","cta_secondary_label",v)} />
            </SectionCard>
          </TabsContent>

          {/* STATS */}
          <TabsContent value="stats">
            <SectionCard title="Stats Strip (4 numbers)"
              onSave={() => save("stats", content.stats)} saving={saving}>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {(content.stats || []).map((s, idx) => (
                  <div key={idx} className="bg-black/40 border border-white/10 rounded-lg p-4 space-y-2"
                       data-testid={`stat-row-${idx}`}>
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-zinc-500">Stat #{idx+1}</span>
                      {content.stats.length > 1 && (
                        <button onClick={() => {
                          const next = content.stats.filter((_,i) => i !== idx);
                          patchList("stats", next);
                        }} className="text-red-400 hover:text-red-300" data-testid={`del-stat-${idx}`}>
                          <Trash2 size={14} />
                        </button>
                      )}
                    </div>
                    <Field small label="Value (e.g. 10M+)"
                      value={s.value}
                      onChange={v => {
                        const next = [...content.stats];
                        next[idx] = { ...next[idx], value: v };
                        patchList("stats", next);
                      }} />
                    <Field small label="Label (e.g. Clicks delivered)"
                      value={s.label}
                      onChange={v => {
                        const next = [...content.stats];
                        next[idx] = { ...next[idx], label: v };
                        patchList("stats", next);
                      }} />
                  </div>
                ))}
              </div>
              <Button variant="outline" size="sm" className="mt-2 border-white/20 text-zinc-300"
                onClick={() => patchList("stats", [...(content.stats||[]), { value: "", label: "" }])}
                data-testid="add-stat">
                <Plus size={13} className="mr-1" /> Add stat
              </Button>
            </SectionCard>
          </TabsContent>

          {/* FEATURES */}
          <TabsContent value="features">
            <SectionCard title="Features section — intro"
              onSave={() => save("features_intro", content.features_intro)} saving={saving}>
              <Field label="Eyebrow (tiny top label)"
                value={content.features_intro.eyebrow} onChange={v => patch("features_intro","eyebrow",v)} />
              <Field label="Section title"
                value={content.features_intro.title} onChange={v => patch("features_intro","title",v)} />
              <Field area label="Section subtitle"
                value={content.features_intro.subtitle} onChange={v => patch("features_intro","subtitle",v)} />
            </SectionCard>

            <SectionCard title="Feature cards"
              onSave={() => save("features", content.features)} saving={saving}>
              <div className="space-y-3">
                {(content.features || []).map((f, idx) => (
                  <div key={idx} className="bg-black/40 border border-white/10 rounded-lg p-4"
                       data-testid={`feature-row-${idx}`}>
                    <div className="flex items-center justify-between mb-3">
                      <span className="text-xs text-zinc-500 flex items-center gap-2">
                        <GripVertical size={14} /> Feature #{idx+1}
                      </span>
                      <div className="flex items-center gap-2">
                        <Button size="sm" variant="ghost" disabled={idx===0}
                          onClick={() => {
                            const next = [...content.features];
                            [next[idx-1], next[idx]] = [next[idx], next[idx-1]];
                            patchList("features", next);
                          }} data-testid={`feature-up-${idx}`}>↑</Button>
                        <Button size="sm" variant="ghost" disabled={idx===content.features.length-1}
                          onClick={() => {
                            const next = [...content.features];
                            [next[idx+1], next[idx]] = [next[idx], next[idx+1]];
                            patchList("features", next);
                          }} data-testid={`feature-dn-${idx}`}>↓</Button>
                        <button onClick={() => {
                          const next = content.features.filter((_,i) => i !== idx);
                          patchList("features", next);
                        }} className="text-red-400 hover:text-red-300" data-testid={`del-feature-${idx}`}>
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                      <div>
                        <Label className="text-xs text-zinc-400">Icon</Label>
                        <select
                          className="w-full mt-1 bg-black border border-white/10 rounded-md p-2 text-sm"
                          value={f.icon || "Sparkles"}
                          onChange={e => {
                            const next = [...content.features];
                            next[idx] = { ...next[idx], icon: e.target.value };
                            patchList("features", next);
                          }}
                          data-testid={`feature-icon-${idx}`}
                        >
                          {ICON_OPTIONS.map(i => <option key={i} value={i}>{i}</option>)}
                        </select>
                      </div>
                      <div className="sm:col-span-2">
                        <Field small label="Title" value={f.title}
                          onChange={v => {
                            const next = [...content.features];
                            next[idx] = { ...next[idx], title: v };
                            patchList("features", next);
                          }} />
                      </div>
                      <div className="sm:col-span-3">
                        <Field area small label="Description" value={f.desc}
                          onChange={v => {
                            const next = [...content.features];
                            next[idx] = { ...next[idx], desc: v };
                            patchList("features", next);
                          }} />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
              <Button variant="outline" size="sm" className="mt-3 border-white/20 text-zinc-300"
                onClick={() => patchList("features", [...(content.features||[]), { icon: "Sparkles", title: "", desc: "" }])}
                data-testid="add-feature">
                <Plus size={13} className="mr-1" /> Add feature
              </Button>
            </SectionCard>
          </TabsContent>

          {/* PRICING INTRO */}
          <TabsContent value="pricing">
            <SectionCard title="Pricing section — intro (plans themselves are under License & Pricing)"
              onSave={() => save("pricing_intro", content.pricing_intro)} saving={saving}>
              <Field label="Eyebrow"
                value={content.pricing_intro.eyebrow} onChange={v => patch("pricing_intro","eyebrow",v)} />
              <Field label="Section title"
                value={content.pricing_intro.title} onChange={v => patch("pricing_intro","title",v)} />
              <Field area label="Section subtitle"
                value={content.pricing_intro.subtitle} onChange={v => patch("pricing_intro","subtitle",v)} />
            </SectionCard>
          </TabsContent>

          {/* FAQ */}
          <TabsContent value="faq">
            <SectionCard title="FAQ section — intro"
              onSave={() => save("faq_intro", content.faq_intro)} saving={saving}>
              <Field label="Eyebrow"
                value={content.faq_intro.eyebrow} onChange={v => patch("faq_intro","eyebrow",v)} />
              <Field label="Section title"
                value={content.faq_intro.title} onChange={v => patch("faq_intro","title",v)} />
              <Field area label="Section subtitle (optional)"
                value={content.faq_intro.subtitle} onChange={v => patch("faq_intro","subtitle",v)} />
            </SectionCard>

            <SectionCard title="FAQ items" onSave={() => save("faqs", content.faqs)} saving={saving}>
              <div className="space-y-3">
                {(content.faqs || []).map((f, idx) => (
                  <div key={idx} className="bg-black/40 border border-white/10 rounded-lg p-4"
                       data-testid={`faq-row-${idx}`}>
                    <div className="flex items-center justify-between mb-3">
                      <span className="text-xs text-zinc-500 flex items-center gap-2">
                        <GripVertical size={14} /> FAQ #{idx+1}
                      </span>
                      <div className="flex items-center gap-2">
                        <Button size="sm" variant="ghost" disabled={idx===0}
                          onClick={() => {
                            const next = [...content.faqs];
                            [next[idx-1], next[idx]] = [next[idx], next[idx-1]];
                            patchList("faqs", next);
                          }} data-testid={`faq-up-${idx}`}>↑</Button>
                        <Button size="sm" variant="ghost" disabled={idx===content.faqs.length-1}
                          onClick={() => {
                            const next = [...content.faqs];
                            [next[idx+1], next[idx]] = [next[idx], next[idx+1]];
                            patchList("faqs", next);
                          }} data-testid={`faq-dn-${idx}`}>↓</Button>
                        <button onClick={() => {
                          patchList("faqs", content.faqs.filter((_,i) => i !== idx));
                        }} className="text-red-400 hover:text-red-300" data-testid={`del-faq-${idx}`}>
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </div>
                    <Field small label="Question" value={f.q}
                      onChange={v => {
                        const next = [...content.faqs];
                        next[idx] = { ...next[idx], q: v };
                        patchList("faqs", next);
                      }} />
                    <Field area small label="Answer" value={f.a}
                      onChange={v => {
                        const next = [...content.faqs];
                        next[idx] = { ...next[idx], a: v };
                        patchList("faqs", next);
                      }} />
                  </div>
                ))}
              </div>
              <Button variant="outline" size="sm" className="mt-3 border-white/20 text-zinc-300"
                onClick={() => patchList("faqs", [...(content.faqs||[]), { q: "", a: "" }])}
                data-testid="add-faq">
                <Plus size={13} className="mr-1" /> Add FAQ
              </Button>
            </SectionCard>
          </TabsContent>

          {/* NAV */}
          <TabsContent value="nav">
            <SectionCard title="Top navigation labels"
              onSave={() => save("nav", content.nav)} saving={saving}>
              <Field label="Features label" value={content.nav.features_label} onChange={v => patch("nav","features_label",v)} />
              <Field label="Pricing label"  value={content.nav.pricing_label}  onChange={v => patch("nav","pricing_label",v)} />
              <Field label="Download label" value={content.nav.download_label} onChange={v => patch("nav","download_label",v)} />
              <Field label="Guide label"    value={content.nav.guide_label}    onChange={v => patch("nav","guide_label",v)} />
              <Field label="FAQ label"      value={content.nav.faq_label}      onChange={v => patch("nav","faq_label",v)} />
              <Field label="Login label"    value={content.nav.login_label}    onChange={v => patch("nav","login_label",v)} />
              <Field label="CTA button label" value={content.nav.cta_label}    onChange={v => patch("nav","cta_label",v)} />
            </SectionCard>
          </TabsContent>

          {/* FOOTER */}
          <TabsContent value="footer">
            <SectionCard title="Footer copy"
              onSave={() => save("footer", content.footer)} saving={saving}>
              <Field area label="Footer tagline"
                value={content.footer.tagline} onChange={v => patch("footer","tagline",v)} />
              <Field label="Copyright text"
                value={content.footer.copyright} onChange={v => patch("footer","copyright",v)} />
            </SectionCard>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}

// ── Small presentational helpers ──────────────────────────────────

function SectionCard({ title, children, onSave, saving }) {
  return (
    <Card className="bg-[#0F0F12] border-white/10 mt-4">
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-base text-white">{title}</CardTitle>
        <Button size="sm" onClick={onSave} disabled={saving}
                className="bg-blue-500 hover:bg-blue-400 text-white" data-testid="save-section">
          <Save size={13} className="mr-1.5" /> {saving ? "Saving…" : "Save"}
        </Button>
      </CardHeader>
      <CardContent className="space-y-3">
        {children}
      </CardContent>
    </Card>
  );
}

function Field({ label, value, onChange, area, small, testid }) {
  return (
    <div>
      <Label className={`text-zinc-400 ${small ? "text-xs" : "text-xs"}`}>{label}</Label>
      {area ? (
        <Textarea
          rows={3}
          value={value || ""}
          onChange={e => onChange(e.target.value)}
          className="mt-1 bg-black border-white/10 text-white"
          data-testid={testid}
        />
      ) : (
        <Input
          value={value || ""}
          onChange={e => onChange(e.target.value)}
          className="mt-1 bg-black border-white/10 text-white"
          data-testid={testid}
        />
      )}
    </div>
  );
}
