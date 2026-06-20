#!/usr/bin/env python3
"""Validate access and upload PDFs to the SH Lab literature base."""

from __future__ import annotations

import argparse
import difflib
import html
import json
import mimetypes
import os
import re
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path


BASE_URL = "https://literature.shsciencegroup.online"
DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.I)


class ApiError(RuntimeError):
    pass


def token_from_value(value: str | None) -> str:
    token = value or os.environ.get("SH_LITERATURE_TOKEN", "")
    token = token.strip()
    if "user_token=" in token:
        parsed = urllib.parse.urlparse(token)
        query = urllib.parse.parse_qs(parsed.query)
        token = query.get("user_token", [""])[0].strip()
    if not token:
        raise ApiError("Missing token. Provide --token or set SH_LITERATURE_TOKEN.")
    return token


def api_url(path: str, token: str) -> str:
    url = urllib.parse.urljoin(BASE_URL, path)
    parsed = urllib.parse.urlparse(url)
    query = urllib.parse.parse_qs(parsed.query)
    query["user_token"] = [token]
    return urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(query, doseq=True)))


def request_json(path: str, token: str, method: str = "GET", data: bytes | None = None, headers: dict[str, str] | None = None) -> dict:
    request_headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) shsciencegroup-literature-skill/1.0",
    }
    if headers:
        request_headers.update(headers)
    req = urllib.request.Request(api_url(path, token), data=data, method=method, headers=request_headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = resp.read()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(body).get("detail") or body
        except json.JSONDecodeError:
            detail = body
        raise ApiError(f"HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise ApiError(f"Network error: {exc.reason}") from exc

    if not payload:
        return {}
    try:
        return json.loads(payload.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ApiError("API returned non-JSON response.") from exc


def library_data(token: str, project_id: str) -> dict:
    return request_json(f"/api/projects/{urllib.parse.quote(project_id)}/library", token)


def library_items(token: str, project_id: str) -> list[dict]:
    data = library_data(token, project_id)
    return data.get("items") or []


def validate_pdf(path: Path) -> None:
    if not path.is_absolute():
        raise ApiError(f"PDF path must be absolute: {path}")
    if not path.exists():
        raise ApiError(f"PDF does not exist: {path}")
    if not path.is_file():
        raise ApiError(f"PDF path is not a file: {path}")
    if path.suffix.lower() != ".pdf":
        raise ApiError(f"File is not a .pdf: {path}")


def collect_pdf_paths(pdf_dirs: list[str] | None, pdfs: list[str] | None, recursive: bool = False) -> list[Path]:
    candidates: list[Path] = []
    for value in pdf_dirs or []:
        directory = Path(value).expanduser().resolve()
        if not directory.exists():
            raise ApiError(f"PDF directory does not exist: {directory}")
        if not directory.is_dir():
            raise ApiError(f"PDF directory path is not a directory: {directory}")
        iterator = directory.rglob("*") if recursive else directory.iterdir()
        candidates.extend(path.resolve() for path in iterator if path.is_file() and path.suffix.lower() == ".pdf")

    for value in pdfs or []:
        pdf = Path(value).expanduser().resolve()
        validate_pdf(pdf)
        candidates.append(pdf)

    if not candidates:
        raise ApiError("No PDF files found. Provide --pdf-dir and/or --pdf.")

    deduped: dict[str, Path] = {}
    for path in candidates:
        key = str(path).casefold()
        deduped.setdefault(key, path)
    return sorted(deduped.values(), key=lambda path: str(path).casefold())


def visible_projects(token: str) -> list[dict]:
    data = request_json("/api/projects", token)
    return data.get("projects") or []


def validate_project(token: str, project_id: str) -> dict:
    user = request_json("/api/me", token)
    projects = visible_projects(token)
    match = next((p for p in projects if str(p.get("id")) == project_id), None)
    if not match:
        visible = ", ".join(str(p.get("id")) for p in projects) or "(none)"
        raise ApiError(f"Project '{project_id}' is not visible to this token. Visible projects: {visible}")
    return {"user": user, "project": match, "project_count": len(projects)}


def normalize_doi(value: str | None) -> str:
    if not value:
        return ""
    value = html.unescape(str(value)).strip().lower()
    value = re.sub(r"^(doi\s*[:：]?\s*|https?://(dx\.)?doi\.org/)", "", value)
    return value.rstrip(".。),;]")


def normalize_title(value: str | None) -> str:
    if not value:
        return ""
    text = html.unescape(str(value)).lower()
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("β", "beta").replace("Β", "beta")
    text = re.sub(r"[\u2010-\u2015−]", "-", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def title_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if len(a) > 24 and (a in b or b in a):
        return 0.97
    return difflib.SequenceMatcher(None, a, b).ratio()


def clean_doi_candidate(value: str) -> str:
    value = re.sub(r"\s+", "", value)
    return normalize_doi(value)


def extract_pdf_identity(pdf: Path) -> dict:
    identity = {"doi": "", "title": "", "source": {}}
    try:
        import pypdf
    except ImportError:
        return identity

    try:
        reader = pypdf.PdfReader(str(pdf))
    except Exception:
        return identity

    metadata = reader.metadata or {}
    metadata_title = html.unescape(str(metadata.get("/Title") or "")).strip()
    metadata_doi = normalize_doi(str(metadata.get("/WPS-ARTICLEDOI") or ""))
    if metadata_title:
        identity["title"] = metadata_title
        identity["source"]["title"] = "pdf_metadata"
    if metadata_doi:
        identity["doi"] = metadata_doi
        identity["source"]["doi"] = "pdf_metadata"

    first_text_parts = []
    for page in reader.pages[:2]:
        try:
            first_text_parts.append(page.extract_text() or "")
        except Exception:
            pass
    first_text = "\n".join(first_text_parts)
    if not identity["doi"]:
        match = DOI_RE.search(first_text)
        if match:
            identity["doi"] = clean_doi_candidate(match.group(0))
            identity["source"]["doi"] = "pdf_text"
    if not identity["title"]:
        lines = [line.strip() for line in first_text.splitlines() if line.strip()]
        for idx, line in enumerate(lines):
            if line.upper() == "ORIGINAL ARTICLE" and idx + 1 < len(lines):
                title_lines = []
                for candidate in lines[idx + 1 : idx + 4]:
                    if re.search(r"\d|\|@|received|accepted|doi", candidate, re.I):
                        break
                    title_lines.append(candidate)
                if title_lines:
                    identity["title"] = " ".join(title_lines)
                    identity["source"]["title"] = "pdf_text"
                    break
    return identity


def item_match_reasons(item: dict, pdf: Path, identity: dict) -> tuple[list[str], float]:
    reasons: list[str] = []
    score = 0.0
    local_name = pdf.name.casefold()
    for field in ("pdf_original_name", "pdf_filename"):
        if str(item.get(field) or "").casefold() == local_name:
            reasons.append(f"{field}_exact")
            score = max(score, 1.0)

    pdf_doi = normalize_doi(identity.get("doi"))
    item_doi = normalize_doi(item.get("doi"))
    if pdf_doi and item_doi and pdf_doi == item_doi:
        reasons.append("doi_exact")
        score = max(score, 1.0)

    pdf_title = normalize_title(identity.get("title"))
    item_title = normalize_title(item.get("title"))
    sim = title_similarity(pdf_title, item_title)
    if sim >= 0.92:
        reasons.append(f"title_similarity_{sim:.2f}")
        score = max(score, sim)

    return reasons, score


def find_existing_pdf_items_from_items(items: list[dict], pdf: Path) -> tuple[list[dict], dict]:
    identity = extract_pdf_identity(pdf)
    matches = []
    for item in items:
        reasons, score = item_match_reasons(item, pdf, identity)
        if reasons:
            enriched = dict(item)
            enriched["_match_reasons"] = reasons
            enriched["_match_score"] = score
            matches.append(enriched)
    matches.sort(key=lambda item: item.get("_match_score", 0), reverse=True)
    return matches, identity


def find_existing_pdf_items(token: str, project_id: str, pdf: Path) -> tuple[list[dict], dict]:
    return find_existing_pdf_items_from_items(library_items(token, project_id), pdf)


def compact_item(item: dict) -> dict:
    return {
        "id": item.get("id"),
        "title": item.get("title"),
        "doi": item.get("doi"),
        "year": item.get("year"),
        "journal": item.get("journal"),
        "category_id": item.get("category_id"),
        "status": item.get("status"),
        "pdf_filename": item.get("pdf_filename"),
        "pdf_original_name": item.get("pdf_original_name"),
        "match_reasons": item.get("_match_reasons", []),
        "match_score": item.get("_match_score", 0),
    }


def batch_plan_entries(pdf_paths: list[Path], items: list[dict]) -> list[dict]:
    entries = []
    for pdf in pdf_paths:
        try:
            validate_pdf(pdf)
            matches, identity = find_existing_pdf_items_from_items(items, pdf)
            entry = {
                "pdf": str(pdf),
                "filename": pdf.name,
                "pdf_identity": identity,
                "match_count": len(matches),
                "matches": [compact_item(item) for item in matches],
            }
            if len(matches) == 0:
                entry["action"] = "upload"
            elif len(matches) == 1:
                entry["action"] = "update-notes"
                entry["item_id"] = matches[0].get("id")
            else:
                entry["action"] = "ambiguous"
            entries.append(entry)
        except Exception as exc:
            entries.append({"pdf": str(pdf), "filename": pdf.name, "action": "error", "error": str(exc)})
    return entries


def item_patch_payload(item: dict, notes: str) -> dict:
    title = str(item.get("title") or "").strip()
    if not title:
        raise ApiError(f"Existing item {item.get('id')} has no title; refusing to patch ambiguous payload.")
    return {
        "title": title,
        "doi": str(item.get("doi") or ""),
        "authors": str(item.get("authors") or ""),
        "year": str(item.get("year") or ""),
        "journal": str(item.get("journal") or ""),
        "category_id": str(item.get("category_id") or "uncat"),
        "status": str(item.get("status") or "待整理"),
        "notes": notes,
    }


def update_item_notes(token: str, project_id: str, item_id: str, notes: str) -> dict:
    items = library_items(token, project_id)
    item = next((x for x in items if str(x.get("id")) == str(item_id)), None)
    if not item:
        raise ApiError(f"Item '{item_id}' is not visible in project '{project_id}'.")
    payload = json.dumps(item_patch_payload(item, notes), ensure_ascii=False).encode("utf-8")
    return request_json(
        f"/api/projects/{urllib.parse.quote(project_id)}/items/{urllib.parse.quote(str(item_id))}",
        token,
        method="PATCH",
        data=payload,
        headers={"Content-Type": "application/json"},
    )


def multipart_upload(token: str, project_id: str, pdf: Path, notes: str, category_id: str) -> dict:
    boundary = f"----shsciencegroupLiteratureSkill{uuid.uuid4().hex}"
    parts: list[bytes] = []

    def add_field(name: str, value: str) -> None:
        parts.append((f"--{boundary}\r\n" f'Content-Disposition: form-data; name="{name}"\r\n\r\n' f"{value}\r\n").encode("utf-8"))

    def add_file(name: str, file_path: Path) -> None:
        content_type = mimetypes.guess_type(file_path.name)[0] or "application/pdf"
        header = (f"--{boundary}\r\n" f'Content-Disposition: form-data; name="{name}"; filename="{file_path.name}"\r\n' f"Content-Type: {content_type}\r\n\r\n").encode("utf-8")
        parts.append(header)
        parts.append(file_path.read_bytes())
        parts.append(b"\r\n")

    add_file("files", pdf)
    add_field("category_id", category_id)
    add_field("notes", notes)
    parts.append(f"--{boundary}--\r\n".encode("utf-8"))

    body = b"".join(parts)
    headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
    return request_json(f"/api/projects/{urllib.parse.quote(project_id)}/upload", token, method="POST", data=body, headers=headers)


def cmd_check(args: argparse.Namespace) -> int:
    token = token_from_value(args.token)
    result = validate_project(token, args.project_id)
    print(json.dumps({"ok": True, **result}, ensure_ascii=False, indent=2))
    return 0


def cmd_find_existing(args: argparse.Namespace) -> int:
    token = token_from_value(args.token)
    pdf = Path(args.pdf)
    validate_pdf(pdf)
    validate_project(token, args.project_id)
    matches, identity = find_existing_pdf_items(token, args.project_id, pdf)
    print(json.dumps({"ok": True, "match_count": len(matches), "matches": matches, "pdf_identity": identity, "matched_by": "doi_or_title_or_original_name_or_pdf_filename"}, ensure_ascii=False, indent=2))
    return 0


def cmd_plan_batch(args: argparse.Namespace) -> int:
    token = token_from_value(args.token)
    project = validate_project(token, args.project_id)["project"]
    pdf_paths = collect_pdf_paths(args.pdf_dir, args.pdf, recursive=args.recursive)
    items = library_items(token, args.project_id)
    entries = batch_plan_entries(pdf_paths, items)
    summary = {
        "upload": sum(1 for entry in entries if entry.get("action") == "upload"),
        "update-notes": sum(1 for entry in entries if entry.get("action") == "update-notes"),
        "ambiguous": sum(1 for entry in entries if entry.get("action") == "ambiguous"),
        "error": sum(1 for entry in entries if entry.get("action") == "error"),
    }
    print(json.dumps({"ok": True, "project": project, "pdf_count": len(pdf_paths), "summary": summary, "plan": entries}, ensure_ascii=False, indent=2))
    return 0

def cmd_upload(args: argparse.Namespace) -> int:
    token = token_from_value(args.token)
    pdf = Path(args.pdf)
    validate_pdf(pdf)
    validate_project(token, args.project_id)
    matches, _ = find_existing_pdf_items(token, args.project_id, pdf)
    if len(matches) == 1:
        raise ApiError(f"PDF/paper already exists as item {matches[0].get('id')}; use update-notes instead of upload.")
    if len(matches) > 1:
        ids = ", ".join(str(item.get("id")) for item in matches)
        raise ApiError(f"PDF/paper already exists multiple times ({ids}); choose an item and use update-notes.")
    notes = Path(args.notes_file).read_text(encoding="utf-8")
    result = multipart_upload(token, args.project_id, pdf, notes, args.category_id)
    print(json.dumps({"ok": True, "operation": "uploaded", "upload": result}, ensure_ascii=False, indent=2))
    return 0


def cmd_update_notes(args: argparse.Namespace) -> int:
    token = token_from_value(args.token)
    validate_project(token, args.project_id)
    notes = Path(args.notes_file).read_text(encoding="utf-8")
    result = update_item_notes(token, args.project_id, args.item_id, notes)
    print(json.dumps({"ok": True, "operation": "notes_updated", "item_id": args.item_id, "update": result}, ensure_ascii=False, indent=2))
    return 0


def cmd_check_library(args: argparse.Namespace) -> int:
    token = token_from_value(args.token)
    validate_project(token, args.project_id)
    data = library_data(token, args.project_id)
    items = data.get("items") or []
    print(json.dumps({"ok": True, "item_count": len(items), "project": data.get("project")}, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    check = subparsers.add_parser("check", help="Validate token and project access.")
    check.add_argument("--project-id", required=True)
    check.add_argument("--token")
    check.set_defaults(func=cmd_check)

    existing = subparsers.add_parser("find-existing", help="Find an existing library item for a local PDF/paper.")
    existing.add_argument("--project-id", required=True)
    existing.add_argument("--pdf", required=True)
    existing.add_argument("--token")
    existing.set_defaults(func=cmd_find_existing)

    plan_batch = subparsers.add_parser("plan-batch", help="Plan batch ingestion from PDF directories and/or explicit PDF paths.")
    plan_batch.add_argument("--project-id", required=True)
    plan_batch.add_argument("--pdf-dir", action="append", default=[])
    plan_batch.add_argument("--pdf", action="append", default=[])
    plan_batch.add_argument("--recursive", action="store_true")
    plan_batch.add_argument("--token")
    plan_batch.set_defaults(func=cmd_plan_batch)

    upload = subparsers.add_parser("upload", help="Upload one PDF with notes.")
    upload.add_argument("--project-id", required=True)
    upload.add_argument("--pdf", required=True)
    upload.add_argument("--notes-file", required=True)
    upload.add_argument("--category-id", default="uncat")
    upload.add_argument("--token")
    upload.set_defaults(func=cmd_upload)

    update = subparsers.add_parser("update-notes", help="Replace notes on an existing library item.")
    update.add_argument("--project-id", required=True)
    update.add_argument("--item-id", required=True)
    update.add_argument("--notes-file", required=True)
    update.add_argument("--token")
    update.set_defaults(func=cmd_update_notes)

    library = subparsers.add_parser("check-library", help="Read project library after upload or notes update.")
    library.add_argument("--project-id", required=True)
    library.add_argument("--token")
    library.set_defaults(func=cmd_check_library)

    return parser


def main(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ApiError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))


