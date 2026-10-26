#!/usr/bin/env python3
"""Check and render a feature-lifecycle run record as one page (reference/visuals.md).

    python3 visuals.py check  RUN_DIR [--view RUN_HTML]
    python3 visuals.py render RUN_DIR --out DIR [--lang en|ja]

RUN_DIR is `.agents/feature-lifecycle/runs/<run-id>/`. check reads RUN.md, every
phase document's envelope and artifacts/visuals.json, and refuses what
reference/run-record.md and reference/visuals.md do not allow; with --view it
also refuses a run.html rendered from different sources. render checks first,
then writes DIR/run.html: the phase timeline with each gate, the artifact flow,
the design diagrams, the screen mocks (before, recommended after, alternatives)
in sandboxed frames, and every phase document. The page loads nothing from the
network; its one script is the Copy for LLM button, allowed by hash. DIR must be
outside RUN_DIR: the record's layout is closed. The page is stamped with the
SHA-256 of the sources it was rendered from.

The mock markup rules are brand-feature-scan's (scripts/proposals.py); change
them there first and keep the two in step. Standard library only.
Exit status: 0 ok, 2 invalid record or I/O error (reasons on stderr).
"""

import argparse
import base64
import hashlib
import html
import json
import os
import re
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path

STAMP = "feature-lifecycle-source"
PHASES = {"00": "P0 Bootstrap", "01": "P1 Discover", "02": "P2 Ideate", "03": "P3 Verdict",
          "04": "P4 Spec", "05": "P5 Design + Risk Gate", "06": "P6 Loop", "07": "Verify", "08": "Ship"}
PHASE_DOC = re.compile(r"^(0[0-8])-[a-z0-9-]+\.md\Z")
STATUSES = ("open", "sealed", "abandoned")
# The phase field each document number carries (reference/run-record.md § Layout).
PHASE_PREFIX = {"00": "P0", "01": "P1", "02": "P2", "03": "P3", "04": "P4", "05": "P5", "06": "P6",
                "07": "VERIFY", "08": "SHIP"}
# RUN.md's **Status:** values (reference/run-record.md § Run Status).
RUN_STATUS = re.compile(r"^(?:running|(?:aborted|blocked)-at-[A-Z0-9_]+|declined-at-P0|shipped|superseded|closed)\Z")
GATES = ("pass", "fail", "n/a")
VISUAL_PHASES = ("P2", "P5")
MOCK_ID = re.compile(r"^M-[0-9]{2}\Z")
DIAGRAM_ID = re.compile(r"^D-[0-9]{2}\Z")
NODE_ID = re.compile(r"^[A-Za-z0-9_.:/-]{1,64}\Z")
NODE_TYPES = ("actor", "component", "store", "external", "step", "state")
CHANGES = ("existing", "new", "changed", "removed")
DIAGRAM_KINDS = ("architecture", "flow", "state", "data")
DIRECTIONS = ("LR", "TB")
LOCATION = re.compile(r"^[^:\x00-\x1f\x7f-\x9f]+:[1-9][0-9]*(?:-[1-9][0-9]*)?\Z")
MAX_NODES = 40
# Design Select (reference/visuals.md § Designs): whole candidate designs the P5 tracks drew.
DESIGN_ID = re.compile(r"^DS-[A-Z]\Z")
DESIGN_STATUSES = ("candidate", "selected", "rejected")
SELECTED_BY = ("user", "delegated")
MAX_DESIGNS = 4
AC_ID = re.compile(r"\bAC-[0-9]+\b")

VIEWPORTS = ("mobile", "desktop")
MOCK_HEIGHT = (120, 4000)
MAX_MOCK_BYTES = 64 * 1024
MAX_ALTERNATIVES = 4
# Mocks render in a sandboxed frame under a no-network CSP, which is the boundary.
# Refusing active content and outside references up front tells the author why
# a mock would not work, and keeps them out of markup copied for building.
MOCK_TAGS = {"script", "iframe", "frame", "frameset", "object", "embed", "applet", "portal", "link", "meta",
             "base", "form", "set", "animate", "animatemotion", "animatetransform", "discard",
             # Raw-text and RCDATA elements: Python versions disagree on whether their
             # content is text, and inside SVG or MathML a browser parses it as markup.
             "xmp", "textarea", "title", "noembed", "noframes", "noscript", "plaintext"}
# Attributes that load or navigate; descriptive ones (cite, longdesc) fetch nothing.
MOCK_URL_ATTRS = {"href", "xlink:href", "src", "action", "formaction", "poster", "background", "ping",
                  "srcset", "imagesrcset"}
MOCK_LOCAL = re.compile(r"(?i)[ \t\r\n\f]*(?:#|data:)")
CSS_ESCAPE = re.compile(r"\\(?:([0-9a-fA-F]{1,6})[ \t\r\n\f]?|(.))", re.S)
CSS_NAME = re.compile(r"(?:[-A-Za-z0-9_]|[^\x00-\x7f]|\\(?:[0-9a-fA-F]{1,6}[ \t\n]?|[^\n]))+")


class RecordError(Exception):
    pass


# ── Mock markup (kept in step with brand-feature-scan scripts/proposals.py) ──────

def _css_decode(value):
    """Decode one token, after its delimiters have been read from the source."""
    def unescape(match):
        if match[1]:
            code = int(match[1], 16)
            return chr(code) if 0 < code <= 0x10FFFF and not 0xD800 <= code <= 0xDFFF else "�"
        return "" if match[2] == "\n" else match[2]
    return CSS_ESCAPE.sub(unescape, value)


def _css_string(css, start):
    """Return a decoded string and its end; an unescaped newline is a bad string."""
    quote, end = css[start], start + 1
    while end < len(css):
        if css[end] == quote:
            return _css_decode(css[start + 1:end]), end + 1
        if css[end] == "\n":
            return None, end
        escape = CSS_ESCAPE.match(css, end) if css[end] == "\\" else None
        end = escape.end() if escape else end + 1
    # CSS closes a string at EOF. No later token can be hidden behind it.
    return _css_decode(css[start + 1:]), end


def _css_problem(css):
    """Check references while keeping strings, comments and function boundaries distinct.

    This is a reference check, not a full CSS grammar validator. Decoding the whole
    stylesheet first would turn escaped quotes/parentheses into structural tokens,
    or turn da/**/ta: inside a string into a different URL.
    """
    css = css.replace("\r\n", "\n").replace("\r", "\n").replace("\f", "\n")
    stack, pos, image_sets = [], 0, 0
    while pos < len(css):
        if css.startswith("/*", pos):
            end = css.find("*/", pos + 2)
            pos = len(css) if end < 0 else end + 2
            continue
        char = css[pos]
        if char in "\"'":
            value, pos = _css_string(css, pos)
            if value is None:
                # CSS recovers from a bad string at the newline. Keep scanning
                # for later references; text attributes also pass through here.
                continue
            # Keep checking nested image candidates; only a direct type() descriptor
            # is metadata. Its strings describe MIME types, not resource URLs.
            parent = stack[-1][1] if stack else None
            descriptor = (parent == "type" and len(stack) > 1
                          and stack[-2][1] in ("image-set", "-webkit-image-set"))
            if (parent == "url" or image_sets and not descriptor) and not MOCK_LOCAL.match(value):
                kind = "url" if parent == "url" else "image-set"
                return f"CSS {kind}() outside #fragment or data:"
            continue
        at_rule = char == "@"
        name = CSS_NAME.match(css, pos + 1 if at_rule else pos)
        if name:
            word, pos = _css_decode(name[0]).lower(), name.end()
            if at_rule:
                if word in ("import", "font-face"):
                    return f"CSS @{word}"
                continue
            if pos < len(css) and css[pos] == "(":
                pos += 1
                if word == "expression":
                    return "CSS expression("
                if word == "url":
                    while pos < len(css) and css[pos] in " \t\n":
                        pos += 1
                    if pos == len(css) or css[pos] not in "\"'":
                        # Unquoted URL tokens have their own escape rules; comment
                        # markers here are URL characters, not stylesheet comments.
                        end = pos
                        while end < len(css) and css[end] != ")":
                            escape = CSS_ESCAPE.match(css, end) if css[end] == "\\" else None
                            end = escape.end() if escape else end + 1
                        if not MOCK_LOCAL.match(_css_decode(css[pos:end])):
                            return "CSS url() outside #fragment or data:"
                        pos = min(end + 1, len(css))
                        continue
                stack.append((")", word))
                image_sets += word in ("image-set", "-webkit-image-set")
            continue
        if char in "([{":
            stack.append(({"(": ")", "[": "]", "{": "}"}[char], None))
        elif stack and char == stack[-1][0]:
            image_sets -= stack.pop()[1] in ("image-set", "-webkit-image-set")
        pos += 1
    return None


def _stylesheet_problem(css):
    """_css_problem for a <style> element's text, where "<" can end it or, inside SVG or MathML, open a tag."""
    return "< inside a stylesheet" if "<" in css else _css_problem(css)


class _MockMarkup(HTMLParser):
    """Finds the first refused tag, attribute or style in mock markup, with references decoded.

    Where Python's parser and a browser's disagree (comments, CDATA, declarations,
    an unterminated tag, "<" in a stylesheet), the markup is refused rather than
    read one way, so a browser can never see a tag this check did not.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.problem, self.in_style = None, False

    def handle_starttag(self, tag, attrs):
        self.in_style = tag == "style"
        if tag in MOCK_TAGS:
            self.problem = self.problem or f"<{tag}>"
        for name, value in attrs:
            value = value or ""
            if name.startswith("on"):
                problem = f"{name}= on <{tag}>"
            elif name in ("srcset", "imagesrcset"):
                problem = f"{name}= (use src with a data: URI)"
            elif name in MOCK_URL_ATTRS and not MOCK_LOCAL.match(value):
                problem = f"{name}={value.strip()[:40]!r} on <{tag}>"
            else:
                # style, and SVG presentation attributes such as fill='url(…)', take CSS values.
                problem = _css_problem(value)
            self.problem = self.problem or problem

    handle_startendtag = handle_starttag

    def handle_endtag(self, tag):
        self.in_style = False

    def handle_data(self, data):
        if self.in_style:
            # Inside SVG or MathML a browser decodes character references in <style>.
            self.problem = self.problem or _stylesheet_problem(data) or _stylesheet_problem(html.unescape(data))

    def handle_comment(self, data):
        self.problem = self.problem or "a comment, CDATA section or declaration"

    handle_decl = unknown_decl = handle_pi = handle_comment


def _html_problem(markup):
    parser = _MockMarkup()
    parser.feed(markup)
    # Text the parser holds back is an unfinished construct; in the frame the
    # markup is followed by </body>, which can complete it into a live tag.
    if "<" in parser.rawdata:
        return parser.problem or "an unterminated tag"
    parser.close()
    return parser.problem


# ── visuals.json ─────────────────────────────────────────────────────────────

def _str(obj, key, where, required=False):
    if key not in obj:
        if required:
            raise RecordError(f"{where}.{key}: required")
        return ""
    value = obj[key]
    if not isinstance(value, str) or (required and not value.strip()):
        raise RecordError(f"{where}.{key}: expected a non-empty string" if required
                          else f"{where}.{key}: expected a string")
    return value


def _strings(obj, key, where):
    value = obj.get(key, [])
    if not isinstance(value, list) or not all(isinstance(v, str) and v.strip() for v in value):
        raise RecordError(f"{where}.{key}: expected a list of non-empty strings")
    return value


def _common(item, where, pattern):
    if not isinstance(item, dict):
        raise RecordError(f"{where}: expected an object")
    if not isinstance(item.get("id"), str) or not pattern.match(item["id"]):
        raise RecordError(f"{where}.id: expected {'M-01' if pattern is MOCK_ID else 'D-01'}, two digits")
    if item.get("phase") not in VISUAL_PHASES:
        raise RecordError(f"{where}.phase: expected one of {', '.join(VISUAL_PHASES)}")
    _str(item, "title", where, required=True)
    for key in ("intent", "option"):
        _str(item, key, where)
    if _strings(item, "acs", where) and item["phase"] == "P2":
        raise RecordError(f"{where}.acs: a P2 visual comes before acceptance criteria exist; leave it empty")


def _screen(screen, where, caption_required=False):
    if not isinstance(screen, dict):
        raise RecordError(f"{where}: expected an object")
    _str(screen, "caption", where, required=caption_required)
    if "source" in screen and not LOCATION.match(_str(screen, "source", where, required=True)):
        raise RecordError(f"{where}.source: expected path:line or path:first-last")
    return _str(screen, "html", where, required=True)


def check_mock(mock, where):
    """One mock: the screen today, the recommended after, up to four alternatives."""
    _common(mock, where, MOCK_ID)
    if mock.get("viewport") not in VIEWPORTS:
        raise RecordError(f"{where}.viewport: expected one of {', '.join(VIEWPORTS)}")
    if "height" in mock and (type(mock["height"]) is not int
                             or not MOCK_HEIGHT[0] <= mock["height"] <= MOCK_HEIGHT[1]):
        raise RecordError(f"{where}.height: expected an integer from {MOCK_HEIGHT[0]} to {MOCK_HEIGHT[1]}")
    _str(mock, "guardrails", where)
    css = _str(mock, "css", where)
    if "after" not in mock:
        raise RecordError(f"{where}.after: required")
    markup = [_screen(mock[side], f"{where}.{side}") for side in ("before", "after") if side in mock]
    alternatives = mock.get("alternatives", [])
    if "alternatives" in mock and (not isinstance(alternatives, list)
                                   or not 1 <= len(alternatives) <= MAX_ALTERNATIVES):
        raise RecordError(f"{where}.alternatives: expected a list of 1 to {MAX_ALTERNATIVES} screens")
    # The caption names how this design differs from the recommended one.
    markup += [_screen(s, f"{where}.alternatives[{i}]", caption_required=True) for i, s in enumerate(alternatives)]
    if len((css + "".join(markup)).encode("utf-8")) > MAX_MOCK_BYTES:
        raise RecordError(f"{where}: html and css exceed {MAX_MOCK_BYTES} bytes")
    problem = _stylesheet_problem(css) or next(filter(None, map(_html_problem, markup)), None)
    if problem:
        raise RecordError(f"{where}: {problem} is not allowed; mocks are static HTML and CSS "
                          "with only #fragment and data: references")


def check_diagram(diagram, where):
    """Nodes and edges laid out by render; `change` marks what the feature adds or alters."""
    _common(diagram, where, DIAGRAM_ID)
    if diagram.get("kind") not in DIAGRAM_KINDS:
        raise RecordError(f"{where}.kind: expected one of {', '.join(DIAGRAM_KINDS)}")
    if diagram.get("direction", "LR") not in DIRECTIONS:
        raise RecordError(f"{where}.direction: expected one of {', '.join(DIRECTIONS)}")
    nodes = diagram.get("nodes")
    if not isinstance(nodes, list) or not 1 <= len(nodes) <= MAX_NODES:
        raise RecordError(f"{where}.nodes: expected a list of 1 to {MAX_NODES} nodes")
    ids = set()
    for i, node in enumerate(nodes):
        at = f"{where}.nodes[{i}]"
        if not isinstance(node, dict) or not isinstance(node.get("id"), str) or not NODE_ID.match(node["id"]):
            raise RecordError(f"{at}.id: expected letters, digits and _.:/- (at most 64)")
        if node["id"] in ids:
            raise RecordError(f"{at}.id: {node['id']} is repeated")
        ids.add(node["id"])
        _str(node, "label", at, required=True)
        if node.get("type", "component") not in NODE_TYPES:
            raise RecordError(f"{at}.type: expected one of {', '.join(NODE_TYPES)}")
        if node.get("change", "existing") not in CHANGES:
            raise RecordError(f"{at}.change: expected one of {', '.join(CHANGES)}")
        if "source" in node and not LOCATION.match(_str(node, "source", at, required=True)):
            raise RecordError(f"{at}.source: expected path:line or path:first-last")
    edges = diagram.get("edges", [])
    if not isinstance(edges, list):
        raise RecordError(f"{where}.edges: expected a list")
    for i, edge in enumerate(edges):
        at = f"{where}.edges[{i}]"
        if not isinstance(edge, dict):
            raise RecordError(f"{at}: expected an object")
        for end in ("from", "to"):
            if not isinstance(edge.get(end), str) or edge[end] not in ids:
                raise RecordError(f"{at}.{end}: expected a node id of this diagram")
        _str(edge, "label", at)
        if edge.get("change", "existing") not in CHANGES:
            raise RecordError(f"{at}.change: expected one of {', '.join(CHANGES)}")


def check_designs(data):
    """Candidate designs group P5 mocks and diagrams; at most one is selected, the rest rejected with a reason."""
    designs = data.get("designs", [])
    if not isinstance(designs, list) or len(designs) > MAX_DESIGNS:
        raise RecordError(f"designs: expected a list of at most {MAX_DESIGNS} designs")
    if not designs:
        return
    p5 = {v["id"] for v in data.get("mocks", []) + data.get("diagrams", []) if v["phase"] == "P5"}
    owner, ids = {}, set()
    for i, design in enumerate(designs):
        at = f"designs[{i}]"
        if not isinstance(design, dict) or not isinstance(design.get("id"), str) or not DESIGN_ID.match(design["id"]):
            raise RecordError(f"{at}.id: expected DS-A … DS-D")
        if design["id"] in ids:
            raise RecordError(f"{at}.id: {design['id']} is repeated")
        ids.add(design["id"])
        _str(design, "title", at, required=True)
        _str(design, "summary", at)
        if design.get("status") not in DESIGN_STATUSES:
            raise RecordError(f"{at}.status: expected one of {', '.join(DESIGN_STATUSES)}")
        drawn = _strings(design, "mocks", at) + _strings(design, "diagrams", at)
        if not drawn:
            raise RecordError(f"{at}: a design draws at least one P5 mock or diagram")
        for vid in drawn:
            if vid not in p5:
                raise RecordError(f"{at}: {vid} is not a P5 mock or diagram")
            if vid in owner:
                raise RecordError(f"{at}: {vid} already belongs to {owner[vid]}")
            owner[vid] = design["id"]
        reason = _str(design, "reason", at)
        if design["status"] == "rejected" and not reason.strip():
            raise RecordError(f"{at}.reason: a rejected design carries the reason it lost")
        if design["status"] == "selected" and design.get("selected_by") not in SELECTED_BY:
            raise RecordError(f"{at}.selected_by: expected one of {', '.join(SELECTED_BY)}")
    loose = sorted(p5 - set(owner))
    if loose:
        raise RecordError(f"designs: {', '.join(loose)} belongs to no design; once designs are recorded, "
                          "every P5 mock and diagram belongs to one")
    statuses = [d["status"] for d in designs]
    if statuses.count("selected") > 1:
        raise RecordError("designs: more than one design is selected")
    if "selected" in statuses and "candidate" in statuses:
        raise RecordError("designs: once a design is selected, every other one is rejected with a reason")
    if statuses == ["selected"] and not designs[0].get("reason", "").strip():
        raise RecordError("designs[0].reason: a lone design is selected only with the reason no alternative existed")


def check_visuals(data):
    if not isinstance(data, dict) or data.get("version") != 1:
        raise RecordError("visuals.json: expected an object with \"version\": 1")
    unknown = set(data) - {"version", "mocks", "diagrams", "designs"}
    if unknown:
        raise RecordError(f"visuals.json: unknown keys {', '.join(sorted(unknown))}")
    seen = set()
    for key, check in (("mocks", check_mock), ("diagrams", check_diagram)):
        items = data.get(key, [])
        if not isinstance(items, list):
            raise RecordError(f"{key}: expected a list")
        for i, item in enumerate(items):
            check(item, f"{key}[{i}]")
            if item["id"] in seen:
                raise RecordError(f"{key}[{i}].id: {item['id']} is repeated")
            seen.add(item["id"])
    check_designs(data)


# ── The run record ───────────────────────────────────────────────────────────

def _flow(text):
    """A YAML flow value as the envelope uses it: scalars, [lists] and {maps}, nested."""
    pos = 0

    def ws():
        nonlocal pos
        while pos < len(text) and text[pos] in " \t\n":
            pos += 1

    def value(stops):
        nonlocal pos
        ws()
        if pos < len(text) and text[pos] in "[{":
            close, items, pairs = ("]" if text[pos] == "[" else "}"), [], {}
            pos += 1
            while True:
                ws()
                if pos < len(text) and text[pos] == close:
                    pos += 1
                    return items if close == "]" else pairs
                if close == "]":
                    items.append(value(",]"))
                else:
                    key = value(":}")
                    if not isinstance(key, str):
                        raise ValueError("a flow-mapping key must be a scalar")
                    if pos >= len(text) or text[pos] != ":":
                        raise ValueError("expected ':' in a flow mapping")
                    pos += 1
                    pairs[key] = value(",}")
                ws()
                if pos < len(text) and text[pos] == ",":
                    pos += 1
                elif pos >= len(text) or text[pos] != close:
                    raise ValueError(f"expected ',' or '{close}'")
        if pos < len(text) and text[pos] in "\"'":
            quote, start = text[pos], pos + 1
            end = text.find(quote, start)
            if end < 0:
                raise ValueError("unterminated quoted scalar")
            pos = end + 1
            return text[start:end]
        start = pos
        while pos < len(text) and text[pos] not in stops:
            pos += 1
        return text[start:pos].strip()

    result = value("")
    ws()
    if pos != len(text):
        raise ValueError("unexpected text after the value")
    return result


def _strip_comment(line):
    """Drop a trailing `# comment`; a '#' inside quotes or glued to a word is text."""
    quote = None
    for i, char in enumerate(line):
        if quote:
            quote = None if char == quote else quote
        elif char in "\"'":
            quote = char
        elif char == "#" and (i == 0 or line[i - 1] in " \t"):
            return line[:i].rstrip()
    return line.rstrip()


def _depth(value):
    """Open [ and { in a flow value, quoted text excluded."""
    depth, quote = 0, None
    for char in value:
        if quote:
            quote = None if char == quote else quote
        elif char in "\"'":
            quote = char
        elif char in "[{":
            depth += 1
        elif char in "]}":
            depth -= 1
    return depth


def parse_envelope(text, where):
    """The frontmatter of reference/run-record.md § The Document Envelope, and the body after it."""
    if not text.startswith("---\n"):
        raise RecordError(f"{where}: expected a frontmatter envelope opening with ---")
    end = text.find("\n---", 3)
    if end < 0:
        raise RecordError(f"{where}: the frontmatter envelope is not closed")
    fields, key, buf = {}, None, ""
    for raw in text[4:end].split("\n") + [""]:
        line = _strip_comment(raw)
        if key and buf[:1] in "[{" and buf and _depth(buf) > 0:
            if re.match(r"^[A-Za-z_][A-Za-z0-9_]*:", line):
                raise RecordError(f"{where}: {key}: the flow value is not closed before {line.split(':')[0]}:")
            buf += " " + line.strip()
            continue
        if key:
            try:
                fields[key] = _flow(buf)
            except ValueError as e:
                raise RecordError(f"{where}: {key}: {e}") from None
            key = None
        if not line.strip():
            continue
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):(.*)$", line)
        if not match:
            raise RecordError(f"{where}: cannot read frontmatter line {raw.strip()!r}")
        key, buf = match[1], match[2].strip()
    body = text[end + 4:]
    return fields, body[body.find("\n") + 1:] if "\n" in body else ""


def sections(body):
    """`## Heading` → its text, in order; text before the first heading is dropped."""
    out, name, lines, fence = [], None, [], False
    for line in body.split("\n"):
        if line.startswith("```"):
            fence = not fence
        if not fence and line.startswith("## "):
            if name is not None:
                out.append((name, "\n".join(lines).strip()))
            name, lines = line[3:].strip(), []
        elif name is not None:
            lines.append(line)
    if name is not None:
        out.append((name, "\n".join(lines).strip()))
    return out


def parse_run(text):
    """RUN.md: the title, the `**Key:** value` pairs of its header and of each section.

    A value continues on indented lines, as `**Re-bind:**` does in reference/run-record.md § What `resume` Reads.
    """
    title = next((line[2:].strip() for line in text.split("\n") if line.startswith("# ")), "")
    head = text.split("\n## ", 1)[0]
    pairs = lambda s: [(m[1].strip(), " ".join(m[2].split()))
                       for m in re.finditer(r"\*\*([^*]+?):\*\*[ \t]*([^·\n]*(?:\n[ \t]+[^·\n]*)*)", s)]
    return {"title": title, "header": pairs(head),
            "sections": [(name, pairs(body), body) for name, body in sections(text)]}


def load_record(run_dir):
    """Read and check everything render shows. Returns (record, sources) or raises RecordError."""
    run_dir = Path(run_dir)
    sources = {}

    def read(rel):
        path = run_dir / rel
        if path.is_symlink() or not path.is_file():
            raise RecordError(f"{rel}: not found as a regular file")
        data = path.read_bytes()
        sources[rel] = hashlib.sha256(data).hexdigest()
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            raise RecordError(f"{rel}: not UTF-8") from None

    if not run_dir.is_dir():
        raise RecordError(f"{run_dir}: not a directory")
    run = parse_run(read("RUN.md"))
    status = dict(run["header"]).get("Status", "")
    if not RUN_STATUS.match(status):
        raise RecordError(f"RUN.md: **Status:** {status!r} is not a run status (reference/run-record.md § Run Status)")
    docs = []
    for path in sorted(run_dir.iterdir()):
        if not PHASE_DOC.match(path.name):
            continue
        fields, body = parse_envelope(read(path.name), path.name)
        for key, allowed in (("status", STATUSES), ("gate", GATES)):
            if fields.get(key) not in allowed:
                raise RecordError(f"{path.name}: {key}: expected one of {', '.join(allowed)}")
        phase = fields.get("phase")
        if not isinstance(phase, str) or not phase.startswith(PHASE_PREFIX[path.name[:2]]):
            raise RecordError(f"{path.name}: phase: expected {PHASE_PREFIX[path.name[:2]]}… for this file number")
        for key in ("consumes", "produces"):
            value = fields.setdefault(key, [])
            if not isinstance(value, list) or not all(isinstance(v, str) and v for v in value):
                raise RecordError(f"{path.name}: {key}: expected a list of paths")
        engines = fields.setdefault("engines", [])
        if not isinstance(engines, list) or not all(
                isinstance(e, dict) and all(isinstance(v, str) for v in e.values()) for e in engines):
            raise RecordError(f"{path.name}: engines: expected a list of {{ role: …, cli: … }}")
        if not re.match(r"^[0-9]+\Z", str(fields.get("spawns", "0"))):
            raise RecordError(f"{path.name}: spawns: expected a count")
        parts = sections(body)
        if fields["status"] == "sealed" and not any(name == "Gate" for name, _ in parts):
            raise RecordError(f"{path.name}: a sealed document carries a ## Gate section")
        docs.append({"file": path.name, "num": path.name[:2], "fields": fields, "sections": parts})
    if any(d["num"] == other["num"] for i, d in enumerate(docs) for other in docs[:i]):
        raise RecordError("one document per phase: two documents share a phase number")
    extra = []
    for rel in ["90-delivery-report.md"] + sorted(
            f"artifacts/{p.name}" for p in (run_dir / "artifacts").glob("*.md") if p.is_file()):
        if (run_dir / rel).is_file():
            extra.append((rel, read(rel)))
    criteria = dict(extra).get("artifacts/acceptance-criteria.md")
    acs = list(dict.fromkeys(AC_ID.findall(criteria or "")))
    visuals = {"version": 1}
    if (run_dir / "artifacts" / "visuals.json").exists():
        try:
            visuals = json.loads(read("artifacts/visuals.json"))
        except json.JSONDecodeError as e:
            raise RecordError(f"artifacts/visuals.json: {e}") from None
        check_visuals(visuals)
        ran = {d["num"] for d in docs}
        design = next((d for d in docs if d["num"] == "05"), None)
        statuses = [d["status"] for d in visuals.get("designs", [])]
        if statuses and design and design["fields"]["status"] == "sealed" and "selected" not in statuses:
            raise RecordError("05-design.md is sealed, so Design Select has run: exactly one design is selected")
        for item in visuals.get("mocks", []) + visuals.get("diagrams", []):
            if "0" + item["phase"][1] not in ran:
                raise RecordError(f"{item['id']}: phase {item['phase']} has no document in this run")
            # Design Select's "ACs drawn" counts against the criteria file; an id it lacks would vanish from it.
            unknown = [a for a in item.get("acs", []) if a not in acs]
            if criteria is not None and unknown:
                raise RecordError(f"{item['id']}.acs: {', '.join(unknown)} not in artifacts/acceptance-criteria.md")
    return {"id": run_dir.name, "run": run, "docs": docs, "extra": extra, "visuals": visuals, "acs": acs}, sources


def source_digest(sources):
    """One digest over every source file and its name, so a renamed or added file changes it."""
    lines = "".join(f"{sha}  {rel}\n" for rel, sha in sorted(sources.items()))
    return hashlib.sha256(lines.encode("utf-8")).hexdigest()


# ── Page ─────────────────────────────────────────────────────────────────────

LABELS = {
    "en": {"title": "Run view", "phases": "Phases", "flow": "Artifact flow", "design": "Design",
           "screens": "Screens", "documents": "Documents", "not_run": "not run", "spawns": "spawns",
           "reentries": "re-entries", "before": "Today", "after": "Proposed", "recommended": "Recommended",
           "alternative": "Alternative {n}", "no_before": "New screen: nothing exists today.",
           "guardrails": "Guardrails", "intent": "Intent", "option": "Option", "acs": "Acceptance criteria",
           "copy_llm": "Copy for LLM", "copy_all": "Copy all screens for LLM", "copied": "Copied",
           "copy_failed": "Copy failed", "none": "Nothing recorded.", "legend": "Legend",
           "flow_note": "Documents (rounded) consume and produce artifacts (square); colour is the gate.",
           "mocks_note": "Mocks illustrate intent. The acceptance criteria, not the pixels, are what VERIFY checks.",
           "P2": "P2 · options compared", "P5": "P5 · the chosen design", "stamp": "Rendered from sources",
           "select": "Design Select", "select_note": "The judge compares the candidates; a person picks one. "
           "Only the selected design goes on to the working slice and the Risk Gate.",
           "status": {"candidate": "candidate", "selected": "selected", "rejected": "rejected"},
           "pending": "Awaiting selection", "screens_n": "Screens", "ac_cover": "ACs drawn",
           "missing": "not drawn", "changes": "Diagram changes", "reason": "Reason", "selected_by": "Selected by",
           "by": {"user": "the user", "delegated": "delegated by the grant"},
           "copy_design": "Copy this design for LLM",
           "change": {"existing": "existing", "new": "new", "changed": "changed", "removed": "removed"}},
    "ja": {"title": "ラン・ビュー", "phases": "フェーズ", "flow": "成果物の流れ", "design": "設計",
           "screens": "画面", "documents": "文書", "not_run": "未実行", "spawns": "spawn",
           "reentries": "再突入", "before": "現在", "after": "提案", "recommended": "推奨",
           "alternative": "代替案 {n}", "no_before": "新しい画面：現在は存在しません。",
           "guardrails": "ガードレール", "intent": "意図", "option": "選択肢", "acs": "受け入れ基準",
           "copy_llm": "LLM 用にコピー", "copy_all": "全画面を LLM 用にコピー", "copied": "コピーしました",
           "copy_failed": "コピーできませんでした", "none": "記録なし。", "legend": "凡例",
           "flow_note": "文書（角丸）が成果物（四角）を消費・生成します。色はゲートの結果です。",
           "mocks_note": "モックは意図の図示です。VERIFY が確かめるのはピクセルではなく受け入れ基準です。",
           "P2": "P2 · 選択肢の比較", "P5": "P5 · 採用した設計", "stamp": "生成元",
           "select": "設計案の選定", "select_note": "judge が候補を比較し、人が1案を選びます。"
           "作業スライスと Risk Gate に進むのは選ばれた案だけです。",
           "status": {"candidate": "候補", "selected": "採用", "rejected": "不採用"},
           "pending": "選定待ち", "screens_n": "画面", "ac_cover": "描かれた受け入れ基準",
           "missing": "未描画", "changes": "設計図の変更", "reason": "理由", "selected_by": "選定者",
           "by": {"user": "ユーザー", "delegated": "許可による委任"},
           "copy_design": "この設計案を LLM 用にコピー",
           "change": {"existing": "既存", "new": "新規", "changed": "変更", "removed": "削除"}},
}

VIEWPORT_SIZE = {"mobile": (390, 844, 1.0), "desktop": (1280, 800, 0.4)}
# Copy for LLM: reads the embedded Markdown and copies it; buttons stay hidden without script.
COPY_SCRIPT = """\
(function () {
  var data = JSON.parse(document.getElementById('llm-data').textContent), ids = Object.keys(data.items);
  function fallback(text) {
    return new Promise(function (resolve, reject) {
      var t = document.createElement('textarea'), ok = false;
      t.value = text; t.readOnly = true; t.style.position = 'fixed'; t.style.left = '-9999px';
      document.body.appendChild(t); t.select();
      try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
      document.body.removeChild(t);
      if (ok) resolve(); else reject(new Error('copy'));
    });
  }
  function copy(text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text).catch(function () { return fallback(text); });
    }
    return fallback(text);
  }
  Array.prototype.forEach.call(document.querySelectorAll('button[data-copy]'), function (b) {
    var label = b.textContent, timer;
    function done(text) {
      b.textContent = text; clearTimeout(timer);
      timer = setTimeout(function () { b.textContent = label; }, 2000);
    }
    b.hidden = false;
    b.addEventListener('click', function () {
      var key = b.getAttribute('data-copy');
      copy(key === '*' ? ids.map(function (id) { return data.items[id]; }).join('\\n')
           : key.indexOf('DS-') === 0 ? data.designs[key] : data.items[key])
        .then(function () { done(data.copied); }, function () { done(data.copy_failed); });
    });
  });
})();
"""
# The page and every srcdoc frame (which inherits it) load nothing from anywhere.
CSP = ("default-src 'none'; style-src 'unsafe-inline'; img-src data:; font-src data:; script-src 'sha256-"
       + base64.b64encode(hashlib.sha256(COPY_SCRIPT.encode("utf-8")).digest()).decode("ascii") + "'")
CSS = """\
:root{color-scheme:light;--bg:#f6f5f1;--panel:#fff;--text:#1b1b1b;--muted:#5a5a5a;--line:#dcd9d2;--tint:#efede6;\
--accent:#1f3f66;--pass:#1d6b3a;--fail:#8a1c1c;--open:#7a4800;--new:#1f3f66;--changed:#7a4800;--removed:#8a1c1c}
@media(prefers-color-scheme:dark){:root{color-scheme:dark;--bg:#17171a;--panel:#1f1f23;--text:#ece9e2;--muted:#b3aea4;\
--line:#3a3936;--tint:#26252a;--accent:#a9c3e6;--pass:#8fd1a5;--fail:#f2a19a;--open:#e8bf7a;--new:#a9c3e6;\
--changed:#e8bf7a;--removed:#f2a19a}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);overflow-wrap:anywhere;\
font:14px/1.65 system-ui,-apple-system,"Hiragino Sans","Noto Sans JP",sans-serif}
main{max-width:1180px;margin:auto;padding:32px 16px 48px}
a{color:var(--accent);text-underline-offset:3px}
h1{font-size:clamp(24px,3.5vw,32px);line-height:1.25;margin:4px 0 8px}
h2{font-size:20px;margin:36px 0 10px;padding-top:12px;border-top:1px solid var(--line)}
h3{font-size:16px;margin:18px 0 6px}
.eyebrow,.muted,figcaption,.meta{color:var(--muted)}
.eyebrow{font-size:12px;font-weight:700;letter-spacing:.12em;text-transform:uppercase}
.pairs{display:flex;flex-wrap:wrap;gap:6px 18px;margin:6px 0;padding:0;list-style:none}
.pairs b{color:var(--muted);font-weight:600;margin-right:4px}
nav{display:flex;flex-wrap:wrap;gap:6px 16px;margin:12px 0}
.timeline{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px}
.phase{display:block;text-decoration:none;color:inherit;background:var(--panel);border:1px solid var(--line);\
border-top:4px solid var(--line);border-radius:8px;padding:10px 12px;font-size:13px}
.phase b{display:block;font-size:14px}
.phase.pass{border-top-color:var(--pass)}.phase.fail{border-top-color:var(--fail)}
.phase.open{border-top-color:var(--open)}.phase.none{opacity:.55;border-style:dashed}
.badge{display:inline-block;font-size:12px;font-weight:700;margin-right:6px}
.badge.pass{color:var(--pass)}.badge.fail{color:var(--fail)}.badge.open{color:var(--open)}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:16px 18px;margin:14px 0}
.head{display:flex;justify-content:space-between;align-items:flex-start;gap:12px}
.diagram{overflow:auto;max-width:100%}
svg text{fill:var(--text);font:12px system-ui,-apple-system,"Hiragino Sans","Noto Sans JP",sans-serif}
svg .node{fill:var(--panel);stroke:var(--line);stroke-width:1.5}
svg .new{stroke:var(--new);stroke-width:2.5}svg .changed{stroke:var(--changed);stroke-width:2.5;stroke-dasharray:6 3}
svg .removed{stroke:var(--removed);stroke-dasharray:3 3;opacity:.7}svg .external{stroke-dasharray:4 3}
svg .pass{stroke:var(--pass);stroke-width:2.5}svg .fail{stroke:var(--fail);stroke-width:2.5}
svg .open{stroke:var(--open);stroke-width:2.5}
svg .edge{fill:none;stroke:var(--muted);stroke-width:1.3}svg .edge.new{stroke:var(--new);stroke-width:2}
svg .edge.changed{stroke:var(--changed)}svg .edge.removed{stroke:var(--removed)}
svg .arrow{fill:var(--muted)}svg .elabel{fill:var(--bg)}svg .label-removed{text-decoration:line-through}
.legend{display:flex;flex-wrap:wrap;gap:4px 14px;font-size:12px;color:var(--muted);margin-top:6px}
.legend span::before{content:"";display:inline-block;width:18px;height:0;border-top:3px solid var(--line);\
margin-right:5px;vertical-align:middle}
.legend .new::before{border-color:var(--new)}.legend .changed::before{border-top-style:dashed;border-color:var(--changed)}
.legend .removed::before{border-top-style:dotted;border-color:var(--removed)}
.compare{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;margin:14px 0 6px}
figure{margin:0;min-width:0}.compare .alt{grid-column:2}
figcaption{font-size:13px;margin-bottom:6px}figcaption b{color:var(--text);margin-right:6px}
.screen{width:max-content;max-width:100%;overflow:auto;border:1px solid var(--line);border-radius:8px;background:#fff}
.frame{overflow:hidden}iframe{display:block;border:0;transform-origin:0 0;background:#fff}
.empty{display:flex;align-items:center;justify-content:center;padding:24px;text-align:center;\
background:var(--tint);color:var(--muted)}
code,pre{font:12px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace}
pre{background:var(--tint);border-radius:6px;padding:10px;overflow:auto}
table{border-collapse:collapse;margin:8px 0;font-size:13px;display:block;overflow:auto}
th,td{border:1px solid var(--line);padding:4px 8px;text-align:left;vertical-align:top}
th{background:var(--tint)}
details{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:10px 16px;margin:10px 0}
summary{cursor:pointer;font-weight:700}
button{font:inherit;font-size:13px;cursor:pointer;background:var(--panel);color:var(--text);\
border:1px solid var(--line);border-radius:7px;padding:6px 10px;white-space:nowrap}
button:hover{background:var(--tint)}[hidden]{display:none!important}
.designs{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px}
.ds{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px 16px;min-width:0}
.ds.selected{border:2px solid var(--pass)}.ds.rejected{opacity:.8}
.badge.selected{color:var(--pass)}.badge.rejected{color:var(--fail)}.badge.candidate{color:var(--open)}
.facts{display:grid;grid-template-columns:max-content 1fr;gap:2px 10px;font-size:13px;margin:8px 0}
.facts dt{color:var(--muted)}.facts dd{margin:0}
.thumbs{display:flex;flex-wrap:wrap;gap:8px;margin:8px 0}.thumbs figure{flex:none}
@media(max-width:860px){.compare{grid-template-columns:minmax(0,1fr)}.compare .alt{grid-column:auto}}
@media print{button{display:none!important}details{break-inside:avoid}}
"""

esc = html.escape


def md_inline(text):
    """Inline Markdown: `code`, **bold** and [text](link) shown as its text; everything else escaped."""
    out = []
    for i, part in enumerate(re.split(r"(`[^`\n]+`)", text)):
        if i % 2:
            out.append(f"<code>{esc(part[1:-1])}</code>")
            continue
        part = esc(part)
        part = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", part)
        out.append(re.sub(r"\[([^\]]+)\]\([^)\s]*\)", r"\1", part))
    return "".join(out)


def _cells(row):
    """A pipe-table row's cells; a pipe inside `code` or escaped as \\| is text."""
    cells, cell, code, i = [], "", False, 0
    row = row.strip().removeprefix("|")
    if row.endswith("|") and not row.endswith("\\|"):
        row = row[:-1]
    while i < len(row):
        if row[i] == "\\" and row[i + 1:i + 2] == "|":
            cell, i = cell + "|", i + 2
            continue
        if row[i] == "`":
            code = not code
        if row[i] == "|" and not code:
            cells.append(cell.strip())
            cell = ""
        else:
            cell += row[i]
        i += 1
    return cells + [cell.strip()]


def md_html(text):
    """The Markdown a phase document uses: headings, paragraphs, lists, pipe tables, fences."""
    lines, out, i = text.split("\n"), [], 0
    block = re.compile(r"^(```|\||#{1,6} |\s*(?:[-*]|\d+\.) )")
    while i < len(lines):
        line = lines[i]
        if line.startswith("```"):
            end = next((j for j in range(i + 1, len(lines)) if lines[j].startswith("```")), len(lines))
            out.append(f"<pre><code>{esc(chr(10).join(lines[i + 1:end]))}</code></pre>")
            i = end + 1
        elif line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                if not re.match(r"^\|[\s:|-]+\|?\s*$", lines[i]):
                    rows.append(_cells(lines[i]))
                i += 1
            if not rows:
                continue
            head, *body = rows
            out.append("<table><tr>" + "".join(f"<th>{md_inline(c)}</th>" for c in head) + "</tr>"
                       + "".join("<tr>" + "".join(f"<td>{md_inline(c)}</td>" for c in r) + "</tr>" for r in body)
                       + "</table>")
        elif re.match(r"^#{1,6} ", line):
            out.append(f"<h4>{md_inline(line.lstrip('#').strip())}</h4>")
            i += 1
        elif re.match(r"^\s*(?:[-*]|\d+\.) ", line):
            tag = "ol" if re.match(r"^\s*\d+\.", line) else "ul"
            items = []
            # A fence, table or heading ends the list even without a blank line before it.
            while i < len(lines) and lines[i].strip() and not re.match(r"^(```|\||#{1,6} )", lines[i]):
                if re.match(r"^\s*(?:[-*]|\d+\.) ", lines[i]):
                    items.append(re.sub(r"^\s*(?:[-*]|\d+\.) ", "", lines[i]))
                else:
                    items[-1] += " " + lines[i].strip()
                i += 1
            out.append(f"<{tag}>" + "".join(f"<li>{md_inline(t)}</li>" for t in items) + f"</{tag}>")
        elif not line.strip():
            i += 1
        else:
            para = []
            while i < len(lines) and lines[i].strip() and not block.match(lines[i]):
                para.append(lines[i].strip())
                i += 1
            out.append(f"<p>{md_inline(' '.join(para))}</p>")
    return "".join(out)


# ── Diagram layout: longest-path layers, one barycentre sweep, cubic edges ───────

def _wrap(label, limit=26):
    """Lines of at most `limit` columns; a CJK character counts as two."""
    lines, line, width = [], "", 0
    for word in re.findall(r"[　-鿿＀-￯]|[^\s　-鿿＀-￯]+|\s+", label):
        w = 2 * len(word) if re.match(r"[　-鿿＀-￯]", word) else len(word)
        if word.isspace():
            if line:
                line, width = line + " ", width + 1
            continue
        if width + w > limit and line.strip():
            lines.append(line.strip())
            line, width = "", 0
        # A path or identifier longer than a line is cut, not left to overflow the node.
        while w > limit:
            lines.append(word[:limit])
            word, w = word[limit:], w - limit
        line, width = line + word, width + w
    return [ln for ln in lines + [line.strip()] if ln] or [""]


def layout(nodes, edges):
    """Rank by longest path over the edges that keep the graph acyclic; order ranks by barycentre."""
    ids = [n["id"] for n in nodes]
    succ = {i: [] for i in ids}
    state = {}

    def visit(n):
        state[n] = 1
        for e in edges:
            if e["from"] == n:
                if state.get(e["to"]) != 1:
                    succ[n].append(e["to"])
                    if e["to"] not in state:
                        visit(e["to"])
        state[n] = 2

    for n in ids:
        if n not in state:
            visit(n)
    rank = {n: 0 for n in ids}
    for _ in ids:
        for n in ids:
            for m in succ[n]:
                if m != n and rank[m] < rank[n] + 1:
                    rank[m] = rank[n] + 1
    layers = {}
    for n in ids:
        layers.setdefault(rank[n], []).append(n)
    for r in sorted(layers)[1:]:
        prev = {n: i for i, n in enumerate(layers[r - 1])} if r - 1 in layers else {}
        def bary(n):
            ps = [prev[e["from"]] for e in edges if e["to"] == n and e["from"] in prev]
            return sum(ps) / len(ps) if ps else float(ids.index(n))
        layers[r].sort(key=bary)
    return layers


def render_diagram(diagram, T, tones=None):
    """Inline SVG for one diagram; tones maps a node id to pass/fail/open for the artifact flow."""
    nodes = {n["id"]: n for n in diagram["nodes"]}
    edges = diagram.get("edges", [])
    layers = layout(diagram["nodes"], edges)
    across = diagram.get("direction", "LR") == "LR"
    size = {}
    for n in nodes.values():
        lines = _wrap(n["label"])
        size[n["id"]] = (max(96, min(230, 16 + 7 * max(len(ln) + sum(ord(c) > 0x2fff for c in ln)
                                                        for ln in lines))), 18 + 16 * len(lines), lines)
    # Edge labels sit between ranks, so the gap grows to the widest one.
    widest = max((10 + 6.5 * (len(e["label"]) + sum(ord(c) > 0x2fff for c in e["label"]))
                  for e in edges if e.get("label")), default=0)
    pos, main_at, gap_main, gap_cross = {}, 20, max(70, round(widest) + 30) if across else 70, 26
    for r in sorted(layers):
        extent = max(size[n][0] if across else size[n][1] for n in layers[r])
        cross_at = 20
        for n in layers[r]:
            w, h, _ = size[n]
            pos[n] = (main_at, cross_at) if across else (cross_at, main_at)
            cross_at += (h if across else w) + gap_cross
        main_at += extent + gap_main
    rank = {n: r for r, layer in layers.items() for n in layer}
    # An edge that does not run forward loops round a lane outside the nodes, one lane each.
    back = [e for e in edges if rank[e["to"]] <= rank[e["from"]]]
    width = max(pos[n][0] + size[n][0] for n in pos) + 20
    height = max(pos[n][1] + size[n][1] for n in pos) + 20
    lanes = {id(e): (height if across else width) + 10 + 26 * i for i, e in enumerate(back)}
    if back:
        if across:
            height += 26 * len(back) + 10
        else:
            width += 26 * len(back) + 10
    marker = f"a-{esc(diagram['id'])}"
    out = [f"<svg role='img' aria-label='{esc(diagram['title'])}' width='{width}' height='{height}' "
           f"viewBox='0 0 {width} {height}' xmlns='http://www.w3.org/2000/svg'>"
           f"<defs><marker id='{marker}' viewBox='0 0 10 10' refX='9' refY='5' markerWidth='7' markerHeight='7' "
           f"orient='auto-start-reverse'><path class='arrow' d='M0,0L10,5L0,10z'/></marker></defs>"]
    labels = []
    for e in edges:
        (x1, y1), (w1, h1, _), (x2, y2), (w2, h2, _) = pos[e["from"]], size[e["from"]], pos[e["to"]], size[e["to"]]
        lane = lanes.get(id(e))
        if lane is not None and across:
            sx, sy, tx, ty = x1 + w1 / 2, y1 + h1, x2 + w2 / 2 + (8 if e["from"] == e["to"] else 0), y2 + h2
            d = f"M{sx:.0f},{sy:.0f} C{sx:.0f},{lane:.0f} {tx:.0f},{lane:.0f} {tx:.0f},{ty:.0f}"
            mx, my = (sx + tx) / 2, lane - 6
        elif lane is not None:
            sx, sy, tx, ty = x1 + w1, y1 + h1 / 2, x2 + w2, y2 + h2 / 2 + (8 if e["from"] == e["to"] else 0)
            d = f"M{sx:.0f},{sy:.0f} C{lane:.0f},{sy:.0f} {lane:.0f},{ty:.0f} {tx:.0f},{ty:.0f}"
            mx, my = lane - 6, (sy + ty) / 2
        elif across:
            sx, sy, tx, ty = x1 + w1, y1 + h1 / 2, x2, y2 + h2 / 2
            bend = max(30, abs(tx - sx) / 2)
            d = f"M{sx:.0f},{sy:.0f} C{sx + bend:.0f},{sy:.0f} {tx - bend:.0f},{ty:.0f} {tx:.0f},{ty:.0f}"
        else:
            sx, sy, tx, ty = x1 + w1 / 2, y1 + h1, x2 + w2 / 2, y2
            bend = max(30, abs(ty - sy) / 2)
            d = f"M{sx:.0f},{sy:.0f} C{sx:.0f},{sy + bend:.0f} {tx:.0f},{ty - bend:.0f} {tx:.0f},{ty:.0f}"
        change = e.get("change", "existing")
        out.append(f"<path class='edge {change}' d='{d}' marker-end='url(#{marker})'/>")
        if e.get("label"):
            if lane is None:
                mx, my = (sx + tx) / 2, (sy + ty) / 2
            text = e["label"]
            w = 10 + 6.5 * (len(text) + sum(ord(c) > 0x2fff for c in text))
            labels.append(f"<rect class='elabel' x='{mx - w / 2:.0f}' y='{my - 9:.0f}' width='{w:.0f}' height='18' "
                          f"rx='4'/><text{' class=label-removed' if change == 'removed' else ''} x='{mx:.0f}' "
                          f"y='{my + 4:.0f}' text-anchor='middle'>{esc(text)}</text>")
    for nid, n in nodes.items():
        (x, y), (w, h, lines) = pos[nid], size[nid]
        kind, change = n.get("type", "component"), n.get("change", "existing")
        cls = f"node {change} {kind} {(tones or {}).get(nid, '')}".strip()
        radius = {"actor": h / 2, "state": 14, "step": 10, "store": 2}.get(kind, 6)
        title = esc(n["label"] + (f" · {n['source']}" if n.get("source") else "")
                    + ("" if change == "existing" else f" · {T['change'][change]}"))
        out.append(f"<g><title>{title}</title><rect class='{cls}' x='{x}' y='{y}' width='{w}' height='{h}' "
                   f"rx='{radius:.0f}'/>")
        if kind == "store":
            out.append(f"<path class='{cls}' d='M{x},{y + 6}h{w}' fill='none'/>")
        text_cls = " class='label-removed'" if change == "removed" else ""
        for i, ln in enumerate(lines):
            out.append(f"<text{text_cls} x='{x + w / 2:.0f}' y='{y + 22 + 16 * i}' text-anchor='middle'>"
                       f"{esc(ln)}</text>")
        out.append("</g>")
    # Labels last, so no node hides one.
    out += labels
    out.append("</svg>")
    return "".join(out)


def legend(T):
    return ("<div class='legend'>" + "".join(f"<span class='{c}'>{esc(T['change'][c])}</span>" for c in CHANGES)
            + "</div>")


# ── Mocks ────────────────────────────────────────────────────────────────────

def mock_screens(mock, T):
    alternatives = mock.get("alternatives", [])
    return [(T["before"], mock.get("before")), (T["recommended"] if alternatives else T["after"], mock["after"]),
            *((T["alternative"].format(n=i), s) for i, s in enumerate(alternatives, 1))]


def mock_frame(mock, screen, title, shrink=1.0):
    width, height, scale = VIEWPORT_SIZE[mock["viewport"]]
    scale *= shrink
    height = mock.get("height", height)
    shown = f"width:{round(width * scale)}px;height:{round(height * scale)}px"
    if screen is None:
        return None, shown
    # A srcdoc document resolves URLs against the parent page; this base keeps
    # #fragment links inside the frame instead of navigating it away.
    doc = ("<!doctype html><html><head><meta charset='utf-8'><base href='about:srcdoc'>"
           f"<meta name='viewport' content='width={width}'>"
           "<style>html{-webkit-print-color-adjust:exact;print-color-adjust:exact}body{margin:0}"
           f"{mock.get('css', '')}</style></head><body>{screen['html']}</body></html>")
    return (f"<iframe sandbox title='{esc(title)}' width='{width}' height='{height}' "
            f"style='width:{width}px;height:{height}px;transform:scale({scale})' srcdoc='{esc(doc)}'></iframe>"), shown


def fenced(label, body, info="text"):
    fence = "`" * max(3, 1 + max((len(run) for run in re.findall(r"`+", body)), default=0))
    return ["", f"### {' '.join(label.split())}", fence + info, body, fence]


def mock_markdown(mock, run_id, T):
    """A mock as Markdown for a model that builds or refines the screen: intent, ACs, guardrails, markup."""
    width, height, _ = VIEWPORT_SIZE[mock["viewport"]]
    out = [f"## {mock['id']} · {' '.join(mock['title'].split())}", "",
           f"- run: `{run_id}` · {T[mock['phase']]}",
           f"- viewport: {mock['viewport']} {width}×{mock.get('height', height)}"]
    if mock.get("option"):
        out.append(f"- {T['option']}: {' '.join(mock['option'].split())}")
    if mock.get("acs"):
        out.append(f"- {T['acs']}: {', '.join(mock['acs'])}")
    for key in ("intent", "guardrails"):
        if mock.get(key, "").strip():
            out += fenced(T[key], mock[key])
    style = f"<style>\n{mock['css']}\n</style>\n" if mock.get("css") else ""
    for name, screen in mock_screens(mock, T):
        if screen is None:
            out += ["", f"### {name}", "", T["no_before"]]
            continue
        label = " · ".join([name, *([screen["caption"]] if screen.get("caption") else []),
                            *([f"`{screen['source']}`"] if screen.get("source") else [])])
        out += fenced(label, style + screen["html"], "html")
    return "\n".join(out) + "\n"


def render_mock(mock, T, copyable=True):
    figures = []
    for i, (name, screen) in enumerate(mock_screens(mock, T)):
        frame, shown = mock_frame(mock, screen, f"{mock['id']} {name}")
        caption = [f"<b>{esc(name)}</b>", *([esc(screen["caption"])] if screen and screen.get("caption") else []),
                   *([f"<code>{esc(screen['source'])}</code>"] if screen and screen.get("source") else [])]
        body = (f"<div class='frame' style='{shown}'>{frame}</div>" if frame
                else f"<div class='empty' style='{shown}'>{esc(T['no_before'])}</div>")
        figures.append(f"<figure{' class=alt' if i > 1 else ''}><figcaption>{' · '.join(caption)}</figcaption>"
                       f"<div class='screen'>{body}</div></figure>")
    facts = [(T["option"], mock.get("option")), (T["acs"], ", ".join(mock.get("acs", [])))]
    return (f"<section class='card' id='{esc(mock['id'])}'><div class='head'><div>"
            f"<span class='badge'>{esc(mock['id'])}</span><h3>{esc(mock['title'])}</h3></div>"
            + (f"<button type='button' data-copy='{esc(mock['id'])}' aria-live='polite' hidden>"
               f"{esc(T['copy_llm'])}</button>" if copyable else "") + "</div>"
            + "".join(f"<p class='meta'><b>{esc(k)}</b> {esc(v)}</p>" for k, v in facts if v)
            + (f"<p>{esc(mock['intent'])}</p>" if mock.get("intent") else "")
            + f"<div class='compare'>{''.join(figures)}</div>"
            + (f"<p class='muted'><b>{esc(T['guardrails'])}</b> {esc(mock['guardrails'])}</p>"
               if mock.get("guardrails") else "") + "</section>")


def design_card(design, by_id, acs, T):
    """One candidate design: its facts computed from the record, its screens as thumbnails, its outcome."""
    mocks = [by_id[v] for v in design.get("mocks", [])]
    diagrams = [by_id[v] for v in design.get("diagrams", [])]
    drawn = {a for v in mocks + diagrams for a in v.get("acs", [])}
    cover = (f"{len(drawn & set(acs))}/{len(acs)}" + (f" · {T['missing']}: {', '.join(a for a in acs if a not in drawn)}"
                                                       if set(acs) - drawn else "")) if acs else ", ".join(sorted(drawn))
    counts = {c: sum(n.get("change", "existing") == c for d in diagrams for n in d["nodes"])
              + sum(e.get("change", "existing") == c for d in diagrams for e in d.get("edges", []))
              for c in ("new", "changed", "removed")}
    facts = [(T["screens_n"], str(len(mocks))), (T["ac_cover"], cover or "—"),
             (T["changes"], " · ".join(f"{T['change'][c]} {n}" for c, n in counts.items()) if diagrams else "—")]
    if design["status"] == "selected":
        facts.append((T["selected_by"], T["by"][design["selected_by"]]))
    if design.get("reason"):
        facts.append((T["reason"], design["reason"]))
    thumbs = []
    for m in mocks:
        frame, shown = mock_frame(m, m["after"], f"{m['id']} {T['after']}", shrink=0.4)
        thumbs.append(f"<figure><figcaption><a href='#{esc(m['id'])}'>{esc(m['id'])}</a></figcaption>"
                      f"<div class='screen'><div class='frame' style='{shown}'>{frame}</div></div></figure>")
    links = " ".join(f"<a href='#{esc(d['id'])}'>{esc(d['id'])}</a>" for d in diagrams)
    copy = (f"<button type='button' data-copy='{esc(design['id'])}' aria-live='polite' hidden>"
            f"{esc(T['copy_design'])}</button>" if design["status"] == "selected" else "")
    return (f"<section class='ds {design['status']}' id='{esc(design['id'])}'><div class='head'><div>"
            f"<span class='badge'>{esc(design['id'])}</span>"
            f"<span class='badge {design['status']}'>{esc(T['status'][design['status']])}</span></div>{copy}</div>"
            f"<h3>{esc(design['title'])}</h3>" + (f"<p>{esc(design['summary'])}</p>" if design.get("summary") else "")
            + "<dl class='facts'>" + "".join(f"<dt>{esc(k)}</dt><dd>{esc(v)}</dd>" for k, v in facts) + "</dl>"
            + (f"<div class='thumbs'>{''.join(thumbs)}</div>" if thumbs else "")
            + (f"<p class='muted'>{links}</p>" if links else "") + "</section>")


def p5_groups(visuals, items, T):
    """P2 as one group; P5 per design when designs are recorded (selected first), otherwise one group."""
    groups = [(T["P2"], [v for v in items if v["phase"] == "P2"])]
    designs = sorted(visuals.get("designs", []), key=lambda d: (d["status"] != "selected", d["id"]))
    if not designs:
        return groups + [(T["P5"], [v for v in items if v["phase"] == "P5"])]
    for d in designs:
        ids = set(d.get("mocks", [])) | set(d.get("diagrams", []))
        groups.append((f"{d['id']} · {d['title']} · {T['status'][d['status']]}", [v for v in items if v["id"] in ids]))
    return groups


# ── The page ─────────────────────────────────────────────────────────────────

def artifact_flow(record):
    """The run's own design: phase documents consuming and producing artifacts, toned by gate."""
    nodes, edges, tones, seen = [], [], {}, set()

    def node(nid, label, kind):
        if nid not in seen:
            seen.add(nid)
            nodes.append({"id": nid, "label": label, "type": kind})

    for d in record["docs"]:
        node(d["file"], f"{PHASES[d['num']]} · {d['file']}", "step")
        f = d["fields"]
        tones[d["file"]] = "open" if f["status"] == "open" else {"pass": "pass", "fail": "fail"}.get(f["gate"], "")
    for d in record["docs"]:
        for rel in d["fields"].get("consumes", []):
            node(rel, rel, "step" if PHASE_DOC.match(rel) else "store")
            edges.append({"from": rel, "to": d["file"]})
        for rel in d["fields"].get("produces", []):
            node(rel, rel, "step" if PHASE_DOC.match(rel) else "store")
            edges.append({"from": d["file"], "to": rel})
    return {"id": "D-00", "title": "artifact flow", "direction": "LR", "nodes": nodes, "edges": edges}, tones


def render_page(record, digest, lang):
    T = LABELS[lang]
    run, docs, visuals = record["run"], {d["num"]: d for d in record["docs"]}, record["visuals"]
    mocks, diagrams = visuals.get("mocks", []), visuals.get("diagrams", [])
    pairs = lambda ps: "<ul class='pairs'>" + "".join(f"<li><b>{esc(k)}</b>{md_inline(v)}</li>" for k, v in ps) + "</ul>"
    head = [f"<div class='eyebrow'>feature-lifecycle · {esc(T['title'])}</div>",
            f"<h1>{esc(run['title'] or record['id'])}</h1>", pairs(run["header"])]
    for name, ps, body in run["sections"]:
        if name in ("Resume", "Budget"):
            head.append(f"<p class='meta'><b>{esc(name)}</b></p>" + (pairs(ps) if ps else md_html(body)))
    designs = visuals.get("designs", [])
    nav = [("phases", T["phases"]), ("flow", T["flow"])]
    nav += [("select", T["select"])] if designs else []
    nav += [("design", T["design"])] if diagrams else []
    nav += [("screens", T["screens"])] if mocks else []
    nav += [("documents", T["documents"])]
    head.append("<nav>" + "".join(f"<a href='#{a}'>{esc(t)}</a>" for a, t in nav) + "</nav>")

    cards = []
    for num, label in PHASES.items():
        d = docs.get(num)
        if not d:
            cards.append(f"<div class='phase none'><b>{esc(label)}</b>{esc(T['not_run'])}</div>")
            continue
        f = d["fields"]
        tone = "open" if f["status"] == "open" else f["gate"] if f["gate"] in ("pass", "fail") else ""
        reentries = sum(name.startswith("Re-entry") for name, _ in d["sections"])
        engines = ", ".join(f"{e.get('role', '?')}:{e.get('cli', '?')}" if isinstance(e, dict) else str(e)
                            for e in f.get("engines", []))
        cards.append(f"<a class='phase {tone.replace('/', '')}' href='#doc-{num}'><b>{esc(label)}</b>"
                     f"<span class='badge {tone}'>{esc(f['status'])} · gate {esc(f['gate'])}</span><br>"
                     + (f"{esc(str(f['spawns']))} {esc(T['spawns'])} · " if "spawns" in f else "")
                     + (f"{reentries} {esc(T['reentries'])} · " if reentries else "")
                     + f"<span class='muted'>{esc(engines)}</span></a>")
    flow, tones = artifact_flow(record)
    body = ["<header>", *head, "</header>",
            f"<h2 id='phases'>{esc(T['phases'])}</h2><div class='timeline'>{''.join(cards)}</div>",
            f"<h2 id='flow'>{esc(T['flow'])}</h2><p class='muted'>{esc(T['flow_note'])}</p>",
            f"<div class='card diagram'>{render_diagram(flow, T, tones) if flow['nodes'] else esc(T['none'])}</div>"]
    by_id = {v["id"]: v for v in mocks + diagrams}
    if designs:
        pending = "" if any(d["status"] == "selected" for d in designs) else f" <span class='badge candidate'>{esc(T['pending'])}</span>"
        body.append(f"<h2 id='select'>{esc(T['select'])}{pending}</h2><p class='muted'>{esc(T['select_note'])}</p>"
                    "<div class='designs'>" + "".join(design_card(d, by_id, record["acs"], T) for d in designs)
                    + "</div>")
    if diagrams:
        body.append(f"<h2 id='design'>{esc(T['design'])}</h2>")
        for heading, group in p5_groups(visuals, diagrams, T):
            if group:
                body.append(f"<h3>{esc(heading)}</h3>")
            for dg in group:
                body.append(f"<section class='card' id='{esc(dg['id'])}'><span class='badge'>{esc(dg['id'])}</span>"
                            f"<span class='muted'>{esc(dg['kind'])}</span>"
                            f"<h3>{esc(dg['title'])}</h3>"
                            + (f"<p>{esc(dg['intent'])}</p>" if dg.get("intent") else "")
                            + f"<div class='diagram'>{render_diagram(dg, T)}</div>{legend(T)}</section>")
    items = {}
    if mocks:
        body.append(f"<h2 id='screens'>{esc(T['screens'])}</h2><p class='muted'>{esc(T['mocks_note'])}</p>"
                    f"<p><button type='button' data-copy='*' aria-live='polite' hidden>{esc(T['copy_all'])}"
                    "</button></p>")
        rejected = {v for d in designs if d["status"] == "rejected" for v in d.get("mocks", [])}
        for heading, group in p5_groups(visuals, mocks, T):
            if group:
                body.append(f"<h3>{esc(heading)}</h3>" + "".join(render_mock(m, T, m["id"] not in rejected)
                                                                  for m in group))
            # A rejected design's screens stay visible but are never handed on to build.
            items.update({m["id"]: mock_markdown(m, record["id"], T) for m in group if m["id"] not in rejected})
    body.append(f"<h2 id='documents'>{esc(T['documents'])}</h2>")
    for d in record["docs"]:
        content = "".join(f"<h3>{esc(name)}</h3>{md_html(text) or esc(T['none'])}" for name, text in d["sections"])
        body.append(f"<details id='doc-{d['num']}'{' open' if d['fields']['gate'] == 'fail' else ''}>"
                    f"<summary>{esc(PHASES[d['num']])} · <code>{esc(d['file'])}</code></summary>{content}</details>")
    for rel, text in record["extra"]:
        body.append(f"<details><summary><code>{esc(rel)}</code></summary>{md_html(text)}</details>")
    body.append(f"<p class='muted'>{esc(T['stamp'])}: <code>{digest}</code></p>")
    # Inside a script element only "<" can end the data early; JSON keeps it as <.
    copies = {d["id"]: f"# {d['id']} · {d['title']}\n\n{d.get('summary', '')}\n\n"
              + "\n".join(items[m] for m in d.get("mocks", []) if m in items)
              for d in designs if d["status"] == "selected"}
    payload = json.dumps({"items": items, "designs": copies, "copied": T["copied"], "copy_failed": T["copy_failed"]},
                         ensure_ascii=False).replace("<", "\\u003c")
    return ("<!doctype html>\n"
            f"<html lang='{lang}'><head><meta charset='utf-8'><meta name='{STAMP}' content='{digest}'>"
            f"<meta http-equiv='Content-Security-Policy' content=\"{CSP}\">"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{esc(T['title'])} · {esc(record['id'])}</title><style>{CSS}</style></head>"
            f"<body><main>{''.join(body)}</main>"
            f"<script id='llm-data' type='application/json'>{payload}</script>"
            f"<script>{COPY_SCRIPT}</script></body></html>\n")


def write_atomic(path, text):
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def stamped_digest(view):
    text = Path(view).read_bytes().decode("utf-8", "replace")
    match = re.search(rf"<meta name='{STAMP}' content='([0-9a-f]{{64}})'>", text)
    return match[1] if match else None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check")
    check.add_argument("run_dir")
    check.add_argument("--view")
    render = sub.add_parser("render")
    render.add_argument("run_dir")
    render.add_argument("--out", required=True)
    render.add_argument("--lang", choices=sorted(LABELS), default="en")
    args = parser.parse_args(argv)
    try:
        record, sources = load_record(args.run_dir)
        digest = source_digest(sources)
        if args.command == "check":
            if args.view and stamped_digest(args.view) != digest:
                raise RecordError(f"{args.view}: rendered from different sources; render it again")
            print(f"ok: {len(record['docs'])} phase document(s), "
                  f"{len(record['visuals'].get('mocks', []))} mock(s), "
                  f"{len(record['visuals'].get('diagrams', []))} diagram(s)")
            return 0
        out, run_dir = Path(args.out).resolve(), Path(args.run_dir).resolve()
        if out == run_dir or run_dir in out.parents:
            raise RecordError("--out must be outside the run directory; the record's layout is closed")
        out.mkdir(parents=True, exist_ok=True)
        target = out / "run.html"
        if target.is_symlink() or (target.exists() and not target.is_file()):
            raise RecordError(f"refusing to write {target}: symlink or non-regular file")
        write_atomic(target, render_page(record, digest, args.lang))
        print(f"wrote {target} ({digest[:12]})")
        return 0
    except (RecordError, OSError) as e:
        print(f"visuals.py: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
