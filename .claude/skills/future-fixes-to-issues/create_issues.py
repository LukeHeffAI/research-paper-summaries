#!/usr/bin/env python3
"""Bulk-create GitHub issues from /tmp/issue-batch-*.md files.

Parses each batch file's `=== ISSUE <id> === ... === END ISSUE <id> ===` blocks,
runs `gh issue create` for non-SKIP items, captures issue numbers, and writes a
mapping to /tmp/issue-mapping.txt for the FUTURE_FIXES.md update step.

Usage:  python3 create_issues.py [--repo OWNER/NAME]
        # Reads /tmp/issue-batch-*.md and writes /tmp/issue-mapping.txt.
        # Sleeps 0.4s between gh calls — gentle on the rate limiter.
        # --repo defaults to LukeHeffAI/research-paper-summaries; omit to use the
        #   repo of the current working directory.
"""

import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

DEFAULT_REPO = "LukeHeffAI/research-paper-summaries"

BATCH_GLOB = sorted(Path("/tmp").glob("issue-batch-*.md"))

ISSUE_BLOCK_RE = re.compile(
    r"=== ISSUE (?P<id>[A-Z0-9]+) ===\n(?P<body>.*?)\n=== END ISSUE \1 ===",
    re.DOTALL,
)


def parse_block(text: str) -> dict:
    fields: dict[str, str] = {}
    if "SKIP: yes" in text:
        fields["skip"] = "yes"
        m = re.search(r"SKIP_REASON:\s*(.+?)(?:\n|$)", text)
        fields["skip_reason"] = m.group(1).strip() if m else "(no reason given)"
        return fields

    fields["skip"] = "no"
    title_m = re.search(r"^TITLE:\s*(.+?)$", text, re.MULTILINE)
    labels_m = re.search(r"^LABELS:\s*(.+?)$", text, re.MULTILINE)
    body_m = re.search(r"^BODY:\s*<<<EOF\n(.*?)\nEOF\s*$", text, re.DOTALL | re.MULTILINE)
    if not (title_m and labels_m and body_m):
        raise ValueError(f"Could not parse fields from block:\n{text[:300]}")
    fields["title"] = title_m.group(1).strip()
    fields["labels"] = labels_m.group(1).strip()
    fields["body"] = body_m.group(1).strip()
    return fields


def create_issue(issue_id: str, fields: dict, repo: str | None) -> str:
    cmd = [
        "gh",
        "issue",
        "create",
        "--title",
        fields["title"],
        "--body",
        fields["body"],
        "--label",
        fields["labels"],
    ]
    if repo:
        cmd += ["--repo", repo]
    print(f"  creating {issue_id}: {fields['title'][:70]}...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"    FAILED: {result.stderr.strip()}", file=sys.stderr)
        return f"ERROR: {result.stderr.strip()[:200]}"
    url = result.stdout.strip()
    m = re.search(r"/issues/(\d+)$", url)
    return m.group(1) if m else url


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo",
        default=DEFAULT_REPO,
        help="OWNER/NAME target repo (default: %(default)s; pass empty to use cwd repo)",
    )
    args = parser.parse_args()
    repo = args.repo or None

    mapping: list[tuple[str, str, str, str]] = []
    skipped: list[tuple[str, str]] = []

    if not BATCH_GLOB:
        print("ERROR: no /tmp/issue-batch-*.md files found", file=sys.stderr)
        return 1

    for batch_path in BATCH_GLOB:
        text = batch_path.read_text()
        print(f"\n=== {batch_path} ===")
        for m in ISSUE_BLOCK_RE.finditer(text):
            issue_id = m.group("id")
            fields = parse_block(m.group("body"))
            if fields["skip"] == "yes":
                print(f"  SKIP {issue_id}: {fields['skip_reason']}")
                skipped.append((issue_id, fields["skip_reason"]))
                continue
            num = create_issue(issue_id, fields, repo)
            mapping.append((issue_id, fields["title"], num, fields["labels"]))
            time.sleep(0.4)

    out = Path("/tmp/issue-mapping.txt")
    with out.open("w") as f:
        f.write("# GH issue mapping (id\\t#N\\tlabels\\ttitle)\n")
        for issue_id, title, num, labels in mapping:
            f.write(f"{issue_id}\t#{num}\t{labels}\t{title}\n")
        f.write("\n# Skipped (id\\treason)\n")
        for issue_id, reason in skipped:
            f.write(f"{issue_id}\tSKIPPED\t{reason}\n")
    print(f"\nCreated {len(mapping)} issues, skipped {len(skipped)}. Mapping: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
