"""
Krexion — RPA Studio module
============================

AdsPower-grade Robotic Process Automation engine.

Endpoints
─────────
Workflows:
  POST   /api/rpa/workflows                  create
  GET    /api/rpa/workflows                  list (current user)
  GET    /api/rpa/workflows/{id}             get one
  PATCH  /api/rpa/workflows/{id}             update
  DELETE /api/rpa/workflows/{id}             delete
  POST   /api/rpa/workflows/{id}/duplicate   clone
  POST   /api/rpa/workflows/import           import JSON
  GET    /api/rpa/workflows/{id}/export      export JSON

Runs:
  POST   /api/rpa/workflows/{id}/run         start a run (returns run_id)
  GET    /api/rpa/runs                       list user's runs (paged)
  GET    /api/rpa/runs/{run_id}              run detail (steps + screenshots)
  POST   /api/rpa/runs/{run_id}/stop         abort a running task
  GET    /api/rpa/runs/{run_id}/live         tail latest progress events
  GET    /api/rpa/runs/{run_id}/screenshot   latest screenshot frame

Templates:
  GET    /api/rpa/templates                  marketplace list (curated)

Catalog:
  GET    /api/rpa/node-catalog               static catalog of all node types

The engine reuses the existing stealth Chromium launcher from
real_user_traffic where available; falls back to a vanilla Playwright
launch if RUT helpers can't be imported (so this module is independently
deployable too).
"""
from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import os
import random
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger("rpa_studio")

_state: Dict[str, Any] = {
    "db": None,
    "runs": {},      # run_id -> in-memory run state (live tasks)
}


# ── Helpers ──────────────────────────────────────────────────────────
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _strip_id(doc: dict) -> dict:
    if not doc:
        return doc
    doc.pop("_id", None)
    return doc


# ── Models ────────────────────────────────────────────────────────────
class WorkflowNode(BaseModel):
    id: str
    type: str
    position: Dict[str, float] = Field(default_factory=lambda: {"x": 0, "y": 0})
    params: Dict[str, Any] = Field(default_factory=dict)
    on_error: str = "skip"  # skip|stop|retry
    body: List[str] = Field(default_factory=list)
    branches: Dict[str, List[str]] = Field(default_factory=dict)


class WorkflowEdge(BaseModel):
    from_id: str = Field(alias="from")
    to: str
    label: Optional[str] = None

    class Config:
        populate_by_name = True


class WorkflowSettings(BaseModel):
    thread_count: int = 1
    on_error_default: str = "skip"
    max_runtime_seconds: int = 3600
    browser_keep_open: bool = False
    use_stealth: bool = True
    headless: bool = True
    viewport: Dict[str, int] = Field(default_factory=lambda: {"width": 1280, "height": 800})


class WorkflowCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    nodes: List[Dict[str, Any]] = Field(default_factory=list)
    edges: List[Dict[str, Any]] = Field(default_factory=list)
    settings: Dict[str, Any] = Field(default_factory=dict)
    variables: Dict[str, Any] = Field(default_factory=dict)


class WorkflowUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    nodes: Optional[List[Dict[str, Any]]] = None
    edges: Optional[List[Dict[str, Any]]] = None
    settings: Optional[Dict[str, Any]] = None
    variables: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class RunStartRequest(BaseModel):
    variables: Dict[str, Any] = Field(default_factory=dict)  # override defaults
    headless: Optional[bool] = None
    starting_url: Optional[str] = None


# ── Node catalog (static) ─────────────────────────────────────────────
NODE_CATALOG = {
    "categories": [
        {
            "key": "web",
            "label": "Web Actions",
            "color": "#10b981",
            "nodes": [
                {"type": "goto", "label": "Goto URL", "params": ["url"]},
                {"type": "new_tab", "label": "New Tab", "params": ["url"]},
                {"type": "close_tab", "label": "Close Tab", "params": ["index"]},
                {"type": "close_other_tabs", "label": "Close Other Tabs", "params": []},
                {"type": "switch_tab", "label": "Switch Tab", "params": ["by", "value"]},
                {"type": "refresh", "label": "Refresh", "params": []},
                {"type": "go_back", "label": "Go Back", "params": []},
                {"type": "go_forward", "label": "Go Forward", "params": []},
                {"type": "click", "label": "Click", "params": ["selector", "button", "count"]},
                {"type": "random_click", "label": "Random Click", "params": ["selectors", "pool_label"]},
                {"type": "checkbox", "label": "Checkbox", "params": ["selector", "action"]},
                {"type": "hover", "label": "Hover", "params": ["selector"]},
                {"type": "focus", "label": "Focus", "params": ["selector"]},
                {"type": "select", "label": "Dropdown Select", "params": ["selector", "value", "match_by"]},
                {"type": "random_select", "label": "Random Select", "params": ["selector"]},
                {"type": "fill", "label": "Input / Fill", "params": ["selector", "value", "clear_first", "type_interval_ms"]},
                {"type": "scroll", "label": "Scroll", "params": ["distance", "smooth"]},
                {"type": "input_file", "label": "Input File", "params": ["selector", "file_url"]},
                {"type": "screenshot", "label": "Screenshot", "params": ["name", "full_page"]},
                {"type": "mark_final", "label": "Mark Final", "params": ["name"]},
                {"type": "evaluate", "label": "Execute JS", "params": ["script", "save_to"]},
            ],
        },
        {
            "key": "keyboard",
            "label": "Keyboard",
            "color": "#6366f1",
            "nodes": [
                {"type": "press", "label": "Key Press", "params": ["key"]},
                {"type": "key_combo", "label": "Key Combination", "params": ["combo"]},
            ],
        },
        {
            "key": "waits",
            "label": "Waits",
            "color": "#f59e0b",
            "nodes": [
                {"type": "wait", "label": "Wait Time", "params": ["ms", "random_min", "random_max"]},
                {"type": "wait_for_selector", "label": "Wait Element", "params": ["selector", "state", "timeout"]},
                {"type": "wait_for_request", "label": "Wait Request", "params": ["url_pattern", "timeout"]},
                {"type": "wait_for_load", "label": "Wait Page Load", "params": ["state"]},
                {"type": "wait_for_text", "label": "Wait Text", "params": ["text", "timeout"]},
                {"type": "wait_for_url", "label": "Wait URL", "params": ["contains", "timeout"]},
            ],
        },
        {
            "key": "data",
            "label": "Get Data",
            "color": "#3b82f6",
            "nodes": [
                {"type": "get_url", "label": "Get URL", "params": ["mode", "save_to"]},
                {"type": "get_element", "label": "Get Element", "params": ["selector", "extraction", "attribute", "save_to"]},
                {"type": "get_cookies", "label": "Get Cookies", "params": ["save_to"]},
                {"type": "clear_cookies", "label": "Clear Cookies", "params": []},
                {"type": "save_to_txt", "label": "Save to Txt", "params": ["filename", "template"]},
                {"type": "save_to_excel", "label": "Save to Excel", "params": ["filename", "columns"]},
                {"type": "download_file", "label": "Download File", "params": ["url"]},
                {"type": "import_excel", "label": "Import Excel", "params": ["upload_id", "save_to"]},
            ],
        },
        {
            "key": "data_proc",
            "label": "Data Processing",
            "color": "#0ea5e9",
            "nodes": [
                {"type": "set_var", "label": "Set Variable", "params": ["name", "value"]},
                {"type": "regex_extract", "label": "Extract via Regex", "params": ["input", "pattern", "save_to"]},
                {"type": "to_json", "label": "Convert to JSON", "params": ["input", "save_to"]},
                {"type": "extract_field", "label": "Extract Field", "params": ["input", "key", "save_to"]},
                {"type": "random_extract", "label": "Random Extract", "params": ["input", "save_to"]},
                {"type": "math", "label": "Math", "params": ["expression", "save_to"]},
            ],
        },
        {
            "key": "control",
            "label": "Control Flow",
            "color": "#a855f7",
            "nodes": [
                {"type": "if", "label": "If / Else", "params": ["variable", "condition", "value"]},
                {"type": "for_loop_times", "label": "For Loop Times", "params": ["times", "save_index"]},
                {"type": "for_loop_data", "label": "For Loop Data", "params": ["data_var", "save_item", "save_index"]},
                {"type": "while_loop", "label": "While Loop", "params": ["variable", "condition", "value", "max_iterations"]},
                {"type": "exit_loop", "label": "Exit Loop", "params": []},
                {"type": "throw_error", "label": "Throw Error", "params": ["message"]},
                {"type": "apply_workflow", "label": "Apply Sub-Workflow", "params": ["workflow_id"]},
                {"type": "quit_browser", "label": "Quit Browser", "params": []},
            ],
        },
        {
            "key": "third_party",
            "label": "Third-Party",
            "color": "#ec4899",
            "nodes": [
                {"type": "openai", "label": "OpenAI / Claude / Gemini", "params": ["provider", "model", "prompt", "save_to"]},
                {"type": "captcha_2captcha", "label": "Captcha Solver (2C/AntiC/CapM)", "params": ["provider", "api_key", "captcha_type", "save_to"]},
                {"type": "google_sheets", "label": "Google Sheets", "params": ["sheet_id", "operation", "range", "values"]},
                {"type": "http_request", "label": "HTTP Request", "params": ["method", "url", "headers", "body", "save_to"]},
            ],
        },
    ],
}


# ── Router build ──────────────────────────────────────────────────────
def build_router(get_current_user):
    router = APIRouter(prefix="/api/rpa", tags=["rpa-studio"])

    # ── Workflows CRUD ────────────────────────────────────────────────
    @router.post("/workflows")
    async def create_workflow(payload: WorkflowCreate, user=Depends(get_current_user)):
        db = _state["db"]
        wf_id = _new_id("wf")
        user_id = (user.get("id") or user.get("user_id") or user.get("email") or "") if isinstance(user, dict) else getattr(user, "id", "")
        now = _now_iso()
        doc = {
            "id": wf_id,
            "owner_user_id": user_id,
            "name": payload.name,
            "description": payload.description,
            "nodes": payload.nodes,
            "edges": payload.edges,
            "settings": payload.settings or {},
            "variables": payload.variables or {},
            "is_active": True,
            "version": 1,
            "created_at": now,
            "updated_at": now,
        }
        await db.rpa_workflows.insert_one(doc.copy())
        return _strip_id(doc)

    # ── Convert Visual Recorder steps → RPA flowchart ────────────────
    @router.post("/workflows/from-recorder")
    async def from_recorder(payload: Dict[str, Any] = Body(...), user=Depends(get_current_user)):
        """Convert a Visual Recorder `steps` array into a Krexion RPA
        workflow (nodes + edges) with auto-layout.

        Payload shape:
            {
              "name":  "My Workflow",          (optional)
              "steps": [{action: "goto", url: "..."}, …]
            }
        Returns the newly-created workflow.
        """
        db = _state["db"]
        user_id = (user.get("id") or user.get("user_id") or user.get("email") or "") if isinstance(user, dict) else getattr(user, "id", "")
        steps = payload.get("steps") or []
        if not isinstance(steps, list) or not steps:
            raise HTTPException(status_code=400, detail="steps array required")
        nodes, edges = _convert_recorder_steps_to_flowchart(steps)
        wf_id = _new_id("wf")
        now = _now_iso()
        doc = {
            "id": wf_id,
            "owner_user_id": user_id,
            "name": payload.get("name") or "Imported from Recorder",
            "description": payload.get("description") or f"Auto-converted from {len(steps)} recorded steps",
            "nodes": nodes,
            "edges": edges,
            "settings": {"use_stealth": True, "headless": True},
            "variables": {},
            "is_active": True,
            "version": 1,
            "created_at": now,
            "updated_at": now,
            "source": "visual_recorder",
        }
        await db.rpa_workflows.insert_one(doc.copy())
        return _strip_id(doc)

    @router.post("/workflows/from-upload/{upload_id}")
    async def from_upload(upload_id: str, user=Depends(get_current_user)):
        """Convert a saved Visual Recorder upload (Uploaded Things →
        Automation JSON) into a brand-new RPA workflow."""
        db = _state["db"]
        user_id = (user.get("id") or user.get("user_id") or user.get("email") or "") if isinstance(user, dict) else getattr(user, "id", "")
        upload = await db.uploads.find_one({"id": upload_id, "user_id": user_id}, {"_id": 0})
        if not upload:
            raise HTTPException(status_code=404, detail="Upload not found")
        try:
            steps = json.loads(upload.get("automation_json") or "[]")
        except Exception:
            steps = []
        if not isinstance(steps, list) or not steps:
            raise HTTPException(status_code=400, detail="Upload has no recorded steps")
        nodes, edges = _convert_recorder_steps_to_flowchart(steps)
        wf_id = _new_id("wf")
        now = _now_iso()
        doc = {
            "id": wf_id,
            "owner_user_id": user_id,
            "name": upload.get("name") or "Imported Recording",
            "description": upload.get("description") or f"Auto-converted from recording • {len(steps)} steps",
            "nodes": nodes,
            "edges": edges,
            "settings": {"use_stealth": True, "headless": True},
            "variables": {},
            "is_active": True,
            "version": 1,
            "created_at": now,
            "updated_at": now,
            "source": "visual_recorder_upload",
            "source_upload_id": upload_id,
        }
        await db.rpa_workflows.insert_one(doc.copy())
        return _strip_id(doc)


    @router.get("/workflows")
    async def list_workflows(user=Depends(get_current_user)):
        db = _state["db"]
        user_id = (user.get("id") or user.get("user_id") or user.get("email") or "") if isinstance(user, dict) else getattr(user, "id", "")
        cursor = db.rpa_workflows.find(
            {"owner_user_id": user_id}, {"_id": 0}
        ).sort("updated_at", -1)
        return await cursor.to_list(length=500)

    @router.get("/workflows/{wf_id}")
    async def get_workflow(wf_id: str, user=Depends(get_current_user)):
        db = _state["db"]
        user_id = (user.get("id") or user.get("user_id") or user.get("email") or "") if isinstance(user, dict) else getattr(user, "id", "")
        doc = await db.rpa_workflows.find_one({"id": wf_id, "owner_user_id": user_id}, {"_id": 0})
        if not doc:
            raise HTTPException(status_code=404, detail="Workflow not found")
        return doc

    @router.patch("/workflows/{wf_id}")
    async def update_workflow(wf_id: str, payload: WorkflowUpdate, user=Depends(get_current_user)):
        db = _state["db"]
        user_id = (user.get("id") or user.get("user_id") or user.get("email") or "") if isinstance(user, dict) else getattr(user, "id", "")
        updates = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")
        updates["updated_at"] = _now_iso()
        # Bump version on structural changes
        if any(k in updates for k in ("nodes", "edges", "settings", "variables")):
            current = await db.rpa_workflows.find_one({"id": wf_id, "owner_user_id": user_id}, {"version": 1})
            if current:
                updates["version"] = int(current.get("version") or 1) + 1
        r = await db.rpa_workflows.update_one(
            {"id": wf_id, "owner_user_id": user_id}, {"$set": updates}
        )
        if r.matched_count == 0:
            raise HTTPException(status_code=404, detail="Workflow not found")
        doc = await db.rpa_workflows.find_one({"id": wf_id, "owner_user_id": user_id}, {"_id": 0})
        return doc

    @router.delete("/workflows/{wf_id}")
    async def delete_workflow(wf_id: str, user=Depends(get_current_user)):
        db = _state["db"]
        user_id = (user.get("id") or user.get("user_id") or user.get("email") or "") if isinstance(user, dict) else getattr(user, "id", "")
        r = await db.rpa_workflows.delete_one({"id": wf_id, "owner_user_id": user_id})
        if r.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Workflow not found")
        return {"deleted": True, "id": wf_id}

    @router.post("/workflows/{wf_id}/duplicate")
    async def duplicate_workflow(wf_id: str, user=Depends(get_current_user)):
        db = _state["db"]
        user_id = (user.get("id") or user.get("user_id") or user.get("email") or "") if isinstance(user, dict) else getattr(user, "id", "")
        src = await db.rpa_workflows.find_one({"id": wf_id, "owner_user_id": user_id}, {"_id": 0})
        if not src:
            raise HTTPException(status_code=404, detail="Workflow not found")
        new_doc = {**src}
        new_doc["id"] = _new_id("wf")
        new_doc["name"] = f"{src.get('name', 'Workflow')} (copy)"
        new_doc["created_at"] = _now_iso()
        new_doc["updated_at"] = _now_iso()
        new_doc["version"] = 1
        await db.rpa_workflows.insert_one(new_doc.copy())
        return _strip_id(new_doc)

    @router.get("/workflows/{wf_id}/export")
    async def export_workflow(wf_id: str, user=Depends(get_current_user)):
        db = _state["db"]
        user_id = (user.get("id") or user.get("user_id") or user.get("email") or "") if isinstance(user, dict) else getattr(user, "id", "")
        doc = await db.rpa_workflows.find_one({"id": wf_id, "owner_user_id": user_id}, {"_id": 0})
        if not doc:
            raise HTTPException(status_code=404, detail="Workflow not found")
        export = {
            "krexion_rpa_export": True,
            "format_version": 1,
            "exported_at": _now_iso(),
            "workflow": doc,
        }
        return export

    @router.post("/workflows/import")
    async def import_workflow(payload: Dict[str, Any] = Body(...), user=Depends(get_current_user)):
        db = _state["db"]
        user_id = (user.get("id") or user.get("user_id") or user.get("email") or "") if isinstance(user, dict) else getattr(user, "id", "")
        wf = payload.get("workflow") or payload
        if not isinstance(wf, dict) or not wf.get("name"):
            raise HTTPException(status_code=400, detail="Invalid workflow JSON")
        new_doc = {
            "id": _new_id("wf"),
            "owner_user_id": user_id,
            "name": wf.get("name") or "Imported Workflow",
            "description": wf.get("description") or "",
            "nodes": wf.get("nodes") or [],
            "edges": wf.get("edges") or [],
            "settings": wf.get("settings") or {},
            "variables": wf.get("variables") or {},
            "is_active": True,
            "version": 1,
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
        }
        await db.rpa_workflows.insert_one(new_doc.copy())
        return _strip_id(new_doc)

    # ── Runs ─────────────────────────────────────────────────────────
    @router.post("/workflows/{wf_id}/run")
    async def run_workflow(wf_id: str, payload: RunStartRequest, user=Depends(get_current_user)):
        db = _state["db"]
        user_id = (user.get("id") or user.get("user_id") or user.get("email") or "") if isinstance(user, dict) else getattr(user, "id", "")
        wf = await db.rpa_workflows.find_one({"id": wf_id, "owner_user_id": user_id}, {"_id": 0})
        if not wf:
            raise HTTPException(status_code=404, detail="Workflow not found")
        run_id = _new_id("run")
        run_doc = {
            "id": run_id,
            "workflow_id": wf_id,
            "workflow_name": wf.get("name", ""),
            "workflow_version": wf.get("version", 1),
            "owner_user_id": user_id,
            "status": "queued",
            "progress": 0,
            "step_results": [],
            "variables": payload.variables or {},
            "started_at": _now_iso(),
            "finished_at": None,
            "error_message": None,
        }
        await db.rpa_runs.insert_one(run_doc.copy())
        # Spawn the executor in the background
        task = asyncio.create_task(
            _execute_workflow(run_id, wf, payload.variables or {}, payload.headless)
        )
        _state["runs"][run_id] = {"task": task, "started_at": time.time(), "events": [], "latest_screenshot": None}
        return {"run_id": run_id, "status": "queued"}

    @router.get("/runs")
    async def list_runs(user=Depends(get_current_user), limit: int = Query(50, le=200)):
        db = _state["db"]
        user_id = (user.get("id") or user.get("user_id") or user.get("email") or "") if isinstance(user, dict) else getattr(user, "id", "")
        cursor = db.rpa_runs.find({"owner_user_id": user_id}, {"_id": 0}).sort("started_at", -1).limit(limit)
        return await cursor.to_list(length=limit)

    @router.get("/runs/{run_id}")
    async def get_run(run_id: str, user=Depends(get_current_user)):
        db = _state["db"]
        user_id = (user.get("id") or user.get("user_id") or user.get("email") or "") if isinstance(user, dict) else getattr(user, "id", "")
        doc = await db.rpa_runs.find_one({"id": run_id, "owner_user_id": user_id}, {"_id": 0})
        if not doc:
            raise HTTPException(status_code=404, detail="Run not found")
        return doc

    @router.post("/runs/{run_id}/stop")
    async def stop_run(run_id: str, user=Depends(get_current_user)):
        db = _state["db"]
        user_id = (user.get("id") or user.get("user_id") or user.get("email") or "") if isinstance(user, dict) else getattr(user, "id", "")
        st = _state["runs"].get(run_id)
        if st and st.get("task"):
            st["task"].cancel()
        await db.rpa_runs.update_one(
            {"id": run_id, "owner_user_id": user_id},
            {"$set": {"status": "cancelled", "finished_at": _now_iso()}},
        )
        return {"cancelled": True}

    @router.get("/runs/{run_id}/live")
    async def run_live(run_id: str, user=Depends(get_current_user)):
        """Return latest in-memory events for a running task."""
        db = _state["db"]
        user_id = (user.get("id") or user.get("user_id") or user.get("email") or "") if isinstance(user, dict) else getattr(user, "id", "")
        doc = await db.rpa_runs.find_one({"id": run_id, "owner_user_id": user_id}, {"_id": 0, "step_results": 1, "status": 1, "progress": 1, "error_message": 1, "variables": 1})
        if not doc:
            raise HTTPException(status_code=404, detail="Run not found")
        st = _state["runs"].get(run_id, {})
        return {
            "status": doc.get("status"),
            "progress": doc.get("progress", 0),
            "events": (doc.get("step_results") or [])[-50:],
            "error_message": doc.get("error_message"),
            "variables": doc.get("variables") or {},
            "has_screenshot": bool(st.get("latest_screenshot")),
        }

    @router.get("/runs/{run_id}/screenshot")
    async def run_screenshot(run_id: str, user=Depends(get_current_user)):
        from fastapi.responses import Response
        # Allow query param `t=` to pass the token (for <img src>) — already
        # validated via Depends above
        st = _state["runs"].get(run_id, {})
        shot = st.get("latest_screenshot")
        if not shot:
            return Response(status_code=204)
        return Response(content=shot, media_type="image/jpeg",
                       headers={"Cache-Control": "no-store"})

    # ── Catalog / templates ──────────────────────────────────────────
    @router.get("/node-catalog")
    async def node_catalog(user=Depends(get_current_user)):
        return NODE_CATALOG

    @router.get("/templates")
    async def list_templates(user=Depends(get_current_user)):
        db = _state["db"]
        cursor = db.rpa_templates.find({"is_public": True}, {"_id": 0}).sort("created_at", -1)
        return await cursor.to_list(length=200)

    return router


# ── Variable substitution ─────────────────────────────────────────────
_VAR_RE = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_.]*)\s*\}\}")


def _substitute(value: Any, vars: Dict[str, Any]) -> Any:
    if isinstance(value, str):
        def _sub(m):
            key = m.group(1)
            if "." in key:
                # path access a.b.c
                parts = key.split(".")
                cur: Any = vars
                for p in parts:
                    if isinstance(cur, dict):
                        cur = cur.get(p)
                    else:
                        return ""
                    if cur is None:
                        return ""
                return str(cur)
            return str(vars.get(key, ""))
        return _VAR_RE.sub(_sub, value)
    if isinstance(value, list):
        return [_substitute(v, vars) for v in value]
    if isinstance(value, dict):
        return {k: _substitute(v, vars) for k, v in value.items()}
    return value


def _eval_condition(variable_val: Any, condition: str, expected: Any) -> bool:
    cond = (condition or "equals").lower()
    if cond == "exists":
        return variable_val is not None and variable_val != ""
    if cond == "not_exists":
        return variable_val is None or variable_val == ""
    try:
        if cond in ("equals", "=="):
            return str(variable_val) == str(expected)
        if cond in ("not_equals", "!="):
            return str(variable_val) != str(expected)
        if cond in ("greater_than", ">"):
            return float(variable_val) > float(expected)
        if cond in ("greater_or_equal", ">="):
            return float(variable_val) >= float(expected)
        if cond in ("less_than", "<"):
            return float(variable_val) < float(expected)
        if cond in ("less_or_equal", "<="):
            return float(variable_val) <= float(expected)
        if cond == "contains":
            return str(expected) in str(variable_val)
        if cond == "not_contains":
            return str(expected) not in str(variable_val)
        if cond == "one_of":
            options = [s.strip() for s in str(expected).split(",")]
            return str(variable_val) in options
        if cond == "regex":
            return bool(re.search(str(expected), str(variable_val)))
    except Exception:
        return False
    return False


class _ExitLoop(Exception):
    """Internal signal to break out of the innermost loop."""
    pass


# ── Workflow executor (Playwright-based) ──────────────────────────────
async def _execute_workflow(run_id: str, wf: dict, override_vars: dict, headless_override: Optional[bool]):
    """Run a workflow end-to-end. Updates rpa_runs doc in MongoDB.

    Builds a node-id → node dict and walks edges. The visual flowchart
    is a DAG with optional branches and loop bodies (nodes contain
    `body` and `branches` lists of child node ids).
    """
    db = _state["db"]
    runtime: Dict[str, Any] = _state["runs"].setdefault(run_id, {})
    runtime["latest_screenshot"] = None

    settings = wf.get("settings") or {}
    headless = settings.get("headless", True) if headless_override is None else headless_override
    viewport = settings.get("viewport") or {"width": 1280, "height": 800}

    # Resolve initial variables (defaults + overrides)
    var_defs = wf.get("variables") or {}
    defaults = {}
    if isinstance(var_defs, dict):
        # Accept either {"name": "value"} or {"globals": [{"name":..., "default":...}]}
        if "globals" in var_defs and isinstance(var_defs["globals"], list):
            for g in var_defs["globals"]:
                if isinstance(g, dict) and g.get("name"):
                    defaults[g["name"]] = g.get("default", "")
        else:
            defaults.update(var_defs)
    variables: Dict[str, Any] = {**defaults, **(override_vars or {})}

    # Build node map and find start (no incoming edges)
    nodes_list = wf.get("nodes") or []
    edges = wf.get("edges") or []
    node_map: Dict[str, dict] = {n["id"]: n for n in nodes_list if isinstance(n, dict) and n.get("id")}
    incoming: Dict[str, List[str]] = {nid: [] for nid in node_map}
    outgoing: Dict[str, List[Tuple[str, Optional[str]]]] = {nid: [] for nid in node_map}
    for e in edges:
        if isinstance(e, dict):
            src = e.get("from") or e.get("source")
            dst = e.get("to") or e.get("target")
            label = e.get("label") or e.get("sourceHandle")
            if src in node_map and dst in node_map:
                incoming.setdefault(dst, []).append(src)
                outgoing.setdefault(src, []).append((dst, label))
    start_ids = [nid for nid in node_map if not incoming.get(nid)]
    if not start_ids and node_map:
        start_ids = [list(node_map.keys())[0]]

    await db.rpa_runs.update_one(
        {"id": run_id}, {"$set": {"status": "running", "started_at": _now_iso()}}
    )

    # Try to load Playwright
    playwright = browser = context = page = None
    try:
        from playwright.async_api import async_playwright

        async def push_event(event: dict):
            event["t"] = _now_iso()
            await db.rpa_runs.update_one({"id": run_id}, {"$push": {"step_results": event}})

        async def take_screenshot():
            nonlocal page
            if page is None:
                return
            try:
                buf = await page.screenshot(type="jpeg", quality=55, full_page=False)
                runtime["latest_screenshot"] = buf
            except Exception:
                pass

        # ── Per-node executor ───────────────────────────────────────
        async def exec_node(node_id: str, depth: int = 0) -> None:
            nonlocal page, context, browser
            if depth > 200:
                raise RuntimeError("Maximum nesting depth exceeded")
            node = node_map.get(node_id)
            if not node:
                return
            ntype = (node.get("type") or "").lower()
            raw_params = node.get("params") or {}
            params = _substitute(raw_params, variables)
            on_error = node.get("on_error") or "skip"
            step_no = len((await db.rpa_runs.find_one({"id": run_id}, {"step_results": 1}) or {}).get("step_results") or [])
            await push_event({"node_id": node_id, "type": ntype, "status": "running", "params": params, "step": step_no + 1})

            try:
                # ── Web actions ─────────────────────────────────────
                if ntype == "goto":
                    url = params.get("url") or ""
                    if not url:
                        raise ValueError("goto requires url")
                    if page is None:
                        await _ensure_browser()
                    await page.goto(url, timeout=int(params.get("timeout") or 60000))
                    await page.wait_for_load_state("domcontentloaded", timeout=30000)
                elif ntype == "new_tab":
                    await _ensure_browser()
                    new_page = await context.new_page()
                    if params.get("url"):
                        await new_page.goto(params["url"])
                    page = new_page
                elif ntype == "close_tab":
                    if page:
                        await page.close()
                        pages = context.pages if context else []
                        page = pages[-1] if pages else None
                elif ntype == "close_other_tabs":
                    if context and page:
                        for p in list(context.pages):
                            if p is not page:
                                await p.close()
                elif ntype == "switch_tab":
                    if context:
                        by = (params.get("by") or "index").lower()
                        v = params.get("value")
                        for p in context.pages:
                            if by == "index" and context.pages.index(p) == int(v or 0):
                                page = p; break
                            if by == "url_contains" and v and v in p.url:
                                page = p; break
                            if by == "title_contains" and v and v in (await p.title()):
                                page = p; break
                elif ntype == "refresh":
                    if page: await page.reload()
                elif ntype == "go_back":
                    if page: await page.go_back()
                elif ntype == "go_forward":
                    if page: await page.go_forward()
                elif ntype == "click":
                    if not page: raise RuntimeError("No active page")
                    sel = params.get("selector") or ""
                    if not sel: raise ValueError("click requires selector")
                    button = params.get("button") or "left"
                    count = int(params.get("count") or 1)
                    await page.click(sel, button=button, click_count=count, timeout=int(params.get("timeout") or 15000))
                elif ntype == "random_click":
                    if not page: raise RuntimeError("No active page")
                    selectors = params.get("selectors") or []
                    if isinstance(selectors, str):
                        selectors = [s.strip() for s in selectors.split(",") if s.strip()]
                    if not selectors: raise ValueError("random_click requires selectors")
                    chosen = random.choice(selectors)
                    await page.click(chosen, timeout=int(params.get("timeout") or 15000))
                    variables["_last_random_choice"] = chosen
                elif ntype == "checkbox":
                    if not page: raise RuntimeError("No active page")
                    sel = params.get("selector") or ""
                    action = (params.get("action") or "check").lower()
                    if action == "check":
                        await page.check(sel, timeout=int(params.get("timeout") or 15000))
                    elif action == "uncheck":
                        await page.uncheck(sel, timeout=int(params.get("timeout") or 15000))
                    else:
                        await page.click(sel, timeout=int(params.get("timeout") or 15000))
                elif ntype == "hover":
                    if not page: raise RuntimeError("No active page")
                    await page.hover(params.get("selector") or "")
                elif ntype == "focus":
                    if not page: raise RuntimeError("No active page")
                    await page.focus(params.get("selector") or "")
                elif ntype == "select":
                    if not page: raise RuntimeError("No active page")
                    sel = params.get("selector") or ""
                    val = params.get("value") or ""
                    match = (params.get("match_by") or "value").lower()
                    if match == "label":
                        await page.select_option(sel, label=str(val))
                    elif match == "index":
                        await page.select_option(sel, index=int(val))
                    else:
                        await page.select_option(sel, value=str(val))
                elif ntype == "random_select":
                    if not page: raise RuntimeError("No active page")
                    sel = params.get("selector") or ""
                    opts = await page.eval_on_selector_all(f"{sel} option", "els => els.map(o => o.value).filter(v => v)")
                    if not opts: raise RuntimeError("No options found")
                    chosen = random.choice(opts)
                    await page.select_option(sel, value=chosen)
                    variables["_last_random_select"] = chosen
                elif ntype == "fill":
                    if not page: raise RuntimeError("No active page")
                    sel = params.get("selector") or ""
                    val = str(params.get("value") or "")
                    clear_first = bool(params.get("clear_first", True))
                    interval = int(params.get("type_interval_ms") or 0)
                    if clear_first:
                        try:
                            await page.fill(sel, "")
                        except Exception:
                            pass
                    if interval > 0:
                        await page.click(sel)
                        await page.type(sel, val, delay=interval)
                    else:
                        await page.fill(sel, val)
                elif ntype == "scroll":
                    if not page: raise RuntimeError("No active page")
                    distance = params.get("distance") or "bottom"
                    if isinstance(distance, str):
                        if distance == "top":
                            await page.evaluate("window.scrollTo({top:0, behavior:'auto'})")
                        elif distance == "middle":
                            await page.evaluate("window.scrollTo({top:document.body.scrollHeight/2, behavior:'auto'})")
                        elif distance == "bottom":
                            await page.evaluate("window.scrollTo({top:document.body.scrollHeight, behavior:'auto'})")
                        else:
                            try:
                                await page.evaluate(f"window.scrollBy(0, {int(distance)})")
                            except Exception:
                                pass
                    else:
                        await page.evaluate(f"window.scrollBy(0, {int(distance)})")
                elif ntype == "input_file":
                    if not page: raise RuntimeError("No active page")
                    await page.set_input_files(params.get("selector") or "", params.get("file_url") or "")
                elif ntype == "screenshot" or ntype == "mark_final":
                    if not page: raise RuntimeError("No active page")
                    buf = await page.screenshot(type="png", full_page=bool(params.get("full_page")))
                    b64 = base64.b64encode(buf).decode()
                    name = params.get("name") or ("Mark Final" if ntype == "mark_final" else f"Screenshot {step_no+1}")
                    variables[f"_screenshot_{step_no+1}"] = b64[:200] + "..."  # truncate for storage
                    await push_event({"node_id": node_id, "type": "screenshot_data", "status": "info", "name": name, "data_url": f"data:image/png;base64,{b64}"})
                elif ntype == "evaluate":
                    if not page: raise RuntimeError("No active page")
                    script = params.get("script") or "1"
                    result = await page.evaluate(script)
                    save_to = params.get("save_to")
                    if save_to:
                        variables[save_to] = result
                # ── Keyboard ───────────────────────────────────────
                elif ntype == "press":
                    if not page: raise RuntimeError("No active page")
                    await page.keyboard.press(params.get("key") or "Enter")
                elif ntype == "key_combo":
                    if not page: raise RuntimeError("No active page")
                    combo = params.get("combo") or "Control+A"
                    await page.keyboard.press(combo)
                # ── Waits ─────────────────────────────────────────
                elif ntype == "wait":
                    rmin = params.get("random_min")
                    rmax = params.get("random_max")
                    if rmin and rmax:
                        ms = random.randint(int(rmin), int(rmax))
                    else:
                        ms = int(params.get("ms") or 1000)
                    await asyncio.sleep(ms / 1000.0)
                elif ntype == "wait_for_selector":
                    if not page: raise RuntimeError("No active page")
                    await page.wait_for_selector(params.get("selector") or "", state=params.get("state") or "visible", timeout=int(params.get("timeout") or 15000))
                elif ntype == "wait_for_request":
                    if not page: raise RuntimeError("No active page")
                    async with page.expect_response(lambda r: params.get("url_pattern", "") in r.url, timeout=int(params.get("timeout") or 30000)):
                        pass
                elif ntype == "wait_for_load":
                    if not page: raise RuntimeError("No active page")
                    await page.wait_for_load_state(params.get("state") or "domcontentloaded", timeout=int(params.get("timeout") or 30000))
                elif ntype == "wait_for_text":
                    if not page: raise RuntimeError("No active page")
                    txt = params.get("text") or ""
                    timeout = int(params.get("timeout") or 15000)
                    deadline = time.time() + timeout / 1000.0
                    while time.time() < deadline:
                        body = await page.content()
                        if txt in body:
                            break
                        await asyncio.sleep(0.5)
                elif ntype == "wait_for_url":
                    if not page: raise RuntimeError("No active page")
                    contains = params.get("contains") or ""
                    timeout = int(params.get("timeout") or 15000)
                    deadline = time.time() + timeout / 1000.0
                    while time.time() < deadline:
                        if contains in page.url:
                            break
                        await asyncio.sleep(0.5)
                # ── Get Data ───────────────────────────────────────
                elif ntype == "get_url":
                    if not page: raise RuntimeError("No active page")
                    mode = (params.get("mode") or "full").lower()
                    url = page.url
                    if mode == "domain":
                        from urllib.parse import urlparse
                        url = urlparse(url).netloc
                    elif mode == "parameter":
                        from urllib.parse import urlparse, parse_qs
                        qs = parse_qs(urlparse(url).query)
                        url = (qs.get(params.get("name") or "", [""]) or [""])[0]
                    if params.get("save_to"):
                        variables[params["save_to"]] = url
                elif ntype == "get_element":
                    if not page: raise RuntimeError("No active page")
                    sel = params.get("selector") or ""
                    extraction = (params.get("extraction") or "text").lower()
                    if extraction == "text":
                        v = await page.text_content(sel)
                    elif extraction == "html":
                        v = await page.inner_html(sel)
                    elif extraction == "value":
                        v = await page.input_value(sel)
                    elif extraction == "attribute":
                        v = await page.get_attribute(sel, params.get("attribute") or "value")
                    else:
                        v = await page.text_content(sel)
                    if params.get("save_to"):
                        variables[params["save_to"]] = v
                elif ntype == "get_cookies":
                    if context:
                        ck = await context.cookies()
                        if params.get("save_to"):
                            variables[params["save_to"]] = ck
                elif ntype == "clear_cookies":
                    if context:
                        await context.clear_cookies()
                # ── Data processing ─────────────────────────────────
                elif ntype == "set_var":
                    name = params.get("name") or ""
                    if name:
                        variables[name] = params.get("value")
                elif ntype == "regex_extract":
                    src = str(params.get("input") or "")
                    pat = params.get("pattern") or ""
                    m = re.search(pat, src)
                    if m and params.get("save_to"):
                        variables[params["save_to"]] = m.group(1) if m.groups() else m.group(0)
                elif ntype == "to_json":
                    src = params.get("input") or ""
                    try:
                        v = json.loads(src) if isinstance(src, str) else src
                        if params.get("save_to"):
                            variables[params["save_to"]] = v
                    except Exception:
                        pass
                elif ntype == "extract_field":
                    src = params.get("input")
                    key = params.get("key") or ""
                    cur: Any = src
                    for part in str(key).replace("[", ".").replace("]", "").split("."):
                        if not part: continue
                        try:
                            if isinstance(cur, list):
                                cur = cur[int(part)]
                            elif isinstance(cur, dict):
                                cur = cur.get(part)
                            else:
                                cur = None
                                break
                        except Exception:
                            cur = None; break
                    if params.get("save_to"):
                        variables[params["save_to"]] = cur
                elif ntype == "random_extract":
                    src = params.get("input")
                    if isinstance(src, list) and src:
                        variables[params.get("save_to", "_random")] = random.choice(src)
                elif ntype == "math":
                    expr = str(params.get("expression") or "0")
                    safe_globals = {"__builtins__": {}}
                    safe_locals = {k: v for k, v in variables.items() if isinstance(v, (int, float, str))}
                    try:
                        result = eval(expr, safe_globals, safe_locals)  # noqa: S307
                        if params.get("save_to"):
                            variables[params["save_to"]] = result
                    except Exception:
                        pass
                # ── Control flow ────────────────────────────────────
                elif ntype == "if":
                    var = params.get("variable") or ""
                    cond = params.get("condition") or "equals"
                    expected = params.get("value")
                    matched = _eval_condition(variables.get(var), cond, expected)
                    branches = node.get("branches") or {}
                    next_ids = branches.get("true" if matched else "false") or []
                    for cid in next_ids:
                        await exec_node(cid, depth + 1)
                elif ntype == "for_loop_times":
                    times = int(params.get("times") or 1)
                    save_index = params.get("save_index") or "_index"
                    for i in range(times):
                        variables[save_index] = i
                        try:
                            for cid in node.get("body") or []:
                                await exec_node(cid, depth + 1)
                        except _ExitLoop:
                            break
                elif ntype == "for_loop_data":
                    data = variables.get(params.get("data_var") or "") or []
                    save_item = params.get("save_item") or "_item"
                    save_index = params.get("save_index") or "_index"
                    if isinstance(data, list):
                        for i, item in enumerate(data):
                            variables[save_item] = item
                            variables[save_index] = i
                            try:
                                for cid in node.get("body") or []:
                                    await exec_node(cid, depth + 1)
                            except _ExitLoop:
                                break
                elif ntype == "while_loop":
                    var = params.get("variable") or ""
                    cond = params.get("condition") or "equals"
                    expected = params.get("value")
                    max_iter = int(params.get("max_iterations") or 1000)
                    i = 0
                    while _eval_condition(variables.get(var), cond, expected) and i < max_iter:
                        try:
                            for cid in node.get("body") or []:
                                await exec_node(cid, depth + 1)
                        except _ExitLoop:
                            break
                        i += 1
                elif ntype == "exit_loop":
                    raise _ExitLoop()
                elif ntype == "throw_error":
                    raise RuntimeError(params.get("message") or "Workflow error")
                elif ntype == "quit_browser":
                    if browser:
                        try:
                            await browser.close()
                        except Exception:
                            pass
                        browser = None
                        page = None
                        context = None
                # ── Third party ────────────────────────────────────
                elif ntype == "openai":
                    res = await _exec_openai_node(params)
                    if params.get("save_to"):
                        variables[params["save_to"]] = res
                elif ntype == "http_request":
                    res = await _exec_http_node(params)
                    if params.get("save_to"):
                        variables[params["save_to"]] = res
                elif ntype == "google_sheets":
                    res = await _exec_gsheets_node(params)
                    if params.get("save_to"):
                        variables[params["save_to"]] = res
                elif ntype == "captcha_2captcha":
                    # Now supports 3 providers via the unified solver:
                    # `provider`: "2captcha" | "anticaptcha" | "capmonster"
                    res = await _exec_universal_captcha_node(params, page)
                    if params.get("save_to"):
                        variables[params["save_to"]] = res
                elif ntype == "apply_workflow":
                    sub_id = params.get("workflow_id")
                    if sub_id:
                        sub = await db.rpa_workflows.find_one({"id": sub_id}, {"_id": 0})
                        if sub:
                            # Inherit current variables
                            sub_nodes = sub.get("nodes") or []
                            sub_edges = sub.get("edges") or []
                            sub_map = {n["id"]: n for n in sub_nodes if isinstance(n, dict)}
                            sub_incoming = {nid: [] for nid in sub_map}
                            for e in sub_edges:
                                if isinstance(e, dict):
                                    dst = e.get("to") or e.get("target")
                                    src = e.get("from") or e.get("source")
                                    if src and dst:
                                        sub_incoming.setdefault(dst, []).append(src)
                            sub_starts = [nid for nid in sub_map if not sub_incoming.get(nid)]
                            old_map = node_map
                            try:
                                node_map.update(sub_map)
                                for sid in sub_starts:
                                    await exec_node(sid, depth + 1)
                            finally:
                                pass
                else:
                    await push_event({"node_id": node_id, "type": ntype, "status": "skipped", "reason": f"Unknown node type: {ntype}"})

                # Update screenshot after each web/data action
                if ntype in ("goto", "click", "fill", "scroll", "press", "refresh", "go_back", "checkbox", "hover", "select", "screenshot", "mark_final"):
                    await take_screenshot()

                await push_event({"node_id": node_id, "type": ntype, "status": "ok", "step": step_no + 1})

                # ── Live variables snapshot (for Variables Inspector) ──
                # Update only the small `variables` field on each step so
                # the UI can stream values as they're set.
                if ntype in ("set_var", "get_url", "get_element", "regex_extract",
                              "to_json", "extract_field", "random_extract", "math",
                              "random_click", "random_select", "evaluate", "openai",
                              "http_request", "google_sheets", "captcha_2captcha",
                              "for_loop_times", "for_loop_data", "while_loop"):
                    try:
                        # Only store JSON-serializable subset
                        snap = {}
                        for k, v in variables.items():
                            try:
                                json.dumps(v)
                                snap[k] = v
                            except Exception:
                                snap[k] = str(v)[:200]
                        await db.rpa_runs.update_one({"id": run_id}, {"$set": {"variables": snap}})
                    except Exception:
                        pass

            except _ExitLoop:
                raise
            except asyncio.CancelledError:
                raise
            except Exception as ex:
                msg = str(ex)
                await push_event({"node_id": node_id, "type": ntype, "status": "error", "error": msg, "on_error": on_error, "step": step_no + 1})
                if on_error == "stop":
                    raise

            # Follow outgoing edges (only when this node isn't a container)
            if ntype not in ("if", "for_loop_times", "for_loop_data", "while_loop"):
                for next_id, _label in outgoing.get(node_id, []):
                    await exec_node(next_id, depth + 1)

        async def _ensure_browser():
            nonlocal playwright, browser, context, page
            if browser is None:
                playwright = await async_playwright().start()
                # ── Try stealth launch first (central anti_detect_engine)
                # so RPA Studio workflows get the SAME 35+ anti-detect
                # patches as Real User Traffic (canvas/audio/WebGL/WebRTC/
                # webdriver/Jornaya/TrustedForm/mobile sensors/CDP …).
                # Falls back to vanilla launch only if stealth path fails.
                use_stealth = bool(settings.get("use_stealth", True))
                if use_stealth:
                    try:
                        from anti_detect_engine import launch_stealth_session as _ade_launch  # type: ignore
                        browser, context, page = await _ade_launch(
                            playwright, headless=headless,
                        )
                        logger.info("RPA run %s: stealth session launched", run_id)
                        return
                    except Exception as _ade_err:
                        logger.warning(
                            "RPA run %s: stealth launch failed (%s) — using vanilla",
                            run_id, _ade_err,
                        )
                # Vanilla fallback
                browser = await playwright.chromium.launch(
                    headless=headless,
                    args=["--no-sandbox", "--disable-dev-shm-usage"],
                )
                context = await browser.new_context(viewport=viewport)
                page = await context.new_page()

        # Start at root(s); but if first start is a "goto" with starting_url override, apply
        for sid in start_ids:
            # Visit only "root" nodes; container body/branches are walked inline.
            await exec_node(sid)

        await db.rpa_runs.update_one(
            {"id": run_id},
            {"$set": {"status": "completed", "finished_at": _now_iso(), "progress": 100, "variables": variables}},
        )

    except asyncio.CancelledError:
        await db.rpa_runs.update_one(
            {"id": run_id},
            {"$set": {"status": "cancelled", "finished_at": _now_iso()}},
        )
    except Exception as e:
        logger.exception("RPA run failed: %s", run_id)
        await db.rpa_runs.update_one(
            {"id": run_id},
            {"$set": {"status": "failed", "finished_at": _now_iso(), "error_message": str(e)}},
        )
    finally:
        try:
            if not settings.get("browser_keep_open"):
                if browser:
                    await browser.close()
                if playwright:
                    await playwright.stop()
        except Exception:
            pass


# ── Third-party node helpers ──────────────────────────────────────────
async def _exec_openai_node(params: dict) -> Any:
    """Use Emergent LLM key via emergentintegrations if available."""
    provider = (params.get("provider") or "openai").lower()
    model = params.get("model") or ("gpt-4o-mini" if provider == "openai" else
                                     "claude-haiku-4-5-20251001" if provider == "anthropic" else
                                     "gemini-2.0-flash")
    prompt = params.get("prompt") or ""
    if not prompt:
        return ""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage  # type: ignore
        api_key = os.environ.get("EMERGENT_LLM_KEY") or os.environ.get("UNIVERSAL_LLM_KEY") or ""
        if not api_key:
            return "[Emergent LLM key missing]"
        chat = LlmChat(api_key=api_key, session_id=_new_id("rpa"), system_message="You are an RPA helper.")
        chat = chat.with_model(provider, model)
        res = await chat.send_message(UserMessage(text=prompt))
        return str(res)
    except Exception as e:
        logger.warning("OpenAI node failed: %s", e)
        return f"[LLM error: {e}]"


async def _exec_http_node(params: dict) -> Any:
    import httpx
    method = (params.get("method") or "GET").upper()
    url = params.get("url") or ""
    headers = params.get("headers") or {}
    body = params.get("body")
    if not url:
        return {"error": "no url"}
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            if isinstance(headers, str):
                try:
                    headers = json.loads(headers)
                except Exception:
                    headers = {}
            kwargs = {"headers": headers}
            if body is not None and method in ("POST", "PUT", "PATCH"):
                if isinstance(body, (dict, list)):
                    kwargs["json"] = body
                else:
                    kwargs["content"] = str(body)
            r = await client.request(method, url, **kwargs)
            try:
                return r.json()
            except Exception:
                return r.text
    except Exception as e:
        return {"error": str(e)}


async def _exec_gsheets_node(params: dict) -> Any:
    """Hand off to gsheet_writer if available."""
    try:
        import gsheet_writer  # type: ignore
        op = (params.get("operation") or "read").lower()
        sheet_id = params.get("sheet_id") or ""
        rng = params.get("range") or "A1"
        values = params.get("values")
        if op == "write" and values is not None:
            # gsheet_writer has its own API surface; this is a best-effort
            # adapter — actual call signature depends on existing helper.
            return {"ok": True, "operation": op, "note": "Use the dedicated Save-to-GSheet step inside RUT for now."}
        return {"ok": True, "operation": op, "note": "Read implementation pending"}
    except ImportError:
        return {"error": "gsheet_writer not available"}


async def _exec_universal_captcha_node(params: dict, page) -> Any:
    """Multi-provider captcha solver. Auto-discovers sitekey from page,
    routes to 2Captcha / AntiCaptcha / CapMonster per `provider` param,
    and injects solved token into the page so the form can submit.
    Supported provider values: 2captcha | anticaptcha | capmonster
    Supported captcha_type: recaptcha_v2 | recaptcha_v3 | hcaptcha |
                            cloudflare_turnstile | image
    """
    provider = (params.get("provider") or "2captcha").lower()
    api_key = params.get("api_key") or ""
    captcha_type = (params.get("captcha_type") or "recaptcha_v2").lower()
    if not api_key:
        return {"error": "api_key required"}
    if not page:
        return {"error": "no active page"}
    try:
        page_url = page.url
        if captcha_type in ("recaptcha_v2", "recaptcha_v3"):
            sitekey = await page.evaluate("""
                () => { const e=document.querySelector('[data-sitekey]');
                  if(e) return e.getAttribute('data-sitekey');
                  const i=document.querySelector('iframe[src*="recaptcha"]');
                  if(i){const u=new URL(i.src);return u.searchParams.get('k');}
                  return null; }""")
        elif captcha_type == "hcaptcha":
            sitekey = await page.evaluate("""
                () => { const e=document.querySelector('[data-sitekey]');
                  if(e) return e.getAttribute('data-sitekey');
                  const i=document.querySelector('iframe[src*="hcaptcha"]');
                  if(i){const u=new URL(i.src);return u.searchParams.get('sitekey');}
                  return null; }""")
        elif captcha_type == "cloudflare_turnstile":
            sitekey = await page.evaluate("""
                () => { const e=document.querySelector('.cf-turnstile,[data-sitekey]');
                  return e ? (e.getAttribute('data-sitekey')||e.getAttribute('data-key')) : null; }""")
        else:
            sitekey = params.get("sitekey")
    except Exception as e:
        return {"error": f"sitekey discovery: {e}"}
    if not sitekey and captcha_type != "image":
        return {"error": "sitekey not found"}

    try:
        from advanced_anti_detect import solve_captcha_universal
    except Exception as e:
        return {"error": f"engine: {e}"}
    res = await solve_captcha_universal(
        provider=provider, api_key=api_key, captcha_type=captcha_type,
        sitekey=sitekey or "", page_url=page_url,
        action=params.get("action"), min_score=float(params.get("min_score") or 0.5),
        image_base64=params.get("image_base64"),
    )
    if not res.get("ok"):
        return res
    token = res["token"]
    try:
        if captcha_type.startswith("recaptcha"):
            await page.evaluate(f"""
                const ta=document.getElementById('g-recaptcha-response')||document.querySelector('textarea[name="g-recaptcha-response"]');
                if(ta){{ta.value='{token}';ta.innerHTML='{token}';}}
                if(window.___grecaptcha_cfg){{try{{window.___grecaptcha_cfg.clients[0].callback('{token}');}}catch(e){{}}}}""")
        elif captcha_type == "hcaptcha":
            await page.evaluate(f"""
                document.querySelectorAll('textarea[name="h-captcha-response"],textarea[name="g-recaptcha-response"]').forEach(t=>{{t.value='{token}';t.innerHTML='{token}';}});""")
        elif captcha_type == "cloudflare_turnstile":
            await page.evaluate(f"""
                document.querySelectorAll('input[name="cf-turnstile-response"]').forEach(t=>{{t.value='{token}';}});""")
    except Exception as e:
        logger.warning(f"token inject: {e}")
    return {"ok": True, "token": token, "provider": provider}


async def _exec_2captcha_node(params: dict, page) -> Any:
    """Real 2Captcha integration. Supports:
      • recaptcha_v2  (uses g-recaptcha-response token injection)
      • recaptcha_v3  (returns token; caller injects)
      • hcaptcha
      • cloudflare_turnstile
      • image          (base64 captcha image -> text)

    Requires the user to provide their 2Captcha API key in params.
    The solved token is automatically injected into the page's
    `g-recaptcha-response` / `h-captcha-response` / `cf-turnstile-response`
    textarea so the form is ready to submit.
    """
    import httpx as _httpx
    api_key = params.get("api_key") or ""
    captcha_type = (params.get("captcha_type") or "recaptcha_v2").lower()
    if not api_key:
        return {"error": "2captcha api_key required"}
    if not page:
        return {"error": "no active page"}

    # Step 1: Discover the sitekey + page URL from the current page
    try:
        page_url = page.url
        if captcha_type in ("recaptcha_v2", "recaptcha_v3"):
            sitekey = await page.evaluate("""
                () => {
                  const el = document.querySelector('[data-sitekey]');
                  if (el) return el.getAttribute('data-sitekey');
                  const iframe = document.querySelector('iframe[src*="recaptcha"]');
                  if (iframe) { const u = new URL(iframe.src); return u.searchParams.get('k'); }
                  return null;
                }
            """)
        elif captcha_type == "hcaptcha":
            sitekey = await page.evaluate("""
                () => {
                  const el = document.querySelector('[data-sitekey]');
                  if (el) return el.getAttribute('data-sitekey');
                  const iframe = document.querySelector('iframe[src*="hcaptcha"]');
                  if (iframe) { const u = new URL(iframe.src); return u.searchParams.get('sitekey'); }
                  return null;
                }
            """)
        elif captcha_type == "cloudflare_turnstile":
            sitekey = await page.evaluate("""
                () => {
                  const el = document.querySelector('.cf-turnstile,[data-sitekey]');
                  return el ? (el.getAttribute('data-sitekey') || el.getAttribute('data-key')) : null;
                }
            """)
        else:
            sitekey = params.get("sitekey")
    except Exception as e:
        return {"error": f"sitekey discovery failed: {e}"}

    if not sitekey and captcha_type != "image":
        return {"error": "sitekey not found on page"}

    # Step 2: Submit to 2Captcha
    submit_params: Dict[str, Any] = {"key": api_key, "json": 1, "pageurl": page_url, "sitekey": sitekey}
    if captcha_type == "recaptcha_v2":
        submit_params["method"] = "userrecaptcha"
    elif captcha_type == "recaptcha_v3":
        submit_params["method"] = "userrecaptcha"
        submit_params["version"] = "v3"
        submit_params["action"] = params.get("action") or "verify"
        submit_params["min_score"] = params.get("min_score") or 0.5
    elif captcha_type == "hcaptcha":
        submit_params["method"] = "hcaptcha"
    elif captcha_type == "cloudflare_turnstile":
        submit_params["method"] = "turnstile"
    elif captcha_type == "image":
        submit_params["method"] = "base64"
        submit_params["body"] = params.get("image_base64") or ""

    try:
        async with _httpx.AsyncClient(timeout=120) as client:
            r = await client.get("https://2captcha.com/in.php", params=submit_params)
            data = r.json()
            if data.get("status") != 1:
                return {"error": f"2captcha submit failed: {data.get('request')}"}
            captcha_id = data["request"]

            # Step 3: Poll for result (max 120s)
            for _ in range(40):
                await asyncio.sleep(3.0)
                rr = await client.get("https://2captcha.com/res.php", params={
                    "key": api_key, "action": "get", "id": captcha_id, "json": 1
                })
                rd = rr.json()
                if rd.get("status") == 1:
                    token = rd["request"]
                    # Step 4: Inject token into page
                    try:
                        if captcha_type.startswith("recaptcha"):
                            await page.evaluate(f"""
                                const ta = document.getElementById('g-recaptcha-response') ||
                                           document.querySelector('textarea[name="g-recaptcha-response"]');
                                if (ta) {{ ta.value = '{token}'; ta.innerHTML = '{token}'; }}
                                if (window.___grecaptcha_cfg) {{
                                  try {{ window.___grecaptcha_cfg.clients[0].callback('{token}'); }} catch(e) {{}}
                                }}
                            """)
                        elif captcha_type == "hcaptcha":
                            await page.evaluate(f"""
                                document.querySelectorAll('textarea[name="h-captcha-response"],textarea[name="g-recaptcha-response"]').forEach(t => {{
                                  t.value = '{token}'; t.innerHTML = '{token}';
                                }});
                            """)
                        elif captcha_type == "cloudflare_turnstile":
                            await page.evaluate(f"""
                                document.querySelectorAll('input[name="cf-turnstile-response"]').forEach(t => {{
                                  t.value = '{token}';
                                }});
                            """)
                    except Exception as e:
                        logger.warning(f"token injection failed: {e}")
                    return {"ok": True, "token": token}
                if rd.get("request") != "CAPCHA_NOT_READY":
                    return {"error": f"2captcha err: {rd.get('request')}"}
            return {"error": "2captcha timeout"}
    except Exception as e:
        return {"error": f"2captcha exception: {e}"}


# ── Bind ──────────────────────────────────────────────────────────────
def _bind(*, main_db, get_current_user):
    _state["db"] = main_db
    router = build_router(get_current_user)
    return router


# ─────────────────────────────────────────────────────────────────────
# Visual Recorder → RPA Studio converter
# ─────────────────────────────────────────────────────────────────────
def _convert_recorder_steps_to_flowchart(steps: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Convert a Visual Recorder steps array into RPA Studio nodes + edges.

    The recorder's JSON is a *linear* list of action dicts. We map each
    to its closest RPA Studio node type, lay them out in a vertical
    chain (auto-spaced), and emit straight edges between consecutive
    nodes so the user immediately sees a working flowchart they can
    extend (add If/Loop branches, sub-workflows, etc.).
    """
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    x = 240
    y = 60
    dy = 110

    prev_id: Optional[str] = None
    for i, raw in enumerate(steps):
        if not isinstance(raw, dict):
            continue
        action = (raw.get("action") or "").lower().strip()
        if not action:
            continue
        nid = f"rec_{i}_{uuid.uuid4().hex[:6]}"
        rpa_node = _recorder_step_to_rpa_node(nid, action, raw, {"x": x, "y": y})
        if rpa_node is None:
            continue
        nodes.append(rpa_node)
        if prev_id is not None:
            edges.append({"id": f"e_{prev_id}_{nid}", "from": prev_id, "to": nid})
        prev_id = nid
        y += dy

    return nodes, edges


def _recorder_step_to_rpa_node(nid: str, action: str, raw: dict, pos: dict) -> Optional[Dict[str, Any]]:
    """Map ONE recorder step → ONE RPA Studio node (or None to skip)."""
    base = {"id": nid, "position": pos, "on_error": "skip", "body": [], "branches": {}}

    if action in ("goto", "navigate"):
        return {**base, "type": "goto", "params": {"url": raw.get("url") or "", "timeout": raw.get("timeout") or 60000}}
    if action == "click":
        return {**base, "type": "click", "params": {
            "selector": raw.get("selector") or "",
            "button": raw.get("button") or "left",
            "count": int(raw.get("click_count") or 1),
            "timeout": raw.get("timeout") or 15000,
        }}
    if action in ("fill", "type"):
        return {**base, "type": "fill", "params": {
            "selector": raw.get("selector") or "",
            "value": str(raw.get("value") or ""),
            "clear_first": True,
            "type_interval_ms": raw.get("delay") or 0,
        }}
    if action == "select":
        return {**base, "type": "select", "params": {
            "selector": raw.get("selector") or "",
            "value": raw.get("value") or "",
            "match_by": raw.get("match_by") or "value",
        }}
    if action in ("check", "uncheck"):
        return {**base, "type": "checkbox", "params": {
            "selector": raw.get("selector") or "",
            "action": action,
        }}
    if action == "press":
        return {**base, "type": "press", "params": {"key": raw.get("key") or "Enter"}}
    if action == "wait":
        return {**base, "type": "wait", "params": {"ms": int(raw.get("ms") or 1000)}}
    if action == "wait_for_load":
        return {**base, "type": "wait_for_load", "params": {"state": raw.get("state") or "domcontentloaded", "timeout": raw.get("timeout") or 30000}}
    if action == "wait_for_selector":
        return {**base, "type": "wait_for_selector", "params": {
            "selector": raw.get("selector") or "",
            "state": raw.get("state") or "visible",
            "timeout": raw.get("timeout") or 15000,
        }}
    if action == "wait_for_text":
        return {**base, "type": "wait_for_text", "params": {
            "text": raw.get("text") or "",
            "timeout": raw.get("timeout") or 15000,
        }}
    if action == "wait_for_url":
        return {**base, "type": "wait_for_url", "params": {
            "contains": raw.get("contains") or raw.get("url") or "",
            "timeout": raw.get("timeout") or 15000,
        }}
    if action == "scroll":
        y_val = raw.get("y")
        dist = "bottom"
        if isinstance(y_val, (int, float)):
            dist = int(y_val)
        elif y_val is not None:
            dist = str(y_val)
        return {**base, "type": "scroll", "params": {"distance": dist, "smooth": True}}
    if action == "evaluate":
        return {**base, "type": "evaluate", "params": {"script": raw.get("script") or "1"}}
    if action == "extract":
        return {**base, "type": "get_element", "params": {
            "selector": raw.get("selector") or "",
            "extraction": "attribute" if raw.get("attribute") else "text",
            "attribute": raw.get("attribute") or "",
            "save_to": raw.get("store_key") or "extracted",
        }}
    if action == "screenshot":
        return {**base, "type": "screenshot", "params": {"name": raw.get("name") or "Screenshot", "full_page": bool(raw.get("full_page"))}}
    if action == "dismiss_popups":
        # No direct node — emit an Execute JS step with a sensible default
        return {**base, "type": "evaluate", "params": {
            "script": "document.querySelectorAll('[aria-label*=close i],[class*=close i]').forEach(el => { try { el.click(); } catch(e) {} });",
        }}
    if action == "close":
        return {**base, "type": "quit_browser", "params": {}}
    if action == "branch":
        # Visual Recorder branch becomes an If node with two child chains.
        # Both branch's `steps` are flattened into the body for now —
        # advanced users can rewire them to true/false handles after import.
        branches = raw.get("branches") or []
        first = (branches[0] if branches else {}) or {}
        cond = (first.get("condition") or {}).get("selector") or ""
        return {**base, "type": "if", "params": {
            "variable": "_branch_indicator",
            "condition": "exists",
            "value": cond,
        }}
    # Unknown / unmapped action → keep as a transparent Execute JS no-op
    # so the original ordering is preserved in the flowchart.
    return {**base, "type": "evaluate", "params": {
        "script": f"/* unmapped recorder action: {action} — params: {json.dumps(raw)[:200]} */ 1",
    }}

