"""Prepare and safely apply city data imports to NRI Ease's existing MySQL schema.

This tool fetches the Square Yards city catalog and can use cited AI web search to
stage evidence candidates for human review. It converts city CSVs into four
idempotent SQL files; it does not bypass CAPTCHA or alter existing tables.
"""

from __future__ import annotations

import argparse
import csv
import getpass
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parent
CITY_ROOT = ROOT / "city_onboarding" / "cities"
SCHEMA_FILE = ROOT / "city_onboarding_schema.sql"
DATABASE = "nriease_guidelines"
RATE_COLUMNS = [
    "plot_residential_sqm", "plot_commercial_sqm", "plot_industrial_sqm",
    "building_residential_rcc_sqm", "building_residential_rbc_sqm",
    "building_residential_tin_shade_sqm", "building_residential_kaccha_kabelu_sqm",
    "building_commercial_shop_sqm", "building_commercial_office_sqm",
    "building_commercial_godown_sqm", "building_multi_residential_sqm",
    "building_multi_commercial_sqm", "agricultural_irrigated_hectare",
    "agricultural_unirrigated_hectare", "agricultural_plot_subclause_1_sqm",
    "agricultural_plot_subclause_2_sqm",
]
ALLOWED_TABLES = {
    "projects", "guideline_sources", "guideline_entries", "project_guideline_matches",
    "financier_reference_sources", "financier_project_references",
    "infrastructure_sources", "infrastructure_projects",
}
REQUIRED_TABLES = ALLOWED_TABLES
PILLAR_FILES = ("projects.sql", "price_trends.sql", "financier.sql", "infrastructure.sql")
SQUARE_YARDS_ENDPOINT = "https://sy-mcp.squareyards.com/mcp/external"
OPENAI_RESPONSES_ENDPOINT = "https://api.openai.com/v1/responses"
GROQ_CHAT_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
GEMINI_GENERATE_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
PROJECT_HEADERS = ["project_id", "project_name", "city", "locality", "project_source", "property_type"]
PRICE_HEADERS = ["city", "district", "financial_year", "file_name", "source_url", "printed_page", "serial_no", "urban_local_body", "sub_area", "ward", "tehsil", "guideline_place", "normalized_place", *RATE_COLUMNS, "extraction_status", "extraction_note"]
FINANCE_HEADERS = ["financier_name", "source_title", "source_type", "source_url", "source_note", "source_captured_at", "project_id", "listed_project_name", "builder_name", "bank_project_code", "match_status", "match_note", "captured_at"]
INFRA_HEADERS = ["source_key", "source_type", "source_title", "source_url", "file_name", "fetched_at", "content_sha256", "extracted_content", "import_note", "source_item_key", "project_name", "city", "area_name", "locality_names", "scope", "category", "program_name", "status_code", "status_label", "description", "capacity_value", "capacity_unit", "source_reference", "raw_record", "is_active", "imported_at"]
SOURCE_HEADERS = ["pillar", "source_name", "source_url", "source_title", "access_status", "checked_at", "notes"]
RESEARCH_TASK_HEADERS = ["task_id", "pillar", "provider", "status", "completed_at", "citations_count", "source_leads", "evidence_leads", "error"]


def slugify(value: str) -> str:
    result = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    if not result:
        raise ValueError("City name must contain letters or numbers.")
    return result


def sql_text(value: Any) -> str:
    if value is None or str(value).strip() == "":
        return "NULL"
    text = str(value).replace("\\", "\\\\").replace("'", "''")
    return "'" + text + "'"


def sql_number(value: Any, *, integer: bool = False) -> str:
    if value is None or str(value).strip() == "":
        return "NULL"
    text = str(value).strip().replace(",", "")
    pattern = r"\d+" if integer else r"\d+(?:\.\d+)?"
    if not re.fullmatch(pattern, text):
        raise ValueError(f"Invalid {'integer' if integer else 'number'}: {value!r}")
    return text


def sql_json(value: Any, *, default: Any = None) -> str:
    if value is None or str(value).strip() == "":
        value = default
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Expected a JSON value, got {value!r}") from exc
    return "CAST(" + sql_text(json.dumps(value, ensure_ascii=False, separators=(",", ":"))) + " AS JSON)"


def read_csv(path: Path, required: set[str]) -> list[dict[str, str]]:
    if not path.exists():
        raise ValueError(f"Required CSV is missing: {path.name}")
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        headers = set(reader.fieldnames or [])
        missing = sorted(required - headers)
        if missing:
            raise ValueError(f"{path.name} is missing columns: {', '.join(missing)}")
        return [{key: (value or "").strip() for key, value in row.items()} for row in reader]


def write_csv(path: Path, headers: list[str], rows: list[dict[str, Any]] | None = None) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        if rows:
            writer.writerows(rows)


def _post_json(url: str, payload: dict[str, Any], headers: dict[str, str], timeout: int = 120, progress_label: str | None = None) -> dict[str, Any]:
    encoded = json.dumps(payload).encode("utf-8")
    for attempt in range(3):
        request = urllib.request.Request(url, data=encoded, headers=headers, method="POST")
        stop_progress = threading.Event()
        progress_thread = None
        if progress_label:
            started = time.monotonic()
            def report_wait() -> None:
                while not stop_progress.wait(20):
                    print(f"[AI research] Still searching {progress_label} ({int(time.monotonic() - started)} sec elapsed)...", flush=True)
            progress_thread = threading.Thread(target=report_wait, daemon=True)
            progress_thread.start()
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read().decode("utf-8")
                try:
                    return json.loads(body)
                except json.JSONDecodeError:
                    for line in body.splitlines():
                        if line.startswith("data:"):
                            try:
                                return json.loads(line[5:].strip())
                            except json.JSONDecodeError:
                                continue
                    raise ValueError("Provider returned an unreadable response.")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:1200]
            if exc.code == 503 and attempt < 2:
                delay = 2 * (attempt + 1)
                print(f"Temporary service outage (HTTP 503); retrying in {delay} seconds ({attempt + 1}/2)...", flush=True)
                time.sleep(delay)
                continue
            if exc.code == 403 and "1010" in detail:
                raise ValueError("The AI provider's edge security blocked this request (HTTP 403/code 1010). Check the provider endpoint/account or try again from a different network.") from exc
            raise ValueError(f"Data provider returned HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise ValueError(f"Could not reach data provider: {exc.reason}") from exc
        finally:
            if progress_thread:
                stop_progress.set()
                progress_thread.join(timeout=1)


def _mcp_call(tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
    payload = _post_json(
        SQUARE_YARDS_ENDPOINT,
        {"jsonrpc": "2.0", "id": int(time.time() * 1000), "method": "tools/call", "params": {"name": tool, "arguments": arguments}},
        {"Content-Type": "application/json", "Accept": "application/json, text/event-stream", "MCP-Protocol-Version": "2025-11-25"},
    )
    if "result" not in payload and "data:" in str(payload):
        raise ValueError("Square Yards returned an unreadable streaming response; try again later.")
    result = payload.get("result", payload)
    if result.get("isError"):
        detail = " ".join(item.get("text", "") for item in result.get("content", []) if isinstance(item, dict))
        raise ValueError("Square Yards project search failed: " + (detail or "provider error"))
    structured = result.get("structuredContent") or payload.get("structuredContent")
    if not isinstance(structured, dict):
        # Some MCP servers return structured JSON as a text content block.
        for item in result.get("content", []):
            if isinstance(item, dict) and item.get("text"):
                try:
                    structured = json.loads(item["text"])
                    break
                except json.JSONDecodeError:
                    pass
    if not isinstance(structured, dict):
        raise ValueError("Square Yards did not return structured project results.")
    return structured


def fetch_city_projects(city: str, page_size: int = 20, max_pages: int = 100) -> list[dict[str, str]]:
    projects: dict[str, dict[str, str]] = {}
    expected_total: int | None = None
    for page in range(1, max_pages + 1):
        print(f"[Projects] Fetching Square Yards page {page}...", flush=True)
        result = _mcp_call("search_projects", {"location": city, "buildingType": "1", "page": page, "paging": page_size, "maxPrice": 50000000000})
        batch = result.get("projects")
        if not isinstance(batch, list):
            raise ValueError("Square Yards response has no projects list; no project CSV was changed.")
        total_value = result.get("total") or result.get("totalCount") or result.get("count")
        expected_total = int(total_value) if total_value is not None else None
        for item in batch:
            if not isinstance(item, dict):
                continue
            pid = item.get("id") or item.get("projectId") or item.get("project_id")
            name = item.get("name") or item.get("projectName") or item.get("project_name") or item.get("title")
            if pid is None or not name:
                continue
            project_id = str(pid).strip()
            if not project_id.isdigit():
                continue
            locality = item.get("locality") or item.get("subLocality") or item.get("subLocation") or item.get("location") or ""
            if isinstance(locality, dict):
                locality = locality.get("name") or locality.get("locality") or ""
            prop_type = item.get("propertyType") or item.get("property_type") or item.get("buildingType") or "Residential"
            projects[project_id] = {"project_id": project_id, "project_name": str(name).strip(), "city": city, "locality": str(locality).strip(), "project_source": "Square Yards", "property_type": str(prop_type).strip()}
        if not batch or len(batch) < page_size or (expected_total is not None and len(projects) >= expected_total):
            break
        print(f"[Projects] Collected {len(projects)} unique project IDs so far" + (f" (source reports {expected_total})" if expected_total is not None else "") + ".", flush=True)
    if expected_total and len(projects) < expected_total and len(projects) >= page_size * max_pages:
        print(f"Warning: reached the {max_pages}-page safety limit; fetched {len(projects)} of approximately {expected_total} listings.")
    if not projects:
        raise ValueError(f"Square Yards returned no usable residential projects for {city}; no CSV was changed.")
    return list(projects.values())


def _run_codex_research(prompt: str, task_id: str) -> tuple[dict[str, Any], set[str]]:
    """Run a web-grounded research pass through the locally authenticated Codex CLI."""
    codex = _find_codex_cli()
    if not codex:
        raise ValueError("Codex CLI was not found. Install Codex CLI and sign in with `codex login`, then rerun this command.")
    command = [codex, "exec", "--json", "--ephemeral", "--skip-git-repo-check", "--sandbox", "read-only", "-c", 'web_search="live"', "-"]
    model = os.environ.get("CODEX_MODEL", "").strip()
    if model:
        command[2:2] = ["--model", model]
    print(f"[Codex] Starting live web research for {task_id}. This uses the local Codex sign-in; no API key is requested.", flush=True)
    try:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, encoding="utf-8", errors="replace", bufsize=1, cwd=ROOT)
    except OSError as exc:
        raise ValueError(f"Could not start Codex CLI: {exc}") from exc
    output_parts: list[str] = []
    events_seen = 0
    try:
        assert process.stdin is not None and process.stdout is not None
        process.stdin.write(prompt)
        process.stdin.close()
        for line in process.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                print(f"[Codex] {line[:500]}", flush=True)
                continue
            events_seen += 1
            event_type = event.get("type", "")
            item = event.get("item", {}) if isinstance(event.get("item"), dict) else {}
            item_type = item.get("type", "")
            if event_type in {"item.started", "item.completed"} and item_type:
                label = item_type.replace("_", " ")
                if "search" in item_type:
                    print(f"[Codex] Searching the web ({task_id})...", flush=True)
                elif event_type == "item.started":
                    print(f"[Codex] Working: {label}...", flush=True)
            if event_type == "item.completed" and item_type in {"agent_message", "assistant_message"}:
                message = item.get("text")
                if isinstance(message, str) and message.strip():
                    output_parts.append(message.strip())
            if event_type == "error":
                detail = event.get("message") or event.get("error") or "Codex reported an error."
                print(f"[Codex] {detail}", flush=True)
        return_code = process.wait(timeout=3600)
    except subprocess.TimeoutExpired as exc:
        process.kill()
        process.wait()
        raise ValueError(f"Codex research for {task_id} exceeded the 60-minute limit. Rerun to retry this pass.") from exc
    except KeyboardInterrupt:
        process.terminate()
        process.wait(timeout=10)
        raise
    if return_code != 0:
        detail = "\n".join(output_parts).strip()
        raise ValueError(f"Codex CLI failed (exit {return_code}). Run `codex login` in PowerShell and confirm web search is available. {detail[-1200:]}")
    if not output_parts:
        raise ValueError(f"Codex completed {task_id} without a final research message ({events_seen} progress events received).")
    raw_text = "\n".join(output_parts)
    cited_urls = set(re.findall(r"https?://[^\s\]}>\"')]+", raw_text))
    candidates = [raw_text]
    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", raw_text, re.I | re.S)
    if fenced:
        candidates.insert(0, fenced.group(1))
    first_brace, last_brace = raw_text.find("{"), raw_text.rfind("}")
    if first_brace >= 0 and last_brace > first_brace:
        candidates.append(raw_text[first_brace:last_brace + 1])
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                print(f"[Codex] Finished {task_id}; {len(cited_urls)} source URLs found.", flush=True)
                return parsed, cited_urls
        except json.JSONDecodeError:
            continue
    raise ValueError("Codex research did not return parseable structured data. No data files were changed for this search; rerun the pass.")


def _find_codex_cli() -> str | None:
    """Find Codex on PATH or in the standard Windows desktop install location."""
    codex = shutil.which("codex")
    if codex:
        return codex
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        return None
    install_root = Path(local_app_data) / "OpenAI" / "Codex" / "bin"
    try:
        candidates = sorted((path / "codex.exe" for path in install_root.iterdir() if path.is_dir()),
                            key=lambda path: path.parent.stat().st_mtime, reverse=True)
    except OSError:
        return None
    return str(next((path for path in candidates if path.is_file()), "")) or None


def _city_research(city: str, projects: list[dict[str, str]], provider: str = "codex", *, _pillar: str | None = None, _task_id: str | None = None, _task_focus: str | None = None, _api_key: str | None = None, on_task_complete: Callable[[str, str, dict[str, Any], set[str]], None] | None = None, refresh: bool = False) -> tuple[dict[str, Any], set[str]]:
    provider = provider.casefold()
    if provider not in {"codex", "groq", "openai", "gemini"}:
        raise ValueError("AI provider must be codex, groq, openai, or gemini.")
    if provider == "codex":
        key_env = key_label = ""
        api_key = ""
    else:
        key_env = {"groq": "GROQ_API_KEY", "openai": "OPENAI_API_KEY", "gemini": "GEMINI_API_KEY"}[provider]
        key_label = {"groq": "Groq", "openai": "OpenAI", "gemini": "Google Gemini"}[provider]
        api_key = _api_key or os.environ.get(key_env)
        if not api_key:
            api_key = getpass.getpass(f"{key_label} API key (input hidden; used for this run only): ").strip()
        if not api_key:
            raise ValueError(f"A {key_label} API key is required for AI source research. Project collection is available separately with collect-projects.")
    if provider == "codex":
        codex = _find_codex_cli()
        if not codex:
            raise ValueError("Codex CLI was not found. Install Codex CLI, run `codex login`, then rerun this command.")
        try:
            login_status = subprocess.run([codex, "login", "status"], capture_output=True, text=True, timeout=15, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ValueError("Could not check Codex sign-in. Run `codex login` in PowerShell, then retry.") from exc
        status_text = (login_status.stdout + "\n" + login_status.stderr).casefold()
        if login_status.returncode != 0 or "not logged" in status_text or "not signed" in status_text or "chatgpt" not in status_text:
            raise ValueError("Codex CLI is not signed in with a ChatGPT account. Run `codex login` in PowerShell and choose ChatGPT sign-in; API-key login is not used by this pipeline.")
    if _pillar is None:
        banks = [
            ("SBI", "sbi.co.in"), ("PNB", "pnb.bank.in"),
            ("HDFC Bank", "homeloans.hdfc.bank.in"), ("Bank of Baroda", "bankofbaroda.bank.in"),
            ("Axis Bank", "application.axis.bank.in"), ("Union Bank", "unionbankofindia.bank.in"),
            ("Indian Bank", "indianbank.in"), ("Kotak Mahindra Bank", "kotak.bank.in"),
            ("Canara Bank", "canarabank.bank.in"), ("Bank of India", "bankofindia.bank.in"),
            ("ICICI Bank", "icicibank.com"),
        ]
        tasks: list[tuple[str, str, str]] = [("price_trends", "price_trends", f"Find the official state registration/valuation authority for {city}. Search separately for the current and prior annual valuation schedules, locality/ward rate tables, and official downloadable PDFs or datasets. Link the government schedule itself; record applicable years and access/CAPTCHA requirements. Do not use secondary summaries as evidence.")]
        tasks.extend((f"bank_{slugify(bank).replace('-', '_')}", "finance", f"Research ONLY {bank}'s official approved housing-project listings for {city}. Search the official host {domain} and PDFs hosted there, using queries for approved projects, builders, home loans, and {city}. Return relevant listed project names, builder, phase, bank code, the direct canonical page/PDF URL (not a Google redirect), and the source wording. If no city-specific list is publicly available, explicitly return no records and say why; do not substitute third-party/property sites or a generic bank homepage.") for bank, domain in banks)
        tasks.extend([
            ("infra_development", "infrastructure", f"Research {city}'s official development authority: master/development plans, capital project pages, and progress/completion reports. Find proposed, active, or recently completed physical projects and preserve named areas, project dates and status wording. Separate plan from actual work."),
            ("infra_municipal", "infrastructure", f"Research {city}'s official municipal corporation pages and reports for locality-specific roads, drainage, sewerage, water, parks, schools, solid waste, and other civic projects. Prioritize progress/completion updates and name areas exactly."),
            ("infra_transport", "infrastructure", f"Research official transport and public-works authorities serving {city} (metro, rail, highways, bus, roads, bridges). Find projects proposed, active, or completed recently. Use authority pages/reports and name exact corridors/localities; label metro-region versus city scope."),
            ("infra_utilities", "infrastructure", f"Research official water, sewerage, electricity and utility authorities serving {city}. Find named infrastructure projects and their reported status/timeline from authority reports or official project pages; avoid generic service pages."),
            ("infra_procurement", "infrastructure", f"Research the official state e-procurement portal for {city}-located infrastructure tenders and their latest tender/award/work status. Use exact project location, department, tender reference and dates. A tender alone must be labelled tendering, not construction or completion.")
        ])
        combined: dict[str, Any] = {"sources": [], "price_trends": [], "finance": [], "infrastructure": []}
        citations: set[str] = set()
        errors: list[str] = []
        task_log = CITY_ROOT / slugify(city) / "research_tasks.csv"
        completed_tasks = set()
        if task_log.exists() and not refresh:
            completed_tasks = {
                row["task_id"] for row in read_csv(task_log, set(RESEARCH_TASK_HEADERS))
                if row.get("provider") == provider and row.get("status") == "completed"
            }
        task_status_rows = read_csv(task_log, set(RESEARCH_TASK_HEADERS)) if task_log.exists() else []

        def record_task(task_id: str, pillar: str, status: str, *, citations_count: int = 0, source_leads: int = 0, evidence_leads: int = 0, error: str = "") -> None:
            item = {"task_id": task_id, "pillar": pillar, "provider": provider, "status": status,
                    "completed_at": datetime.now().isoformat(timespec="seconds"), "citations_count": citations_count,
                    "source_leads": source_leads, "evidence_leads": evidence_leads, "error": error}
            for index, previous in enumerate(task_status_rows):
                if previous.get("task_id") == task_id and previous.get("provider") == provider:
                    task_status_rows[index] = item
                    break
            else:
                task_status_rows.append(item)
            write_csv(task_log, RESEARCH_TASK_HEADERS, task_status_rows)

        for number, (task_id, pillar, task_focus) in enumerate(tasks, start=1):
            if task_id in completed_tasks:
                print(f"[AI research] Pass {number}/{len(tasks)}: {task_id} — already completed; reusing CSV results.", flush=True)
                continue
            pass_result: dict[str, Any] = {}
            pass_citations: set[str] = set()
            print(f"[AI research] Pass {number}/{len(tasks)}: {task_id} — searching official sources...", flush=True)
            try:
                pass_result, pass_citations = _city_research(city, projects, provider, _pillar=pillar, _task_id=task_id, _task_focus=task_focus, _api_key=api_key)
                if not isinstance(pass_result.get("sources"), list) or not isinstance(pass_result.get(pillar), list):
                    raise ValueError("Research response is missing the expected source or evidence list.")
            except (ValueError, OSError) as exc:
                errors.append(f"{task_id}: {exc}")
                print(f"[AI research] {task_id} failed: {exc}", flush=True)
                error_text = str(exc).casefold()
                is_quota = "http 429" in error_text and any(term in error_text for term in ("quota", "resource_exhausted", "retry in", "daily"))
                record_task(task_id, pillar, "quota_blocked" if is_quota else "failed", error=str(exc))
                if is_quota:
                    skipped = len(tasks) - number
                    if skipped:
                        errors.append(f"Stopped after provider quota exhaustion; {skipped} later research passes were not attempted. Run again after quota resets or use a provider with available quota.")
                        print(f"[AI research] Provider quota is exhausted; stopping to avoid wasting calls. {skipped} searches remain and will need a later run.", flush=True)
                    break
                continue
            combined["sources"].extend(pass_result.get("sources", []))
            combined[pillar].extend(pass_result.get(pillar, []))
            citations.update(pass_citations)
            print(f"[AI research] {task_id}: {len(pass_citations)} citations, {len(pass_result.get('sources', []))} source leads, {len(pass_result.get(pillar, []))} evidence leads.", flush=True)
            if on_task_complete:
                on_task_complete(task_id, pillar, pass_result, pass_citations)
            record_task(task_id, pillar, "completed", citations_count=len(pass_citations), source_leads=len(pass_result.get("sources", [])), evidence_leads=len(pass_result.get(pillar, [])))
        if errors:
            combined["_research_errors"] = errors
            print("[AI research] Some searches failed. Successful findings from this run are kept in the CSV review files.", flush=True)
        return combined, citations
    if _pillar not in {"price_trends", "finance", "infrastructure"}:
        raise ValueError(f"Unknown research pillar: {_pillar}")
    print(f"[AI research] Preparing official-source search for {city} using {key_label}...", flush=True)
    # Project matching is performed locally against the full fetched catalog;
    # never let a truncated LLM prompt decide which IDs can be considered.
    locality_projects: dict[str, list[str]] = {}
    for project in projects:
        locality = re.sub(r"\s+", " ", str(project.get("locality") or "").strip())
        name = str(project.get("project_name") or "").strip()
        if locality:
            bucket = locality_projects.setdefault(locality, [])
            if name and len(bucket) < 3:
                bucket.append(name)
    # Give the evidence search the actual locality vocabulary in the imported
    # catalog. Previously this was always empty, so infrastructure findings
    # could not be compared with the city's property areas.
    project_context = [
        {"locality": locality, "sample_projects": names}
        for locality, names in sorted(locality_projects.items(), key=lambda item: item[0].casefold())[:150]
    ]
    instructions = f"""Research official public records for the Indian city {city}. Use browser search. Find: (1) official state registration/stamp-duty guideline source, (2) official bank approved-project lists, and (3) official city-development, municipal, transport, water, utilities or procurement projects. Use only facts supported by sources. Do not bypass CAPTCHA, sign-in, or access controls. Do not guess rates, project matches, localities, status, dates, IDs, or URLs. Prefer official government/bank sources; exclude news, social media, Wikipedia and property portals. Use supplied Square Yards IDs only when the source explicitly identifies the same project; uncertain matches are null or possible. The supplied catalog is an excerpt of the first 25 projects; do not match any other ID. For price records, identify unit/category mismatches and only include values that fit existing NRI Ease rate fields. For CAPTCHA, report access_status=captcha. Return one complete valid JSON object only, no markdown fences or commentary. Keep it concise: no more than 6 sources total and no more than 2 records in each pillar; use empty arrays when evidence is unavailable. Never cut off the JSON. Shape: {{"sources":[{{"pillar":"price_trends|finance|infrastructure","source_name":"","source_url":"","source_title":"","access_status":"public|captcha|not_found|needs_review","notes":""}}],"price_trends":[{{"district":"","financial_year":"","file_name":"","source_url":"","printed_page":"","serial_no":"","urban_local_body":"","sub_area":"","ward":"","tehsil":"","guideline_place":"","normalized_place":"","rates":{{"plot_residential_sqm":null,"plot_commercial_sqm":null,"plot_industrial_sqm":null,"building_residential_rcc_sqm":null,"building_residential_rbc_sqm":null,"building_residential_tin_shade_sqm":null,"building_residential_kaccha_kabelu_sqm":null,"building_commercial_shop_sqm":null,"building_commercial_office_sqm":null,"building_commercial_godown_sqm":null,"building_multi_residential_sqm":null,"building_multi_commercial_sqm":null,"agricultural_irrigated_hectare":null,"agricultural_unirrigated_hectare":null,"agricultural_plot_subclause_1_sqm":null,"agricultural_plot_subclause_2_sqm":null}},"extraction_note":""}}],"finance":[{{"financier_name":"","source_title":"","source_type":"official_website|pdf","source_url":"","source_note":"","source_captured_at":"","project_id":null,"listed_project_name":"","builder_name":"","bank_project_code":"","match_status":"possible","match_note":""}}],"infrastructure":[{{"source_key":"","source_type":"webpage|pdf","source_title":"","source_url":"","project_name":"","area_name":"","locality_names":[],"scope":"locality|area_based|citywide|unlocated","category":"","program_name":"","status_code":"proposed|tendering|dpr_preparation|awaiting_land_transfer|work_in_progress|completed_reported|unknown","status_label":"","description":"","source_reference":""}}]}}. Include the exact source URL in each record. Supplied Square Yards IDs/names/localities: {json.dumps(project_context, ensure_ascii=False)}"""
    focus = _task_focus or f"Search official sources for the { _pillar.replace('_', ' ') } pillar in {city}; use multiple focused queries, exact source URLs and source-backed facts."
    instructions = instructions.replace("The supplied catalog is an excerpt of the first 25 projects; do not match any other ID.", "Project IDs are matched locally against the complete Square Yards catalog after source research; do not invent IDs.")
    instructions = re.sub(r"Research official public records.*?Use only facts supported by sources\.", f"Research the {_pillar.replace('_', ' ')} pillar ONLY for {city}. Use live Codex web search to inspect relevant official pages/PDFs. {focus} Use only facts supported by sources. For infrastructure, include locality-specific records only when the source names the area; use citywide only when the source clearly covers the whole city, and exclude projects located only elsewhere in the metropolitan region. The supplied locality list is a relevance checklist, not proof of a project-area match. For price trends, return rate rows only when the official schedule itself provides the exact locality, year, units and values; otherwise return no rate rows and report the source/CAPTCHA status.", instructions, count=1, flags=re.S)
    instructions = instructions.replace("no more than 6 sources total and no more than 2 records in each pillar", "no more than 10 sources and 15 evidence records for the active pillar; return empty arrays for the other pillars")
    if provider == "codex":
        return _run_codex_research(instructions, _task_id or _pillar or "research")
    if provider == "groq":
        request_payload = {
            "model": os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b"),
            "messages": [{"role": "user", "content": instructions}],
            "tools": [{"type": "browser_search"}],
            "tool_choice": "required",
            "max_completion_tokens": 4096,
            "stream": False,
        }
        endpoint = GROQ_CHAT_ENDPOINT
    elif provider == "openai":
        request_payload = {
            "model": os.environ.get("OPENAI_MODEL", "gpt-5.5"),
            "tools": [{"type": "web_search"}],
            "include": ["web_search_call.action.sources"],
            "input": instructions,
            "max_output_tokens": 12000,
        }
        endpoint = OPENAI_RESPONSES_ENDPOINT
    else:
        model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
        request_payload = {
            "contents": [{"parts": [{"text": instructions}]}],
            "tools": [{"google_search": {}}, {"url_context": {}}],
            "generationConfig": {"maxOutputTokens": 16000},
        }
        endpoint = GEMINI_GENERATE_ENDPOINT.format(model=model)
    headers = {"Content-Type": "application/json"}
    if provider == "gemini":
        headers["x-goog-api-key"] = api_key
    else:
        headers["Authorization"] = f"Bearer {api_key}"
    payload = _post_json(endpoint, request_payload, headers, progress_label=_task_id or _pillar)
    print("[AI research] Search response received; extracting cited sources and structured records...", flush=True)
    if payload.get("error"):
        raise ValueError(f"{key_label} research failed: " + str(payload["error"].get("message", "API error")))
    text_parts: list[str] = []
    cited_urls: set[str] = set()
    if provider == "gemini":
        for candidate in payload.get("candidates", []):
            content = candidate.get("content", {})
            text_parts.extend(part.get("text", "") for part in content.get("parts", []) if isinstance(part, dict) and part.get("text"))
            metadata = candidate.get("groundingMetadata", {})
            for chunk in metadata.get("groundingChunks", []):
                uri = chunk.get("web", {}).get("uri") if isinstance(chunk, dict) else None
                if uri and uri.startswith(("https://", "http://")):
                    cited_urls.add(uri)
    if provider == "groq":
        for choice in payload.get("choices", []):
            message = choice.get("message", {})
            content = message.get("content")
            if isinstance(content, str):
                text_parts.append(content)
            elif isinstance(content, list):
                text_parts.extend(str(part.get("text", "")) for part in content if isinstance(part, dict))
            for citation in message.get("citations", []) or []:
                if isinstance(citation, str):
                    cited_urls.add(citation)
                elif isinstance(citation, dict) and citation.get("url"):
                    cited_urls.add(citation["url"])
    for item in payload.get("output", []):
        if item.get("type") == "web_search_call":
            for source in item.get("action", {}).get("sources", []):
                if source.get("url", "").startswith("https://") or source.get("url", "").startswith("http://"):
                    cited_urls.add(source["url"])
        if item.get("type") == "message":
            for part in item.get("content", []):
                if part.get("type") == "output_text":
                    text_parts.append(part.get("text", ""))
                    for annotation in part.get("annotations", []):
                        url = annotation.get("url") or annotation.get("url_citation", {}).get("url")
                        if url and url.startswith(("https://", "http://")):
                            cited_urls.add(url)
    if not text_parts and provider == "groq":
        # Responses-compatible endpoints can return a convenience field.
        convenience_text = payload.get("output_text")
        if convenience_text:
            text_parts.append(str(convenience_text))
    if not text_parts:
        raise ValueError(f"{key_label} research returned no usable response text.")
    raw_text = "\n".join(text_parts).strip()
    if provider == "gemini" and any(c.get("finishReason") == "MAX_TOKENS" for c in payload.get("candidates", [])):
        raise ValueError("Gemini stopped before completing its response. No data files were changed for this search; retry with a smaller scope or later.")
    # Groq's browser-search citations are normally rendered inline in the
    # response instead of in OpenAI's web_search_call source array.
    cited_urls.update(re.findall(r"https?://[^\s\]}>\"')]+", raw_text))
    # Web Search currently rejects Responses API JSON mode. Ask for JSON in
    # the prompt, then tolerate a fenced or prose-wrapped JSON object here.
    candidates = [raw_text]
    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", raw_text, re.I | re.S)
    if fenced:
        candidates.insert(0, fenced.group(1))
    first_brace, last_brace = raw_text.find("{"), raw_text.rfind("}")
    if first_brace >= 0 and last_brace > first_brace:
        candidates.append(raw_text[first_brace:last_brace + 1])
    findings = None
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                findings = parsed
                break
        except json.JSONDecodeError:
            continue
    if findings is None:
        raise ValueError("AI research did not return parseable structured data. No data files were changed for this search; retry or use a different provider/model.")
    print(f"[AI research] Completed {_task_id or _pillar}: {len(cited_urls)} grounded source URLs captured.", flush=True)
    return findings, cited_urls


def _merge_csv(path: Path, headers: list[str], rows: list[dict[str, Any]], keys: tuple[str, ...]) -> int:
    existing = read_csv(path, set(headers)) if path.exists() else []
    seen = {tuple(row.get(k, "").strip().casefold() for k in keys) for row in existing}
    added = 0
    for row in rows:
        item = {header: "" if row.get(header) is None else str(row.get(header, "")) for header in headers}
        key = tuple(item.get(k, "").strip().casefold() for k in keys)
        if not all(key) or key in seen:
            continue
        existing.append(item)
        seen.add(key)
        added += 1
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(existing)
    return added


def _merge_project_catalog(path: Path, rows: list[dict[str, Any]]) -> tuple[int, int]:
    """Merge the live catalog by project_id, collapsing any old duplicate rows."""
    existing = read_csv(path, set(PROJECT_HEADERS)) if path.exists() else []
    merged: dict[str, dict[str, str]] = {}
    order: list[str] = []
    removed = 0
    for row in existing:
        project_id = row.get("project_id", "").strip()
        if not project_id:
            removed += 1
            continue
        if project_id in merged:
            removed += 1
            # Preserve populated values from duplicate rows while keeping one row per ID.
            merged[project_id].update({k: v for k, v in row.items() if v})
        else:
            merged[project_id] = dict(row)
            order.append(project_id)
    added = 0
    for row in rows:
        project_id = str(row.get("project_id", "")).strip()
        if not project_id:
            continue
        normalized = {header: str(row.get(header, "") or "") for header in PROJECT_HEADERS}
        if project_id not in merged:
            merged[project_id] = normalized
            order.append(project_id)
            added += 1
        else:
            # Refresh fields returned by Square Yards without erasing existing non-empty metadata.
            merged[project_id].update({k: v for k, v in normalized.items() if v})
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=PROJECT_HEADERS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(merged[project_id] for project_id in order)
    return added, removed


def _trusted_source_url(pillar: str, url: str) -> bool:
    try:
        host = (urlsplit(url).hostname or "").casefold().removeprefix("www.")
    except ValueError:
        return False
    if not host:
        return False
    if pillar in {"price_trends", "infrastructure"}:
        if host.endswith((".gov.in", ".nic.in")) or host in {"gov.in", "nic.in", "mcgm.gov.in"}:
            return True
        return pillar == "infrastructure" and host in {"mahametro.org", "mmrda.maharashtra.gov.in", "cidco.maharashtra.gov.in"}
    bank_domains = (
        "pnb.bank.in", "pnbindia.in", "sbi.co.in", "hdfc.bank.in", "hdfc.com",
        "bankofbaroda.bank.in", "bankofbaroda.in", "axisbank.com", "axis.bank.in",
        "unionbankofindia.bank.in", "unionbankofindia.co.in", "indianbank.in",
        "indianbank.bank.in", "kotak.bank.in", "kotak.com", "canarabank.bank.in",
        "canarabank.com", "bankofindia.bank.in", "bankofindia.co.in", "icicibank.com",
    )
    return any(host == domain or host.endswith("." + domain) for domain in bank_domains)


def _url_identity(url: str) -> tuple[str, str]:
    parsed = urlsplit(str(url).strip())
    return (parsed.hostname.casefold() if parsed.hostname else "", parsed.path.rstrip("/").casefold())


def _project_name_identity(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


def _persist_research_pass(folder: Path, city: str, projects: list[dict[str, str]], findings: dict[str, Any], cited_urls: set[str]) -> dict[str, int]:
    citation_keys = {_url_identity(url) for url in cited_urls}
    counts = {"sources_added": 0, "price_candidates_added": 0, "finance_candidates_added": 0,
              "infrastructure_candidates_added": 0, "rejected_nonofficial_or_uncited_candidates": 0,
              "grounding_redirect_review_leads": 0}

    def valid_urls(values: Any, pillar: str) -> list[dict[str, Any]]:
        output = []
        for row in values if isinstance(values, list) else []:
            if not isinstance(row, dict):
                counts["rejected_nonofficial_or_uncited_candidates"] += 1
                continue
            source_url = str(row.get("source_url") or "").strip()
            is_cited = _url_identity(source_url) in citation_keys
            try:
                host = (urlsplit(source_url).hostname or "").casefold()
                is_grounding_link = host == "vertexaisearch.cloud.google.com" and urlsplit(source_url).path.startswith("/grounding-api-redirect/")
            except ValueError:
                host, is_grounding_link = "", False
            is_direct_trusted = _trusted_source_url(pillar, source_url)
            if (is_cited and (is_direct_trusted or is_grounding_link)) or is_direct_trusted:
                candidate = dict(row)
                candidate["_source_needs_review"] = is_grounding_link or not is_cited
                if candidate["_source_needs_review"]:
                    counts["grounding_redirect_review_leads"] += 1
                output.append(candidate)
            else:
                counts["rejected_nonofficial_or_uncited_candidates"] += 1
        return output

    captured = date.today().isoformat()
    source_rows = []
    for row in findings.get("sources", []) if isinstance(findings.get("sources"), list) else []:
        pillar = row.get("pillar") if isinstance(row, dict) else None
        if pillar not in {"price_trends", "finance", "infrastructure"}:
            counts["rejected_nonofficial_or_uncited_candidates"] += 1
            continue
        if not valid_urls([row], pillar):
            continue
        notes = str(row.get("notes") or "")
        if row.get("_source_needs_review"):
            wording = "Google Search grounding link; open it and confirm the final destination is the named official source before using this record." if "vertexaisearch.cloud.google.com" in str(row.get("source_url") or "") else "AI-reported official URL could not be matched directly to the grounding citation; verify the page supports the record."
            notes = (notes + " " + wording).strip()
        source_rows.append({"pillar": row.get("pillar"), "source_name": row.get("source_name"), "source_url": row.get("source_url"), "source_title": row.get("source_title"), "access_status": "needs_review" if row.get("_source_needs_review") else row.get("access_status"), "checked_at": captured, "notes": notes})
    counts["sources_added"] = _merge_csv(folder / "sources.csv", SOURCE_HEADERS, source_rows, ("pillar", "source_url"))

    prices = []
    for row in valid_urls(findings.get("price_trends", []), "price_trends"):
        rates = row.get("rates") if isinstance(row.get("rates"), dict) else {}
        item = {k: row.get(k, "") for k in PRICE_HEADERS}
        item.update({k: rates.get(k, "") for k in RATE_COLUMNS})
        item.update(city=city, extraction_status="extracted", extraction_note=(str(row.get("extraction_note", "")) + " AI-discovered candidate; verify exact source row, unit, page and locality before marking reviewed.").strip())
        if item.get("printed_page") and item.get("serial_no") and item.get("guideline_place") and item.get("financial_year"):
            prices.append(item)
    counts["price_candidates_added"] = _merge_csv(folder / "price_trends.csv", PRICE_HEADERS, prices, ("district", "financial_year", "guideline_place", "serial_no"))

    finance = []
    exact_project_names: dict[str, list[str]] = {}
    for project in projects:
        exact_project_names.setdefault(_project_name_identity(project.get("project_name")), []).append(project["project_id"])
    for row in valid_urls(findings.get("finance", []), "finance"):
        name_key = _project_name_identity(row.get("listed_project_name"))
        matching_ids = exact_project_names.get(name_key, []) if name_key else []
        pid = matching_ids[0] if len(matching_ids) == 1 else ""
        note = str(row.get("match_note", ""))
        if pid:
            note += " Unique normalized project-name candidate from the complete Square Yards catalog; verify builder/phase before confirming."
        if row.get("_source_needs_review"):
            note += " Source URL needs review: confirm it resolves to the bank's official listing and supports the project entry."
        finance.append({**row, "project_id": pid, "match_status": "possible", "match_note": (note + " AI candidate; verify project identity and phase against the bank source.").strip(), "captured_at": captured})
    counts["finance_candidates_added"] = _merge_csv(folder / "finance.csv", FINANCE_HEADERS, finance, ("financier_name", "source_title", "listed_project_name"))

    infra = []
    for row in valid_urls(findings.get("infrastructure", []), "infrastructure"):
        source_key = slugify(str(row.get("source_title") or "source"))[:70]
        localities = row.get("locality_names") if isinstance(row.get("locality_names"), list) else []
        import_note = "AI-discovered candidate; verify source wording, status, dates and locality before activation."
        if row.get("_source_needs_review"):
            import_note += " Source URL needs review: confirm it resolves to the named official source and supports the project details."
        infra.append({**row, "source_key": source_key, "city": city, "source_type": row.get("source_type") if row.get("source_type") in {"webpage", "pdf"} else "webpage", "locality_names": json.dumps(localities, ensure_ascii=False), "is_active": "0", "imported_at": captured + " 00:00:00", "import_note": import_note})
    counts["infrastructure_candidates_added"] = _merge_csv(folder / "infrastructure.csv", INFRA_HEADERS, infra, ("source_key", "project_name", "area_name"))
    return counts


def collect_city(city: str, *, projects_only: bool = False, page_size: int = 20, max_pages: int = 100, ai_provider: str = "codex", refresh_research: bool = False) -> tuple[Path, dict[str, Any]]:
    folder = CITY_ROOT / slugify(city)
    if not folder.exists():
        raise ValueError(f"No package for {city!r}. Run init-city first.")
    projects = fetch_city_projects(city, page_size, max_pages)
    print(f"[Projects] Received {len(projects)} unique IDs. Merging by project_id (existing IDs are updated, not duplicated)...", flush=True)
    added, removed = _merge_project_catalog(folder / "projects.csv", projects)
    counts = {"projects_added": added, "duplicate_project_rows_removed": removed, "projects_in_catalog": len(read_csv(folder / "projects.csv", set(PROJECT_HEADERS)))}
    print(f"[Projects] Catalog saved: {counts['projects_in_catalog']} rows, {added} new IDs, {removed} duplicate/empty-ID rows removed.", flush=True)
    if projects_only:
        return folder, counts
    evidence_counts = {"sources_added": 0, "price_candidates_added": 0, "finance_candidates_added": 0,
                       "infrastructure_candidates_added": 0, "rejected_nonofficial_or_uncited_candidates": 0,
                       "grounding_redirect_review_leads": 0}

    def save_completed_task(task_id: str, pillar: str, findings: dict[str, Any], cited_urls: set[str]) -> None:
        partial = {"sources": findings.get("sources", []), "price_trends": [], "finance": [], "infrastructure": []}
        partial[pillar] = findings.get(pillar, [])
        saved = _persist_research_pass(folder, city, projects, partial, cited_urls)
        for key, value in saved.items():
            evidence_counts[key] += value
        print(f"[CSV] Saved results for {task_id}: sources +{saved['sources_added']}, price +{saved['price_candidates_added']}, finance +{saved['finance_candidates_added']}, infrastructure +{saved['infrastructure_candidates_added']}.", flush=True)

    try:
        findings, _ = _city_research(city, projects, ai_provider, on_task_complete=save_completed_task, refresh=refresh_research)
    except (ValueError, OSError) as exc:
        # The live project catalog is already safely merged and must still be
        # importable when a separate evidence provider is temporarily down.
        counts["ai_research_error"] = str(exc)
        print(f"[AI research] Could not complete this run: {exc}", flush=True)
        print("[AI research] Continuing with the saved project catalog; no new evidence candidates were added.", flush=True)
        return folder, counts
    counts.update(evidence_counts)
    counts["research_errors"] = findings.get("_research_errors", [])
    return folder, counts


def ensure_city(row: dict[str, str], city: str, filename: str) -> None:
    value = row.get("city", "").strip()
    if value.casefold() != city.casefold():
        raise ValueError(f"{filename} contains city {value!r}; expected {city!r}.")


def generate_projects(city: str, rows: list[dict[str, str]]) -> str:
    if not rows:
        raise ValueError("projects.csv is empty. Load the city's project catalog first.")
    ids: set[int] = set()
    values = []
    for row in rows:
        ensure_city(row, city, "projects.csv")
        if not row.get("project_name", "").strip():
            raise ValueError("Every projects.csv row needs a project_name.")
        project_id = int(sql_number(row["project_id"], integer=True))
        if project_id <= 0 or project_id in ids:
            raise ValueError(f"Duplicate or invalid project_id: {project_id}")
        ids.add(project_id)
        values.append("(" + ", ".join([
            str(project_id), sql_text(row["project_name"]), sql_text(city),
            sql_text(row.get("locality")), sql_text(row.get("property_type")),
            sql_text(row.get("project_source") or "Square Yards"),
        ]) + ")")
    statements = [
        "-- City project catalog. Inserts/upserts only; no schema changes.",
        f"USE `{DATABASE}`;",
    ]
    for offset in range(0, len(values), 250):
        batch = values[offset:offset + 250]
        statements.append(
            "INSERT INTO projects (project_id, project_name, city, locality, property_type, project_source) VALUES\n"
            + ",\n".join(batch)
            + "\nON DUPLICATE KEY UPDATE project_name=VALUES(project_name), city=VALUES(city), "
            "locality=VALUES(locality), property_type=VALUES(property_type), project_source=VALUES(project_source);"
        )
    statements.append(f"-- Projects included: {len(values)}")
    return "\n\n".join(statements) + "\n"


def generate_price(city: str, rows: list[dict[str, str]]) -> str:
    required = {"city", "district", "financial_year", "file_name", "source_url", "printed_page", "serial_no", "guideline_place"}
    for row in rows:
        ensure_city(row, city, "price_trends.csv")
        missing = [key for key in required if not row.get(key)]
        if missing:
            raise ValueError(f"price_trends.csv row missing: {', '.join(missing)}")
        if not any(row.get(column, "").strip() for column in RATE_COLUMNS):
            raise ValueError("Each price row must contain at least one rate in a supported existing guideline column.")
    out = ["-- Shared price-trend import. Maps to the existing guideline schema for the selected city.", f"USE `{DATABASE}`;", "START TRANSACTION;"]
    sources = sorted({(r["district"], r["financial_year"], f"{slugify(city)}__{r['file_name']}", r["source_url"]) for r in rows})
    for district, year, filename, url in sources:
        if len(filename) > 255:
            raise ValueError("City-prefixed guideline file_name exceeds the existing 255-character column limit.")
        out.append(
            "INSERT INTO guideline_sources (city,district,financial_year,file_name,source_url) VALUES "
            f"({sql_text(city)},{sql_text(district)},{sql_text(year)},{sql_text(filename)},{sql_text(url)}) "
            "ON DUPLICATE KEY UPDATE city=VALUES(city), source_url=VALUES(source_url);"
        )
    fields = ["printed_page", "serial_no", "urban_local_body", "sub_area", "ward", "tehsil", "guideline_place", "normalized_place", *RATE_COLUMNS, "extraction_status", "extraction_note"]
    updates = ", ".join(f"{field}=VALUES({field})" for field in fields if field not in {"printed_page", "serial_no"})
    for row in rows:
        vals = [sql_number(row["printed_page"], integer=True), sql_number(row["serial_no"], integer=True)]
        vals += [sql_text(row.get(field)) for field in ["urban_local_body", "sub_area", "ward", "tehsil", "guideline_place"]]
        vals += [sql_text(row.get("normalized_place") or re.sub(r"[^A-Z0-9]+", " ", row["guideline_place"].upper()).strip())]
        vals += [sql_number(row.get(col)) for col in RATE_COLUMNS]
        vals += [sql_text(row.get("extraction_status") or "extracted"), sql_text(row.get("extraction_note"))]
        out.append(
            f"INSERT INTO guideline_entries (source_id,{','.join(fields)}) "
            f"SELECT s.source_id,{','.join(vals)} FROM guideline_sources s "
            f"WHERE s.city={sql_text(city)} AND s.district={sql_text(row['district'])} "
            f"AND s.financial_year={sql_text(row['financial_year'])} AND s.file_name={sql_text(slugify(city) + '__' + row['file_name'])} "
            f"ON DUPLICATE KEY UPDATE {updates};"
        )
    out.append("COMMIT;")
    out.append(f"-- Dated rate rows included: {len(rows)}. Empty means no supported rates were imported.")
    return "\n\n".join(out) + "\n"


def generate_finance(city: str, rows: list[dict[str, str]], project_ids: set[int]) -> str:
    statuses = {"exact", "listed", "possible", "unmatched"}
    for row in rows:
        if row.get("project_id"):
            project_id = int(sql_number(row["project_id"], integer=True))
            if project_id not in project_ids:
                raise ValueError(f"finance.csv project_id {project_id} is not in this city's projects.csv")
        if row.get("match_status") and row["match_status"] not in statuses:
            raise ValueError("finance.csv match_status must be exact, listed, possible, or unmatched.")
        for col in ("financier_name", "source_title", "listed_project_name"):
            if not row.get(col):
                raise ValueError(f"finance.csv requires {col} on every record.")
    out = ["-- Bank reference import. Uses existing finance tables only.", f"USE `{DATABASE}`;", "START TRANSACTION;"]
    sources = sorted({(r["financier_name"], r["source_title"], r.get("source_type") or "official_website", r.get("source_url", ""), r.get("source_note", ""), r.get("source_captured_at", "")) for r in rows})
    for bank, title, typ, url, note, captured in sources:
        out.append(
            "INSERT INTO financier_reference_sources (financier_name,source_title,source_type,source_url,source_note,captured_at) VALUES "
            f"({sql_text(bank)},{sql_text(title)},{sql_text(typ)},{sql_text(url)},{sql_text(note)},{sql_text(captured)}) "
            "ON DUPLICATE KEY UPDATE source_url=VALUES(source_url),source_note=VALUES(source_note),captured_at=VALUES(captured_at);"
        )
    for row in rows:
        pid = sql_number(row.get("project_id"), integer=True)
        out.append(
            "INSERT INTO financier_project_references "
            "(source_id,project_id,listed_project_name,builder_name,bank_project_code,match_status,match_note,captured_at) "
            f"SELECT s.source_id,{pid},{sql_text(row['listed_project_name'])},{sql_text(row.get('builder_name'))},"
            f"{sql_text(row.get('bank_project_code'))},{sql_text(row.get('match_status') or 'listed')},"
            f"{sql_text(row.get('match_note'))},{sql_text(row.get('captured_at') or row.get('source_captured_at'))} "
            f"FROM financier_reference_sources s WHERE s.financier_name={sql_text(row['financier_name'])} "
            f"AND s.source_title={sql_text(row['source_title'])} "
            "ON DUPLICATE KEY UPDATE project_id=VALUES(project_id),builder_name=VALUES(builder_name),"
            "bank_project_code=VALUES(bank_project_code),match_status=VALUES(match_status),"
            "match_note=VALUES(match_note),captured_at=VALUES(captured_at);"
        )
    out += ["COMMIT;", f"-- Finance reference rows included: {len(rows)}."]
    return "\n\n".join(out) + "\n"


def generate_infrastructure(city: str, rows: list[dict[str, str]]) -> str:
    scopes = {"locality", "area_based", "citywide", "unlocated"}
    statuses = {"proposed", "tendering", "dpr_preparation", "awaiting_land_transfer", "work_in_progress", "completed_reported", "unknown"}
    source_types = {"webpage", "pdf"}
    for row in rows:
        ensure_city(row, city, "infrastructure.csv")
        for col in ("source_key", "source_title", "project_name"):
            if not row.get(col):
                raise ValueError(f"infrastructure.csv requires {col} on every record.")
        if row.get("source_type") and row["source_type"] not in source_types:
            raise ValueError("infrastructure.csv source_type must be webpage or pdf.")
        if row.get("scope") and row["scope"] not in scopes:
            raise ValueError(f"Invalid infrastructure scope: {row['scope']}")
        if row.get("status_code") and row["status_code"] not in statuses:
            raise ValueError(f"Invalid infrastructure status_code: {row['status_code']}")
        sql_json(row.get("locality_names"), default=[])
        if row.get("raw_record"):
            sql_json(row["raw_record"], default={})
    out = ["-- Infrastructure import. Uses existing infrastructure tables only.", f"USE `{DATABASE}`;", "START TRANSACTION;"]
    sources: dict[str, dict[str, str]] = {}
    for row in rows:
        stored_key = slugify(city) + "__" + row["source_key"]
        if len(stored_key) > 100:
            raise ValueError("City-prefixed infrastructure source_key exceeds the existing 100-character column limit.")
        prior = sources.setdefault(stored_key, row)
        for key in ("source_title", "source_url"):
            if prior.get(key) != row.get(key):
                raise ValueError(f"Rows sharing source_key {stored_key!r} must have the same {key}.")
    for key, row in sorted(sources.items()):
        out.append(
            "INSERT INTO infrastructure_sources (source_key,source_type,source_title,source_url,file_name,fetched_at,content_sha256,extracted_content,import_note) VALUES "
                f"({sql_text(key)},{sql_text(row.get('source_type') or 'webpage')},{sql_text(row['source_title'])},"
            f"{sql_text(row.get('source_url'))},{sql_text(row.get('file_name'))},{sql_text(row.get('fetched_at') or datetime.now().strftime('%Y-%m-%d %H:%M:%S'))},"
            f"{sql_text(row.get('content_sha256'))},{sql_text(row.get('extracted_content'))},{sql_text(row.get('import_note'))}) "
            "ON DUPLICATE KEY UPDATE source_type=VALUES(source_type),source_title=VALUES(source_title),"
            "source_url=VALUES(source_url),fetched_at=VALUES(fetched_at),import_note=VALUES(import_note);"
        )
    cols = ["source_item_key", "project_name", "city", "area_name", "locality_names", "scope", "category", "program_name", "status_code", "status_label", "description", "capacity_value", "capacity_unit", "source_reference", "raw_record", "is_active", "imported_at"]
    updates = ",".join(f"{c}=VALUES({c})" for c in cols if c not in {"source_item_key", "imported_at"})
    for row in rows:
        stable = row.get("source_item_key") or hashlib.sha256((row["source_key"] + "|" + row["project_name"] + "|" + row.get("area_name", "") + "|" + row.get("source_reference", "")).encode("utf-8")).hexdigest()
        locals_json = sql_json(row.get("locality_names"), default=[])
        raw_json = sql_json(row.get("raw_record"), default={}) if row.get("raw_record") else "NULL"
        out.append(
            f"INSERT INTO infrastructure_projects (source_id,{','.join(cols)}) "
            f"SELECT s.source_id,{sql_text(stable)},{sql_text(row['project_name'])},{sql_text(city)},{sql_text(row.get('area_name'))},"
            f"{locals_json},{sql_text(row.get('scope') or 'unlocated')},{sql_text(row.get('category'))},"
            f"{sql_text(row.get('program_name'))},{sql_text(row.get('status_code') or 'unknown')},"
            f"{sql_text(row.get('status_label') or 'Status not stated by source')},{sql_text(row.get('description'))},"
            f"{sql_number(row.get('capacity_value'))},{sql_text(row.get('capacity_unit'))},{sql_text(row.get('source_reference'))},"
            f"{raw_json},{sql_number(row.get('is_active') or '1', integer=True)},"
            f"{sql_text(row.get('imported_at') or date.today().isoformat() + ' 00:00:00')} "
            f"FROM infrastructure_sources s WHERE s.source_key={sql_text(slugify(city) + '__' + row['source_key'])} "
            f"ON DUPLICATE KEY UPDATE {updates};"
        )
    out += ["COMMIT;", f"-- Infrastructure project rows included: {len(rows)}."]
    return "\n\n".join(out) + "\n"


def init_city(city: str) -> Path:
    slug = slugify(city)
    folder = CITY_ROOT / slug
    if folder.exists() and any(folder.iterdir()):
        raise ValueError(f"City package already exists and is not empty: {folder}")
    folder.mkdir(parents=True, exist_ok=True)
    write_csv(folder / "projects.csv", PROJECT_HEADERS)
    write_csv(folder / "price_trends.csv", PRICE_HEADERS)
    write_csv(folder / "finance.csv", FINANCE_HEADERS)
    write_csv(folder / "infrastructure.csv", INFRA_HEADERS)
    write_csv(folder / "sources.csv", SOURCE_HEADERS)
    write_csv(folder / "research_tasks.csv", RESEARCH_TASK_HEADERS)
    (folder / "README.md").write_text(
        f"# {city} onboarding package\n\n"
        "Run collection first, review the CSV contents directly, then build and apply SQL with the commands below.\n\n"
        "1. Run `py city_onboarding.py collect-city --city \"" + city + "\"` to fetch the Square Yards catalog and discover cited source/evidence candidates using your signed-in Codex CLI.\n"
        "   If you only want the Square Yards catalog, run `py city_onboarding.py collect-projects --city \"" + city + "\"` (no AI access needed).\n"
        "2. Review `research_tasks.csv`, `sources.csv`, and the three evidence CSVs directly against the linked official sources. Correct or delete unsupported rows. No review-marker edits are required. AI output is a lead, not verification.\n"
        "3. Run `py city_onboarding.py build --city \"" + city + "\"`; this converts all remaining valid rows in the four data CSVs to SQL. Inspect the generated files.\n"
        "4. Run `py city_onboarding.py apply --city \"" + city + "\" --dry-run`, then `--execute` after review; enter the city name when prompted.\n\n"
        "The builder writes only INSERT/UPSERT SQL for the existing `nriease_guidelines` tables. It never creates tables.\n"
        "Price rows must fit an existing rate column exactly in meaning and unit; do not relabel unlike categories to force an import.\n"
        "Only CSV files hold the city catalog, source audit, and evidence candidates. Research is run fresh each time; partial findings from a completed run are kept in CSVs. CAPTCHA-protected records require a person or an alternate permitted bulk source.\n",
        encoding="utf-8",
    )
    return folder


def build_city(city: str) -> tuple[Path, dict[str, int]]:
    folder = CITY_ROOT / slugify(city)
    if not folder.exists():
        raise ValueError(f"No package for {city!r}. Run init-city first.")
    project_rows = read_csv(folder / "projects.csv", {"project_id", "project_name", "city", "locality"})
    all_price_rows = read_csv(folder / "price_trends.csv", {"city", "district", "financial_year", "file_name", "source_url", "printed_page", "serial_no", "guideline_place"})
    all_finance_rows = read_csv(folder / "finance.csv", {"financier_name", "source_title", "listed_project_name"})
    all_infra_rows = read_csv(folder / "infrastructure.csv", {"source_key", "source_title", "project_name", "city"})
    # The CSVs are the review surface: users correct or remove unsupported
    # rows there. Build every remaining valid row without requiring marker edits.
    price_rows = all_price_rows
    finance_rows = all_finance_rows
    infra_rows = all_infra_rows
    ids = {int(row["project_id"]) for row in project_rows}
    sqls = {
        "projects.sql": generate_projects(city, project_rows),
        "price_trends.sql": generate_price(city, price_rows),
        "financier.sql": generate_finance(city, finance_rows, ids),
        "infrastructure.sql": generate_infrastructure(city, infra_rows),
    }
    for name, content in sqls.items():
        (folder / name).write_text(content, encoding="utf-8")
    counts = {
        "projects": len(project_rows), "price_trend_rows": len(price_rows),
        "finance_references": len(finance_rows), "infrastructure_projects": len(infra_rows),
    }
    return folder, counts


def ensure_city_package(city: str) -> Path:
    folder = CITY_ROOT / slugify(city)
    if not folder.exists():
        return init_city(city)
    required_files = ("projects.csv", "price_trends.csv", "finance.csv", "infrastructure.csv", "sources.csv")
    missing = [name for name in required_files if not (folder / name).exists()]
    if missing:
        raise ValueError(f"Existing city folder is incomplete; missing {', '.join(missing)}. Move it aside or restore those files before continuing.")
    task_log = folder / "research_tasks.csv"
    if not task_log.exists():
        write_csv(task_log, RESEARCH_TASK_HEADERS)
    return folder


def split_sql(script: str) -> list[str]:
    """Split straightforward MySQL scripts while respecting quotes and comments."""
    result: list[str] = []
    buf: list[str] = []
    quote: str | None = None
    line_comment = False
    block_comment = False
    i = 0
    while i < len(script):
        ch = script[i]
        nxt = script[i + 1] if i + 1 < len(script) else ""
        if line_comment:
            if ch in "\r\n":
                line_comment = False
                buf.append("\n")
            i += 1
            continue
        if block_comment:
            if ch == "*" and nxt == "/":
                block_comment = False
                i += 2
            else:
                i += 1
            continue
        if quote:
            buf.append(ch)
            if ch == "\\" and nxt:
                buf.append(nxt)
                i += 2
                continue
            if ch == quote:
                if nxt == quote:
                    buf.append(nxt)
                    i += 2
                    continue
                quote = None
            i += 1
            continue
        if ch in ("'", '"', "`"):
            quote = ch
            buf.append(ch)
            i += 1
            continue
        if ch == "#" or (ch == "-" and nxt == "-" and (i + 2 == len(script) or script[i + 2].isspace())):
            line_comment = True
            i += 1 if ch == "#" else 2
            continue
        if ch == "/" and nxt == "*":
            block_comment = True
            i += 2
            continue
        if ch == ";":
            statement = "".join(buf).strip()
            if statement:
                result.append(statement)
            buf = []
        else:
            buf.append(ch)
        i += 1
    if quote or block_comment:
        raise ValueError("SQL has an unterminated quote or block comment.")
    tail = "".join(buf).strip()
    if tail:
        result.append(tail)
    return result


def validate_sql_package(folder: Path, city: str) -> dict[str, int]:
    summary = {}
    for name in PILLAR_FILES:
        path = folder / name
        if not path.exists():
            raise ValueError(f"Missing generated SQL file: {name}. Run build first.")
        statements = split_sql(path.read_text(encoding="utf-8-sig"))
        for stmt in statements:
            command = re.match(r"\s*([A-Za-z]+)", stmt)
            if not command:
                continue
            verb = command.group(1).upper()
            if verb not in {"USE", "START", "COMMIT", "INSERT"}:
                raise ValueError(f"Blocked SQL operation {verb} in {name}; schema and destructive changes are not allowed.")
            if verb in {"INSERT", "UPDATE"}:
                match = re.search(r"\b(?:INSERT\s+(?:IGNORE\s+)?INTO|UPDATE)\s+`?([A-Za-z0-9_]+)`?", stmt, re.I)
                if not match or match.group(1).lower() not in ALLOWED_TABLES:
                    target = match.group(1) if match else "unknown"
                    raise ValueError(f"Blocked write target {target!r} in {name}; only existing platform tables are allowed.")
            if verb == "USE":
                selected = re.search(r"\bUSE\s+`?([A-Za-z0-9_]+)`?", stmt, re.I)
                if selected and selected.group(1) != DATABASE:
                    raise ValueError(f"{name} selects {selected.group(1)!r}; expected existing database {DATABASE!r}.")
        summary[name] = len(statements)
    return summary


def db_connect():
    try:
        import mysql.connector
    except ImportError as exc:
        raise ValueError("Install mysql-connector-python before applying SQL: py -m pip install mysql-connector-python") from exc
    password = os.environ.get("MYSQL_PASSWORD")
    if password is None:
        password = getpass.getpass("MySQL password (input hidden; not saved): ")
    config = {
        "host": os.environ.get("MYSQL_HOST", "127.0.0.1"),
        "port": int(os.environ.get("MYSQL_PORT", "3306")),
        "user": os.environ.get("MYSQL_USER", "root"),
        "password": password,
        "connection_timeout": 10,
        "autocommit": False,
    }
    database = os.environ.get("MYSQL_DATABASE", DATABASE)
    if database != DATABASE:
        raise ValueError(f"MYSQL_DATABASE must be {DATABASE!r} for this pipeline.")
    try:
        return mysql.connector.connect(**config, database=DATABASE)
    except mysql.connector.Error as error:
        if getattr(error, "errno", None) != 1049:  # Unknown database
            raise
        # Bootstrap a missing database only after MySQL confirms it is absent.
        server_connection = mysql.connector.connect(**config)
        try:
            cursor = server_connection.cursor()
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{DATABASE}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
            )
            cursor.close()
        finally:
            server_connection.close()
        return mysql.connector.connect(**config, database=DATABASE)


def ensure_schema(connection) -> list[str]:
    """Create absent standard tables from the reviewed schema file; never alter existing tables."""
    if not SCHEMA_FILE.exists():
        raise ValueError(f"Schema definition file is missing: {SCHEMA_FILE.name}")
    cursor = connection.cursor()
    cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema=%s", (DATABASE,))
    present = {row[0].lower() for row in cursor.fetchall()}
    missing = set(REQUIRED_TABLES) - present
    cursor.close()
    if not missing:
        return []

    create_statements: dict[str, str] = {}
    for statement in split_sql(SCHEMA_FILE.read_text(encoding="utf-8-sig")):
        if re.match(r"\s*CREATE\s+DATABASE\b", statement, re.I) or re.match(r"\s*USE\b", statement, re.I):
            continue
        match = re.match(r"\s*CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+`?([A-Za-z0-9_]+)`?", statement, re.I)
        if not match:
            raise ValueError("Schema file may contain only CREATE DATABASE, USE, and CREATE TABLE IF NOT EXISTS statements.")
        table = match.group(1).lower()
        if table not in REQUIRED_TABLES:
            raise ValueError(f"Schema file contains unapproved table {table!r}.")
        create_statements[table] = statement
    absent_definitions = missing - set(create_statements)
    if absent_definitions:
        raise ValueError("No standard schema definition found for: " + ", ".join(sorted(absent_definitions)))

    # Keep schema-file ordering so referenced parent tables are created first.
    for statement in split_sql(SCHEMA_FILE.read_text(encoding="utf-8-sig")):
        match = re.match(r"\s*CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+`?([A-Za-z0-9_]+)`?", statement, re.I)
        if match and match.group(1).lower() in missing:
            cursor = connection.cursor()
            try:
                cursor.execute(statement)
            finally:
                cursor.close()
    cursor = connection.cursor()
    cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema=%s", (DATABASE,))
    now_present = {row[0].lower() for row in cursor.fetchall()}
    cursor.close()
    still_missing = REQUIRED_TABLES - now_present
    if still_missing:
        raise ValueError("Schema bootstrap did not create required tables: " + ", ".join(sorted(still_missing)))
    return sorted(missing)


def apply_package(folder: Path, city: str) -> None:
    scripts = [(folder / name, split_sql((folder / name).read_text(encoding="utf-8-sig"))) for name in PILLAR_FILES]
    connection = db_connect()
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT DATABASE()")
        active_db = cursor.fetchone()[0]
        if active_db != DATABASE:
            raise ValueError(f"Connected to {active_db!r}; expected {DATABASE!r}.")
        created = ensure_schema(connection)
        print("Created missing standard tables: " + (", ".join(created) if created else "none; schema already present"))
        project_sql = (folder / "projects.sql").read_text(encoding="utf-8-sig")
        project_ids = [int(value) for value in re.findall(r"\(\s*(\d+)\s*,", project_sql)]
        if project_ids:
            placeholders = ",".join(["%s"] * len(project_ids))
            cursor.execute(
                f"SELECT project_id, city FROM projects WHERE project_id IN ({placeholders}) AND LOWER(city) <> LOWER(%s)",
                (*project_ids, city),
            )
            conflicts = cursor.fetchall()
            if conflicts:
                raise ValueError("Project ID collision with another city; no SQL was applied: " + repr(conflicts[:10]))
        cursor.close()
        for path, statements in scripts:
            cursor = connection.cursor()
            for statement in statements:
                if re.match(r"\s*(USE|START\s+TRANSACTION|COMMIT)\b", statement, re.I):
                    continue
                cursor.execute(statement)
                if cursor.with_rows:
                    cursor.fetchall()
            cursor.close()
            print(f"Prepared {path.name}")
        connection.commit()
        print("Committed all four SQL files as one transaction.")
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT COUNT(*) AS project_count FROM projects WHERE LOWER(city)=LOWER(%s)", (city,))
        print(f"Database city project count for {city}: {cursor.fetchone()['project_count']}")
        cursor.close()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect, review, prepare, and apply city data using the existing NRI Ease schema.")
    commands = parser.add_subparsers(dest="command", required=True)
    setup = commands.add_parser("setup", help="Create the database if needed and create only missing standard tables.")
    init = commands.add_parser("init-city", help="Create CSV templates for a new city.")
    init.add_argument("--city", required=True)
    collect_projects = commands.add_parser("collect-projects", help="Fetch and merge the Square Yards residential catalog for a city.")
    collect_projects.add_argument("--city", required=True)
    collect_projects.add_argument("--page-size", type=int, default=20)
    collect_projects.add_argument("--max-pages", type=int, default=100)
    collect = commands.add_parser("collect-city", help="Fetch projects and use cited AI web search to prepare reviewable evidence candidates.")
    collect.add_argument("--city", required=True)
    collect.add_argument("--page-size", type=int, default=20)
    collect.add_argument("--max-pages", type=int, default=100)
    collect.add_argument("--ai-provider", choices=("codex", "gemini", "groq", "openai"), default="codex", help="Research provider; Codex CLI with live web search is the default and uses your local Codex sign-in.")
    collect.add_argument("--refresh-research", action="store_true", help="Repeat all searches, including tasks already marked completed in research_tasks.csv.")
    onboard = commands.add_parser("onboard-city", help="Create/reuse a city package, collect, and build SQL for review before import.")
    onboard.add_argument("--city", required=True)
    onboard.add_argument("--execute", action="store_true", help="Deprecated: collection always pauses for CSV/SQL review before database import.")
    onboard.add_argument("--page-size", type=int, default=20)
    onboard.add_argument("--max-pages", type=int, default=100)
    onboard.add_argument("--ai-provider", choices=("codex", "gemini", "groq", "openai"), default="codex", help="Research provider; Codex CLI with live web search is the default and uses your local Codex sign-in.")
    onboard.add_argument("--refresh-research", action="store_true", help="Repeat all searches, including tasks already marked completed in research_tasks.csv.")
    build = commands.add_parser("build", help="Generate the four idempotent SQL imports from all valid data CSV rows.")
    build.add_argument("--city", required=True)
    apply = commands.add_parser("apply", help="Validate and optionally apply the four SQL files.")
    apply.add_argument("--city", required=True)
    mode = apply.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "setup":
            connection = db_connect()
            try:
                created = ensure_schema(connection)
                print("Schema is ready. Created missing tables: " + (", ".join(created) if created else "none; all standard tables already existed"))
            finally:
                connection.close()
            return 0
        if args.command == "init-city":
            folder = init_city(args.city)
            print(f"Created onboarding package: {folder}")
            return 0
        if args.command == "collect-projects":
            if args.page_size < 1 or args.max_pages < 1:
                raise ValueError("--page-size and --max-pages must be positive integers.")
            folder, counts = collect_city(args.city, projects_only=True, page_size=args.page_size, max_pages=args.max_pages)
            print(f"Square Yards city catalog saved to: {folder / 'projects.csv'}")
            print(json.dumps(counts, indent=2))
            print("No database was changed.")
            return 0
        if args.command == "collect-city":
            if args.page_size < 1 or args.max_pages < 1:
                raise ValueError("--page-size and --max-pages must be positive integers.")
            folder, counts = collect_city(args.city, page_size=args.page_size, max_pages=args.max_pages, ai_provider=args.ai_provider, refresh_research=args.refresh_research)
            print(f"City research candidates saved in: {folder}")
            print(json.dumps(counts, indent=2))
            print("Review cited sources and candidates before build/import. No database was changed.")
            return 0
        if args.command == "onboard-city":
            if args.page_size < 1 or args.max_pages < 1:
                raise ValueError("--page-size and --max-pages must be positive integers.")
            folder = ensure_city_package(args.city)
            print(f"Using city package: {folder}")
            print("Step 1/4: Fetching and de-duplicating the Square Yards project catalog...", flush=True)
            collected_folder, collected = collect_city(args.city, page_size=args.page_size, max_pages=args.max_pages, ai_provider=args.ai_provider, refresh_research=args.refresh_research)
            print("Collection results:")
            print(json.dumps(collected, indent=2))
            print("Step 2/4: Building the four SQL packages...", flush=True)
            _, built = build_city(args.city)
            print("SQL package built:")
            print(json.dumps(built, indent=2))
            print("Review the CSV contents directly before applying. Build includes all valid rows in the data CSVs.")
            if collected.get("ai_research_error"):
                print("Database import stopped because AI research did not complete. Fix the research provider and rerun before importing this city package.", flush=True)
                return 1
            if args.execute:
                print("Automatic import is paused so you can review the CSVs and generated SQL first.")
                print(f"After review, run: py city_onboarding.py apply --city \"{args.city}\" --dry-run")
                print(f"Then apply with: py city_onboarding.py apply --city \"{args.city}\" --execute")
                return 0
            print("No database was changed. Review the CSVs and SQL, then run the apply command when ready.")
            return 0
        if args.command == "build":
            folder, counts = build_city(args.city)
            print(f"Generated SQL package: {folder}")
            print(json.dumps(counts, indent=2))
            print("No database was changed. Review all four SQL files before applying.")
            return 0
        folder = CITY_ROOT / slugify(args.city)
        counts = validate_sql_package(folder, args.city)
        print("SQL package is valid. No schema-changing or destructive statements found.")
        print(json.dumps(counts, indent=2))
        if args.dry_run:
            print("Dry run only; database was not contacted or changed.")
            return 0
        answer = input(f"Type {args.city} exactly to apply projects, price trends, finance, and infrastructure in that order: ").strip()
        if answer.casefold() != args.city.casefold():
            print("Confirmation did not match; nothing was applied.")
            return 2
        apply_package(folder, args.city)
        return 0
    except (ValueError, OSError, csv.Error) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"ERROR: operation failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
