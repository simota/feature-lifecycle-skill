#!/usr/bin/env python3
"""
Lint the feature-lifecycle skill.

Four groups of checks. The one that carries this repository is L — the standalone
invariant. The skill was extracted from a repository whose `_common/` protocol directory
sat beside every skill; here there is no such directory, so a reference to one is a
path that renders fine to a human browsing the repo and resolves to nothing for the
agent reading the skill. That failure is silent by construction, which is why it is
checked mechanically rather than remembered.

  F1  frontmatter `name` is kebab-case, <=64 chars, no reserved prefix
  F2  frontmatter `description` is non-empty, <=1024 chars, carries a WHEN phrase,
      and contains no XML tags or non-Latin script — no letter outside the Latin
      script and nothing from CJK onward (accented Latin prose and typographic
      punctuation pass)
  F3  no frontmatter keys outside the allowlist
  N1  skill folder name == frontmatter `name`
  C1  the entry file is exactly `SKILL.md`
  C2  no README.md inside the skill folder (it belongs at the repo root)
  H1  CAPABILITIES_SUMMARY block present, with the COLLABORATION_PATTERNS,
      BIDIRECTIONAL_PARTNERS and PROJECT_AFFINITY markers inside that same
      `<!-- -->` comment — a marker that drifted out of it is not a marker
  ST1 required section headings present, outside code fences
  L1  no `_common/<path>` reference anywhere, at any depth, extension or not —
      the standalone invariant
  L2  every `reference/<file>.md` cited by any file in the skill resolves on disk
  L3  every file under `reference/` is cited by at least one *other* file
  L4  every `§ <section>` citation — `reference/x.md` § Heading, `SKILL.md` § Heading,
      a bare § Heading in its own file, or a numbered `§N` — names a heading that
      exists in the file it points at, outside code fences
  S1  SKILL.md body size (line count and token estimate) within the advisory tiers

Severity:
  P1  blocking
  P2  blocking
  P3  advisory — reported, never blocks

Usage:
  python3 tools/lint.py              # exit 1 on any P1/P2
  python3 tools/lint.py --strict     # exit 1 on any finding, P3 included
  python3 tools/lint.py --selftest   # prove each check blocks, and names itself, when
                                     # the input it guards is broken
"""

from __future__ import annotations

import argparse
import re
import unicodedata
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = REPO_ROOT / "skills"

FRONTMATTER_KEYS = {"name", "description", "model", "tools", "allowed-tools"}
RESERVED_PREFIXES = ("anthropic", "claude")
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
XML_RE = re.compile(r"<[a-zA-Z/!?][^>]*>")
WHEN_RE = re.compile(r"\b(use when|use it|use for|use this|when the|when a|when an)\b", re.I)

REQUIRED_HEADINGS = (
    "Trigger Guidance",
    "Core Contract",
    "Boundaries",
    "Workflow",
    "Recipes",
    "Subcommand Dispatch",
    "Output Requirements",
    "Collaboration",
    "Reference Map",
    "Operational",
)

CAPABILITY_MARKERS = (
    "CAPABILITIES_SUMMARY:",
    "COLLABORATION_PATTERNS:",
    "BIDIRECTIONAL_PARTNERS:",
    "PROJECT_AFFINITY:",
)

# A `_common/` mention naming something under it — at any depth, with or without an
# extension. `_common/OPERATIONAL` and `_common/protocols/loop.md` resolve to nothing
# here exactly as `_common/OPERATIONAL.md` does, so no form of the path may pass.
# Bare `_common/` in prose (provenance, "a repository that ships its own _common/
# set") names no path and is not a finding: at least one path character must follow
# the slash. A `.` closing a sentence is left outside the match.
COMMON_PATH_RE = re.compile(r"_common/[A-Za-z0-9_./-]*[A-Za-z0-9_/-]")
REFERENCE_PATH_RE = re.compile(r"reference/[A-Za-z0-9_.-]+\.md")

# A section citation: an optional backticked target file, then `§`, then either a
# section number (`§3`) or the heading's words running on into the prose. Where the
# heading text ends is unknowable from the citation alone, so the check runs the other
# way round: some heading in the target must be a prefix of what follows the `§`.
# The capture stops at the next `§`, so a second citation on the line is checked too;
# a number counts as a section number only when no word character follows it
# (`§3`, `§10.`), so `§ 0e. CONFIRM` is matched as a heading. A `§` not followed by
# an alphanumeric (prose about the sign itself) is not a citation.
CITE_FILE_RE = re.compile(r"`([A-Za-z0-9_./-]+\.md)`\s*$")
CITE_TEXT_RE = re.compile(
    r"\s*(\d+(?!\w)|[A-Za-z0-9][^`§]*(?:`[^`]*`[^`§]*)*?(?=`[A-Za-z0-9_./-]+\.md`\s*§|§|$))")


def citations(line: str):
    """Yield (target file or None, cited text) for each `§` on a line. The target is
    the backticked `.md` path immediately before the `§`; the cited text runs to the
    next citation, so neither swallows its neighbour."""
    for i, ch in enumerate(line):
        if ch != "§":
            continue
        target = CITE_FILE_RE.search(line[:i])
        text = CITE_TEXT_RE.match(line, i + 1)
        if text:
            yield (target.group(1) if target else None), text.group(1)

LINE_TIERS = ((1000, "P1"), (700, "P2"), (500, "P3"))
TOKEN_TIERS = ((15000, "P1"), (10000, "P2"), (7000, "P3"))


@dataclass
class Finding:
    severity: str
    rule: str
    where: str
    message: str

    def __str__(self) -> str:
        return f"  [{self.severity}] {self.rule:<4} {self.where}: {self.message}"


def _unquote(value: str) -> str:
    """Strip one matched pair of surrounding quotes. Stripping quote *characters*
    would eat a value's own trailing quotation mark."""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Return (frontmatter mapping, body). Missing frontmatter yields an empty map.

    A value may span lines two ways, and truncating either one hands the F2 checks
    a fragment to inspect while they report on the whole: a block scalar (`>`/`|`),
    where a blank line is a paragraph break and ends nothing, and a plain scalar,
    which YAML folds across more-indented lines until a blank or dedented one.
    """
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    block, body = text[4:end], text[end + 5 :]

    parts: dict[str, list[str]] = {}
    key: str | None = None
    scalar = False

    for line in block.splitlines():
        if not line.strip():
            if not scalar:
                key = None
            continue
        if line[:1] in (" ", "\t"):
            if key is not None:
                parts[key].append(line.strip())
            continue
        if line.startswith("#") or ":" not in line:
            key, scalar = None, False
            continue
        raw_key, _, value = line.partition(":")
        key, value = raw_key.strip(), value.strip()
        scalar = value in (">", ">-", ">+", "|", "|-", "|+")
        parts[key] = [] if scalar else [value]

    return {k: _unquote(" ".join(v).strip()) for k, v in parts.items()}, body


def headings(text: str) -> list[str]:
    """Markdown headings outside fenced code blocks. A `### Residual Ledger` inside a
    fenced template renders as literal text, so nothing can be cited to it."""
    found: list[str] = []
    fence = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            fence = not fence
            continue
        if not fence:
            m = re.match(r"^#{1,6}\s+(.+?)\s*#*\s*$", line)
            if m:
                found.append(m.group(1))
    return found


def _citation_keys(heading: str) -> set[str]:
    """The forms a heading is cited by: verbatim, without a trailing parenthetical
    (`Integration evidence (conditional third pass)`), and up to its colon
    (`Phase 0: Bootstrap …` is cited as `§ Phase 0`)."""
    forms = {heading, re.sub(r"\s*\([^)]*\)\s*$", "", heading)}
    if ":" in heading:
        forms.add(heading.split(":", 1)[0])
    return {f.strip().strip("`").lower() for f in forms if f.strip()}


def _resolves(cited: str, target_headings: list[str]) -> bool:
    cited = cited.lower()
    number = re.match(r"\d+", cited)
    if number:
        return any(re.match(rf"{number.group(0)}\.\s", h) for h in target_headings)
    for heading in target_headings:
        for key in _citation_keys(heading):
            if cited.startswith(key) and (len(cited) == len(key) or not cited[len(key)].isalnum()):
                return True
    return False


#: CJK and fullwidth blocks, flagged whatever the character's category: `。` and `「`
#: are punctuation, not letters, and still mark the text as non-Latin.
CJK_RANGES = ((0x2E80, 0x9FFF), (0xA000, 0xA4CF), (0xAC00, 0xD7AF), (0xF900, 0xFAFF),
              (0xFE30, 0xFE4F), (0xFF00, 0xFFEF), (0x20000, 0x3FFFF))
#: Letters whose Unicode names omit LATIN but which are Latin-script prose:
#: the Spanish/Portuguese ordinals and the micro sign.
LATIN_EXTRAS = set("ªºµ")


def _non_latin(text: str) -> set[str]:
    """Characters that do not route as Latin-script prose: a letter or digit of another
    script (Cyrillic, Greek, Arabic, Devanagari, kana …), and anything in a CJK or
    fullwidth block. Modifier letters, combining marks and format characters (an
    emoji's variation selector) carry no script of their own and pass, as do accented
    Latin, ligatures and typographic punctuation (— → ≤ ∧ “ ” …)."""
    bad = set()
    for c in text:
        cp, cat = ord(c), unicodedata.category(c)
        if any(lo <= cp <= hi for lo, hi in CJK_RANGES):
            bad.add(c)
        elif c in LATIN_EXTRAS or cat in ("Lm", "Mn", "Mc", "Me", "Cf"):
            continue
        elif cat.startswith("L") and "LATIN" not in unicodedata.name(c, ""):
            bad.add(c)
        elif cat == "Nd" and not c.isascii():
            bad.add(c)
    return bad


def lint_skill(skill_dir: Path, out: list[Finding]) -> None:
    name = skill_dir.name
    skill_md = skill_dir / "SKILL.md"
    rel = lambda p: str(p.relative_to(REPO_ROOT))  # noqa: E731

    # C1
    if not skill_md.is_file():
        entries = [p.name for p in skill_dir.iterdir() if p.suffix == ".md"]
        out.append(Finding("P1", "C1", rel(skill_dir), f"no SKILL.md (found: {entries or 'nothing'})"))
        return

    # C2
    for stray in ("README.md", "readme.md"):
        if (skill_dir / stray).is_file():
            out.append(Finding("P2", "C2", rel(skill_dir / stray),
                               "README.md inside the skill folder — put it at the repo root"))

    text = skill_md.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(text)

    # F1
    fm_name = fm.get("name", "")
    if not fm_name:
        out.append(Finding("P1", "F1", rel(skill_md), "frontmatter has no `name`"))
    else:
        if not NAME_RE.match(fm_name):
            out.append(Finding("P1", "F1", rel(skill_md), f"name `{fm_name}` is not kebab-case"))
        if len(fm_name) > 64:
            out.append(Finding("P1", "F1", rel(skill_md), f"name is {len(fm_name)} chars > 64"))
        if fm_name.startswith(RESERVED_PREFIXES):
            out.append(Finding("P1", "F1", rel(skill_md), f"name `{fm_name}` uses a reserved prefix"))
        # N1
        if fm_name != name:
            out.append(Finding("P1", "N1", rel(skill_md),
                               f"frontmatter name `{fm_name}` != folder `{name}`"))

    # F2
    desc = fm.get("description", "")
    if not desc:
        out.append(Finding("P1", "F2", rel(skill_md), "frontmatter has no `description`"))
    else:
        if len(desc) > 1024:
            out.append(Finding("P1", "F2", rel(skill_md), f"description is {len(desc)} chars > 1024"))
        if XML_RE.search(desc):
            out.append(Finding("P1", "F2", rel(skill_md), "description contains an XML/HTML tag"))
        if not WHEN_RE.search(desc):
            out.append(Finding("P2", "F2", rel(skill_md),
                               "description states no WHEN — a trigger phrase is what routes to it"))
        # Latin script — accents included — routes fine; other scripts do not.
        non_latin = _non_latin(desc)
        if non_latin:
            out.append(Finding("P1", "F2", rel(skill_md),
                               f"description contains non-Latin characters: {''.join(sorted(non_latin))}"))

    # F3
    for key in sorted(set(fm) - FRONTMATTER_KEYS):
        out.append(Finding("P1", "F3", rel(skill_md), f"frontmatter key `{key}` is not allowed"))

    # H1 — the markers are read out of the comment that opens with CAPABILITIES_SUMMARY,
    # so one that slipped below the `-->` (and now renders as prose) is missing.
    summary = next((c for c in re.findall(r"<!--(.*?)-->", body, re.S)
                    if c.lstrip().startswith(CAPABILITY_MARKERS[0])), "")
    for marker in CAPABILITY_MARKERS:
        if marker not in summary:
            where = "missing" if marker not in body else "outside the CAPABILITIES_SUMMARY comment —"
            out.append(Finding("P2", "H1", rel(skill_md), f"{where} `{marker}` marker"))

    # ST1
    present = {h.strip() for h in headings(body)}
    for required in REQUIRED_HEADINGS:
        if not any(required.lower() in h.lower() for h in present):
            out.append(Finding("P2", "ST1", rel(skill_md), f"missing required section `## {required}`"))

    # S1
    lines = body.count("\n") + 1
    tokens = int(len(body) / 3.5)
    for limit, sev in LINE_TIERS:
        if lines > limit:
            out.append(Finding(sev, "S1", rel(skill_md), f"body {lines} lines > {limit}"))
            break
    for limit, sev in TOKEN_TIERS:
        if tokens > limit:
            out.append(Finding(sev, "S1", rel(skill_md), f"body ~{tokens} tokens > {limit}"))
            break

    lint_links(skill_dir, out)


def lint_links(skill_dir: Path, out: list[Finding]) -> None:
    """L1-L4: the standalone invariant, reference/ resolving in both directions, and
    every § citation landing on a heading that exists."""
    rel = lambda p: str(p.relative_to(REPO_ROOT))  # noqa: E731
    files = sorted(p for p in skill_dir.rglob("*.md") if p.is_file())
    cited: set[str] = set()
    heading_cache: dict[Path, list[str]] = {}

    for path in files:
        own = path.relative_to(skill_dir).as_posix()
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            # L4 — a bare numbered `§N` after a cited file inherits that file:
            # "`reference/contracts.md` §1: the gate (§2), the ladder (§3)" cites
            # contracts.md three times, not SKILL.md twice. A bare `§ Heading` is
            # always the citing file's own.
            last_cited = path
            for target, quoted in citations(line):
                if target:
                    context = last_cited = skill_dir / target
                elif quoted[:1].isdigit():
                    context = last_cited
                else:
                    context = path
                if not context.is_file():
                    # L2 only sees `reference/…` paths; a citation to any other file
                    # (`contracts.md` § X from a sibling) is checked here.
                    if target and not REFERENCE_PATH_RE.fullmatch(target):
                        out.append(Finding("P2", "L4", f"{rel(path)}:{lineno}",
                                           f"cites `{target}`, which is not a file in the skill"))
                    continue
                if context not in heading_cache:
                    heading_cache[context] = headings(context.read_text(encoding="utf-8"))
                if not _resolves(quoted, heading_cache[context]):
                    shown = "§ " + quoted
                    shown = shown if len(shown) <= 50 else shown[:47] + "..."
                    out.append(Finding("P2", "L4", f"{rel(path)}:{lineno}",
                                       f"\"{shown}\" names no heading in {context.relative_to(skill_dir).as_posix()}"))
            # L1
            for match in COMMON_PATH_RE.findall(line):
                out.append(Finding("P1", "L1", f"{rel(path)}:{lineno}",
                                   f"references `{match}` — no such directory ships with this skill"))
            # L2
            for match in REFERENCE_PATH_RE.findall(line):
                # A file naming its own path — every reference file here carries a
                # `**Read when:**` header — does not make itself reachable.
                if match != own:
                    cited.add(match)
                if not (skill_dir / match).is_file():
                    out.append(Finding("P1", "L2", f"{rel(path)}:{lineno}",
                                       f"references `{match}`, which does not exist"))

    # L3
    ref_dir = skill_dir / "reference"
    if ref_dir.is_dir():
        for path in sorted(ref_dir.glob("*.md")):
            if f"reference/{path.name}" not in cited:
                out.append(Finding("P2", "L3", rel(path),
                                   "no other file in the skill cites this — it is unreachable at runtime"))


def run(strict: bool) -> int:
    if not SKILLS_ROOT.is_dir():
        print(f"lint: no skills/ directory at {SKILLS_ROOT}", file=sys.stderr)
        return 2

    skill_dirs = sorted(p for p in SKILLS_ROOT.iterdir() if p.is_dir() and not p.name.startswith("."))
    if not skill_dirs:
        print("lint: skills/ holds no skill directory", file=sys.stderr)
        return 2

    findings: list[Finding] = []
    for skill_dir in skill_dirs:
        lint_skill(skill_dir, findings)

    order = {"P1": 0, "P2": 1, "P3": 2}
    findings.sort(key=lambda f: (order.get(f.severity, 9), f.rule, f.where))

    blocking = [f for f in findings if f.severity in ("P1", "P2")]
    advisory = [f for f in findings if f.severity == "P3"]

    print(f"lint: {len(skill_dirs)} skill(s), {len(findings)} finding(s)")
    for finding in findings:
        print(finding)

    if blocking or (strict and advisory):
        return 1
    if advisory:
        print("lint: advisory only — not blocking")
    return 0


# --------------------------------------------------------------------------- selftest

#: Each mutation takes the scratch skill directory and breaks exactly one check.
#: It must produce a blocking finding *carrying that check's rule id*, or the check
#: is indistinguishable from one that returns zero unconditionally.
def _edit(rel: str, transform):
    def apply(skill: Path) -> bool:
        path = skill / rel
        before = path.read_text(encoding="utf-8")
        after = transform(before)
        if after == before:
            return False
        path.write_text(after, encoding="utf-8")
        return True
    return apply


def _add_readme(skill: Path) -> bool:
    (skill / "README.md").write_text("# feature-lifecycle\n", encoding="utf-8")
    return True


def _add_orphan_reference(skill: Path) -> bool:
    (skill / "reference" / "orphan.md").write_text("# orphan\n", encoding="utf-8")
    return True


def _rename_entry_file(skill: Path) -> bool:
    (skill / "SKILL.md").rename(skill / "GUIDE.md")
    return True


def _add_self_citing_reference(skill: Path) -> bool:
    (skill / "reference" / "self-cited.md").write_text(
        "# self-cited\n\n**Read when:** see `reference/self-cited.md`.\n", encoding="utf-8")
    return True


def _set_description(value: str):
    """Replace the whole `description:` line. The length, XML, WHEN and script
    checks each need their own broken input, and carving up the real description
    would couple every mutation to its current wording."""
    return _edit("SKILL.md", lambda s: re.sub(
        r"^description: .*$", lambda _m: f"description: {value}", s, count=1, flags=re.M))


#: (rule, label, mutation). The rule id is asserted, not just the exit code: a
#: mutation usually trips more than one check — `name: Bad_Name` breaks kebab-case
#: *and* the folder-name match — so exit 1 alone cannot say which one caught it,
#: and a deleted check keeps passing behind its neighbour.
MUTATIONS = [
    ("F1", "rejects a non-kebab name",
     _edit("SKILL.md", lambda s: s.replace("name: feature-lifecycle", "name: Bad_Name", 1))),
    ("F1", "rejects a reserved prefix",
     _edit("SKILL.md", lambda s: s.replace("name: feature-lifecycle", "name: claude-feature-lifecycle", 1))),
    ("F1", "rejects an over-long name",
     _edit("SKILL.md", lambda s: s.replace("name: feature-lifecycle", "name: " + "a" * 65, 1))),
    ("F2", "rejects an empty description", _set_description('""')),
    ("F2", "rejects an over-long description",
     _set_description('"Use when the run is high-stakes. ' + "padding " * 150 + '"')),
    ("F2", "rejects an XML tag in the description",
     _set_description('"Use when the feature is <b>high-stakes</b> and expensive to reverse."')),
    ("F2", "rejects a description that states no WHEN",
     _set_description('"Runs one high-stakes feature end to end and ships it."')),
    ("F2", "rejects non-Latin script in the description",
     _set_description('"Use when the feature is \u9ad8\u30ea\u30b9\u30af and expensive to reverse."')),
    ("F2", "rejects a non-Latin script below the CJK range",
     _set_description('"Use when the feature is \u0432\u044b\u0441\u043e\u043a\u0438\u0439 risk and expensive to reverse."')),
    ("F3", "rejects an unknown frontmatter key",
     _edit("SKILL.md", lambda s: s.replace("name: feature-lifecycle", "name: feature-lifecycle\nversion: 2", 1))),
    ("H1", "catches a dropped marker",
     _edit("SKILL.md", lambda s: s.replace("PROJECT_AFFINITY:", "AFFINITY:", 1))),
    ("H1", "catches a marker moved outside the summary comment",
     _edit("SKILL.md", lambda s: re.sub(r"\n(PROJECT_AFFINITY:[^\n]*)\n-->", r"\n-->\n\1", s, count=1))),
    ("ST1", "catches a dropped section",
     _edit("SKILL.md", lambda s: s.replace("\n## Core Contract\n", "\n## Contract\n", 1))),
    ("ST1", "ignores a required heading that only survives inside a code fence",
     _edit("SKILL.md", lambda s: s.replace("\n## Core Contract\n", "\n```\n## Core Contract\n```\n", 1))),
    ("L1", "catches a reintroduced _common path",
     _edit("SKILL.md", lambda s: s.replace("\n## Workflow\n", "\nSee `_common/OPERATIONAL.md`.\n\n## Workflow\n", 1))),
    ("L2", "catches a dead reference link",
     _edit("SKILL.md", lambda s: s.replace("`reference/loop-engine.md`", "`reference/loop-engin.md`", 1))),
    ("L4", "catches a section citation whose heading was renamed",
     _edit("reference/loop-engine.md", lambda s: s.replace("\n## Termination Bounds\n", "\n## Loop Bounds\n", 1))),
    ("L4", "catches a numbered citation past the last section",
     _edit("SKILL.md", lambda s: s.replace("(`reference/contracts.md` §2)", "(`reference/contracts.md` §12)", 1))),
    ("L4", "catches a citation to a heading that exists only inside a code fence",
     _edit("reference/phase-contracts.md", lambda s: s.replace(
         "§ Output Envelope)", "§ Residual Ledger)", 1))),
    ("L4", "checks a second citation on the same line",
     _edit("SKILL.md", lambda s: s.replace(
         "(`reference/loop-engine.md` § Termination Bounds); acceptance-gap",
         "(`reference/loop-engine.md` § Termination Bounds, `reference/loop-engine.md` § No Such Section); acceptance-gap", 1))),
    ("L4", "catches a citation to a file outside reference/ that does not exist",
     _edit("reference/phase-contracts.md", lambda s: s.replace(
         "`reference/engine-roster.md` § Phase → Role Map owns", "`contracts.md` § Phase → Role Map owns", 1))),
    ("L3", "catches an uncited reference file", _add_orphan_reference),
    ("L3", "catches a reference file that cites only itself", _add_self_citing_reference),
    ("C2", "catches a README inside the skill folder", _add_readme),
    ("N1", "catches a name that no longer matches its folder",
     _edit("SKILL.md", lambda s: s.replace("name: feature-lifecycle", "name: feature-lifecycle-lifecycle", 1))),
    ("C1", "catches a missing SKILL.md", _rename_entry_file),
    ("S1", "blocks at the top line tier",
     _edit("SKILL.md", lambda s: s + "\n" * 1100)),
    ("S1", "blocks at the top token tier",
     _edit("SKILL.md", lambda s: s + "\n" + "x" * 60000)),
]


def _names_blocking(stdout: str, rule: str) -> bool:
    """Did the linter report a P1/P2 finding under this exact rule id?"""
    return re.search(rf"^\s*\[P[12]\]\s+{re.escape(rule)}\s", stdout, re.M) is not None


def selftest() -> int:
    """Break one check at a time in a scratch copy and require the linter to name it."""
    script = Path(__file__).resolve()
    failures = 0

    for rule, label, mutate in MUTATIONS:
        title = f"{rule} {label}"
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp) / "repo"
            shutil.copytree(REPO_ROOT, work, ignore=shutil.ignore_patterns(".git"))
            if not mutate(work / "skills" / "feature-lifecycle"):
                print(f"  BROKEN  {title} — the mutation changed nothing; fix the selftest")
                failures += 1
                continue

            proc = subprocess.run([sys.executable, str(work / script.relative_to(REPO_ROOT))],
                                  capture_output=True, text=True)
            if proc.returncode != 1:
                print(f"  FAIL    {title} — linter exited {proc.returncode}, expected 1")
            elif not _names_blocking(proc.stdout, rule):
                print(f"  FAIL    {title} — exited 1 with no blocking {rule} finding; "
                      f"another check caught it, so {rule} could be deleted unnoticed")
            else:
                print(f"  PASS    {title}")
                continue
            print("          " + proc.stdout.strip().replace("\n", "\n          "))
            failures += 1

    # And the unmutated tree must be clean, or every PASS above proves nothing.
    proc = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
    if proc.returncode == 0:
        print("  PASS    the repository itself is clean")
    else:
        print(f"  FAIL    the repository itself does not pass (exit {proc.returncode})")
        print("          " + proc.stdout.strip().replace("\n", "\n          "))
        failures += 1

    print(f"selftest: {len(MUTATIONS) + 1 - failures}/{len(MUTATIONS) + 1} passed")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="exit 1 on advisory findings too")
    parser.add_argument("--selftest", action="store_true", help="prove each check fails when broken")
    args = parser.parse_args()
    return selftest() if args.selftest else run(args.strict)


if __name__ == "__main__":
    sys.exit(main())
