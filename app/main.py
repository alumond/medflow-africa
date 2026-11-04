"""FastAPI entry point for the editorial interface, API and reviewable exports."""

import csv
import hashlib
import io
import json
import logging
import os
import secrets
import tempfile
import time
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal, Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from app.core.config import POLICY, ROOT
from app.core.schemas import ReportRequest, ReviewRequest, CopilotRequest
from app.data.store import Store
from app.data.blob import BlobSnapshots, SnapshotConflict
from app.data.validation import parse_csv
from app.reporting.gemini import MODEL as GEMINI_MODEL, compose
from app.reporting.report import build_report, email_file, escalation
from app.services.service import Service
from app.services.copilot import answer as copilot_answer, monitoring

if not os.environ.get("VERCEL"):
    load_dotenv(ROOT / ".env.local")
    load_dotenv(ROOT / ".env")

logger = logging.getLogger("medflow")
app = FastAPI(title="MedFlow Africa", version="0.1.0", docs_url="/api/docs", openapi_url="/api/openapi.json")
app.mount("/assets", StaticFiles(directory=ROOT / "app/web/assets"), name="assets")


@app.middleware("http")
async def repository_context(request: Request, call_next):
    """Use local SQLite or isolated, CAS-persisted private Blob snapshots on Vercel."""
    correlation = uuid.uuid4().hex
    request.state.correlation = correlation
    started = time.monotonic()
    temporary = None
    remote = bool(os.environ.get("VERCEL"))
    cookie = request.cookies.get("medflow_workspace", "")
    if not (len(cookie) == 64 and all(c in "0123456789abcdef" for c in cookie)):
        cookie = secrets.token_hex(32)
    try:
        if request.url.path.startswith(
            ("/api/", "/risk/", "/data/", "/redistribution/", "/reports/", "/audit/")
        ) and request.url.path not in ("/api/docs", "/api/openapi.json"):
            if remote:
                temporary = tempfile.TemporaryDirectory(prefix="medflow-")
                db_path = Path(temporary.name) / "workspace.sqlite"
                blob_path = "workspaces/" + hashlib.sha256(cookie.encode()).hexdigest() + ".sqlite"
                snapshots = BlobSnapshots()
                before, etag = await snapshots.read(blob_path)
                if before:
                    db_path.write_bytes(before)
                request.state.store = Store(str(db_path))
            else:
                request.state.store = Store(os.environ.get("MEDFLOW_DB", str(ROOT / "data/medflow.sqlite")))
            Service(request.state.store).ensure_demo()
        response = await call_next(request)
        if remote and hasattr(request.state, "store") and response.status_code < 500:
            after = db_path.read_bytes()
            if after != before:
                await snapshots.write(blob_path, after, etag)
        response.headers["X-Correlation-ID"] = correlation
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "private, no-store"
        response.set_cookie(
            "medflow_workspace", cookie, httponly=True, secure=remote, samesite="lax", max_age=90 * 86400
        )
        logger.info(
            json.dumps(
                {
                    "event": "request.completed",
                    "correlation_id": correlation,
                    "path": request.url.path,
                    "status": response.status_code,
                    "duration_ms": round((time.monotonic() - started) * 1000),
                }
            )
        )
        return response
    except Exception as exc:
        kind = type(exc).__name__
        conflict = isinstance(exc, SnapshotConflict)
        logger.error(
            json.dumps({"event": "request.failed", "correlation_id": correlation, "error_type": kind})
        )
        return JSONResponse(
            status_code=409 if conflict else 503,
            content={
                "detail": "Your workspace changed in another request. Refresh and retry."
                if conflict
                else "The workspace is temporarily unavailable. Please retry.",
                "correlation_id": correlation,
            },
            headers={"X-Correlation-ID": correlation},
        )
    finally:
        if temporary:
            temporary.cleanup()


def service(request: Request) -> Service:
    """Resolve only the repository assigned to this request's workspace."""
    return Service(request.state.store)


@app.exception_handler(ValueError)
async def value_error(request: Request, error: ValueError):
    return JSONResponse(
        status_code=422, content={"detail": str(error), "correlation_id": request.state.correlation}
    )


@app.exception_handler(LookupError)
async def lookup_error(request: Request, error: LookupError):
    return JSONResponse(
        status_code=404, content={"detail": str(error), "correlation_id": request.state.correlation}
    )


@app.exception_handler(RuntimeError)
async def stale_error(request: Request, error: RuntimeError):
    return JSONResponse(
        status_code=409, content={"detail": str(error), "correlation_id": request.state.correlation}
    )


@app.get("/", response_class=HTMLResponse)
def index():
    return (ROOT / "app/web/index.html").read_text()


@app.get("/health")
@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "version": "0.1.0",
        "mode": "synthetic decision support",
        "llm_enabled": bool(os.environ.get("GEMINI_API_KEY")),
        "persistence": "private Vercel Blob" if os.environ.get("VERCEL") else "SQLite",
    }


@app.get("/api/risk/summary")
@app.get("/risk/summary", include_in_schema=False)
def summary(window: int = Query(14, ge=7, le=30), svc: Service = Depends(service)):
    return svc.overview(window)


@app.get("/api/risk/details")
@app.get("/risk/details", include_in_schema=False)
def risk_details(
    window: int = Query(14, ge=7, le=30),
    facility: Optional[str] = None,
    medicine: Optional[str] = None,
    risk: Optional[Literal["high", "medium", "low", "not_assessed"]] = None,
    quality: Optional[Literal["strong", "acceptable", "limited", "blocked"]] = None,
    svc: Service = Depends(service),
):
    snapshot = svc.snapshot(window)
    return {
        "context": snapshot["context"],
        "pairs": [
            p
            for p in snapshot["pairs"]
            if (not facility or p["facility_id"] == facility)
            and (not medicine or p["medicine_id"] == medicine)
            and (not risk or p["risk"] == risk)
            and (not quality or p["quality"] == quality)
        ],
    }


@app.get("/api/data/quality")
@app.get("/data/quality", include_in_schema=False)
def quality(svc: Service = Depends(service)):
    return svc.snapshot()["quality"]


@app.post("/api/data/demo")
def demo(svc: Service = Depends(service)):
    return svc.load_demo()


@app.post("/api/data/import")
@app.post("/data/import", include_in_schema=False)
async def import_data(
    facilities: UploadFile = File(...),
    medicines: UploadFile = File(...),
    inventory: UploadFile = File(...),
    orders: UploadFile = File(...),
    cutoff: date = Form(...),
    schema_version: str = Form("1.0.0"),
    anonymised_confirmed: bool = Form(False),
    svc: Service = Depends(service),
):
    if schema_version != POLICY["schema_version"]:
        raise ValueError("Unsupported schema version")
    if not anonymised_confirmed:
        raise ValueError("Confirm that files contain synthetic or anonymised operational data only")
    if cutoff > datetime.now(timezone.utc).date():
        raise ValueError("Reporting cut-off cannot be in the future")
    bundle, sources = {}, []
    try:
        for entity, file in (
            ("facilities", facilities),
            ("medicines", medicines),
            ("inventory", inventory),
            ("orders", orders),
        ):
            content = await file.read(POLICY["max_upload_bytes"] + 1)
            bundle[entity] = parse_csv(content, entity)
            sources.append(
                {
                    "filename": Path((file.filename or "dataset.csv").replace("\\", "/")).name[:120],
                    "entity": entity,
                    "rows": len(bundle[entity]),
                    "checksum": hashlib.sha256(content).hexdigest(),
                }
            )
        return svc.import_bundle(bundle, cutoff, sources, synthetic=False)
    except ValueError:
        svc.store.audit("import.failed", "upload", {"reason": "validation_failure"})
        raise


@app.get("/api/data/imports/{import_id}")
def import_status(import_id: str, svc: Service = Depends(service)):
    return {k: v for k, v in svc.store.import_by_id(import_id).items() if k != "data"}


@app.get("/api/data/demo/{entity}.csv")
def demo_file(entity: str):
    if entity not in ("facilities", "medicines", "inventory", "orders"):
        raise HTTPException(404, "Dataset type not found")
    return FileResponse(
        ROOT / f"data/demo/{entity}.csv", media_type="text/csv", filename=f"medflow-{entity}.csv"
    )


@app.get("/api/data/rejections.csv")
def rejections(svc: Service = Depends(service)):
    rows = svc.store.latest()["rejected"]
    out = io.StringIO()
    writer = csv.DictWriter(
        out,
        fieldnames=[
            "entity",
            "row",
            "facility_id",
            "medicine_id",
            "reporting_date",
            "rule",
            "field",
            "reason",
            "severity",
        ],
    )
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                key: "'" + value
                if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r"))
                else value
                for key, value in row.items()
            }
        )
    return Response(
        out.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="medflow-rejected-rows.csv"'},
    )


@app.get("/api/redistribution/recommendations")
@app.get("/redistribution/recommendations", include_in_schema=False)
def recommendations(window: int = Query(14, ge=7, le=30), svc: Service = Depends(service)):
    return svc.planner(window)


@app.post("/api/redistribution/{recommendation_id}/review")
@app.post("/redistribution/{recommendation_id}/review", include_in_schema=False)
def review(
    recommendation_id: str,
    request: ReviewRequest,
    window: int = Query(14, ge=7, le=30),
    svc: Service = Depends(service),
):
    return svc.review(recommendation_id, request.model_dump(), window)


@app.get("/api/reports/draft")
def draft(svc: Service = Depends(service)):
    return svc.store.draft(svc.store.latest()["import_id"])


@app.put("/api/reports/draft")
def save_draft(request: ReportRequest, svc: Service = Depends(service)):
    svc.store.save_draft(svc.store.latest()["import_id"], request.model_dump(mode="json"))
    return {"status": "saved"}


@app.post("/api/reports/action-report", response_class=HTMLResponse)
async def report(request: ReportRequest, download: bool = False, svc: Service = Depends(service)):
    snapshot = svc.snapshot(request.window)
    planner = svc.planner(request.window)
    narrative = await compose(snapshot, planner, request.model_dump(mode="json"), svc.store)
    html = build_report(snapshot, planner, request.model_dump(mode="json"), narrative)
    svc.store.audit(
        "report.exported" if download else "report.generated",
        snapshot["context"]["import_id"],
        {"window": request.window},
    )
    headers = (
        {"Content-Disposition": 'attachment; filename="medflow-district-action-report.html"'}
        if download
        else {}
    )
    return HTMLResponse(html, headers=headers)


@app.get("/api/reports/action-report", response_class=HTMLResponse)
@app.get("/reports/action-report", include_in_schema=False, response_class=HTMLResponse)
async def report_get(window: int = Query(14, ge=7, le=30), svc: Service = Depends(service)):
    return await report(ReportRequest(window=window), False, svc)


@app.post("/api/reports/escalation")
async def email_draft(request: ReportRequest, download: bool = False, svc: Service = Depends(service)):
    snapshot, planner = svc.snapshot(request.window), svc.planner(request.window)
    narrative = await compose(snapshot, planner, request.model_dump(mode="json"), svc.store)
    result = escalation(snapshot, planner, request.model_dump(mode="json"))
    result["narrative"] = {k: v for k, v in narrative.items() if k != "sections"}
    if narrative["mode"] == "gemini":
        framing = "\n\n".join(p["text"] for p in narrative["sections"]["executive_summary"])
        result["body"] = "AI-assisted draft — pending human review\n\n" + framing + "\n\n" + result["body"]
    svc.store.audit("escalation.drafted", svc.store.latest()["import_id"], {"warranted": result["warranted"]})
    if download:
        return Response(
            email_file(result),
            media_type="message/rfc822",
            headers={"Content-Disposition": 'attachment; filename="medflow-escalation-draft.eml"'},
        )
    return result


@app.get("/api/ai/status")
def ai_status():
    return {
        "configured": bool(os.environ.get("GEMINI_API_KEY")),
        "model": os.environ.get("GEMINI_MODEL", GEMINI_MODEL),
        "scope": "synthetic_summary_facts_only",
        "daily_workspace_limit": 10,
    }


@app.post("/api/ai/narrative")
async def ai_narrative(request: ReportRequest, svc: Service = Depends(service)):
    return await compose(
        svc.snapshot(request.window), svc.planner(request.window), request.model_dump(mode="json"), svc.store
    )


@app.get("/api/audit/events")
@app.get("/audit/events", include_in_schema=False)
def events(
    limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), svc: Service = Depends(service)
):
    return {"events": svc.store.events(limit, offset), "limit": limit, "offset": offset}


@app.get("/api/model/evaluation")
def evaluation():
    path = ROOT / "model_artifacts/evaluation.json"
    return (
        json.loads(path.read_text())
        if path.exists()
        else {
            "status": "not_trained",
            "message": "No evaluated model artifact. Deterministic baseline remains available.",
        }
    )


@app.post("/api/copilot/ask")
async def copilot(request: CopilotRequest, svc: Service = Depends(service)):
    return await copilot_answer(svc, request.model_dump())


@app.get("/api/monitoring/summary")
def model_monitoring(window: int = Query(14, ge=7, le=30), svc: Service = Depends(service)):
    return monitoring(svc, window)
