#!/usr/bin/env python3
"""Retry ChinaMoney attachment downloads with curl and stricter file validation."""

import argparse
import datetime as dt
import json
from pathlib import Path
import subprocess
from typing import Dict, Iterable, Tuple
from urllib.parse import urlsplit, urlunsplit


ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
RAW_FILES = ROOT / "data" / "raw" / "files" / "china_money"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
)


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def iter_jsonl(path: Path) -> Iterable[Dict]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def write_jsonl(path: Path, rows: Iterable[Dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def gap_key(row: Dict) -> Tuple:
    return (row.get("source_id"), row.get("doc_id"), row.get("url"), row.get("gap_type"))


def looks_like_html(path: Path) -> bool:
    if not path.exists() or path.stat().st_size == 0:
        return True
    head = path.read_bytes()[:512].decode("utf-8", errors="ignore").lower()
    return "<html" in head or "<!doctype html" in head or "request-id" in head


def output_path(att: Dict) -> Path:
    attachment_id = att["attachment_id"]
    suffix = Path(att.get("attachment_path") or "").suffix
    if not suffix:
        suffix = Path(att.get("attachment_name") or "").suffix or ".bin"
    return RAW_FILES / f"{attachment_id}{suffix}"


def fallback_urls(url: str) -> Iterable[str]:
    yield url
    parts = urlsplit(url)
    if parts.netloc == "www.chinamoney.com.cn":
        yield urlunsplit((parts.scheme, "www.chinamoney.org.cn", parts.path, parts.query, parts.fragment))


def referer_for(url: str) -> str:
    parts = urlsplit(url)
    base = f"{parts.scheme}://{parts.netloc}" if parts.scheme and parts.netloc else "https://www.chinamoney.com.cn"
    return f"{base}/chinese/"


def download_once(url: str, out: Path, timeout: int) -> Tuple[bool, str]:
    out.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            "curl",
            "-sL",
            "--compressed",
            "--fail",
            "--connect-timeout",
            "10",
            "--max-time",
            str(timeout),
            "-A",
            USER_AGENT,
            "-H",
            f"Referer: {referer_for(url)}",
            url,
            "-o",
            str(out),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout + 5,
    )
    if result.returncode != 0:
        return False, result.stderr.decode("utf-8", errors="replace") or f"curl exit {result.returncode}"
    if looks_like_html(out):
        return False, "Downloaded HTML/error page instead of attachment"
    return True, ""


def download(url: str, out: Path, timeout: int) -> Tuple[bool, str]:
    reasons = []
    for candidate in fallback_urls(url):
        ok, reason = download_once(candidate, out, timeout)
        if ok:
            return True, ""
        reasons.append(f"{candidate}: {reason}")
    if out.exists() and looks_like_html(out):
        out.unlink()
    return False, " | ".join(reasons)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    attachments_path = PROCESSED / "attachments.jsonl"
    gaps_path = PROCESSED / "gaps.jsonl"
    attachments = list(iter_jsonl(attachments_path))
    gaps = list(iter_jsonl(gaps_path))

    targets = [
        att for att in attachments
        if att.get("source_id") == "china_money"
        and (not att.get("downloaded") or att.get("download_error") == "Downloaded HTML error page instead of attachment")
        and att.get("download_url")
    ]
    if args.limit:
        targets = targets[:args.limit]

    success_keys = set()
    attempted = 0
    downloaded = 0
    failed = 0
    by_id = {att.get("attachment_id"): att for att in attachments}
    for att in targets:
        attempted += 1
        out = output_path(att)
        ok = out.exists() and not looks_like_html(out)
        reason = "" if ok else None
        if not ok:
            ok, reason = download(att["download_url"], out, args.timeout)
        if ok:
            downloaded += 1
            att["downloaded"] = True
            att["download_error"] = ""
            att["local_path"] = str(out.relative_to(ROOT))
            att["retrieved_at"] = now_iso()
            success_keys.add((att.get("source_id"), att.get("attachment_id"), att.get("url")))
            print(f"downloaded {att.get('attachment_id')} {out.name}", flush=True)
        else:
            failed += 1
            att["downloaded"] = False
            att["download_error"] = reason
            att.pop("local_path", None)
            print(f"failed {att.get('attachment_id')} {reason[:160]}", flush=True)
        by_id[att.get("attachment_id")] = att

    if success_keys:
        gaps = [
            gap for gap in gaps
            if (gap.get("source_id"), gap.get("doc_id"), gap.get("url")) not in success_keys
        ]
    write_jsonl(attachments_path, by_id.values())
    write_jsonl(gaps_path, gaps)
    print(f"attempted={attempted} downloaded={downloaded} failed={failed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
