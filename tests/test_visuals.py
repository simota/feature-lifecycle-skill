"""scripts/visuals.py against examples/sample-run: what check refuses, what render draws."""

import contextlib
import copy
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SAMPLE = REPO / "examples" / "sample-run"
sys.path.insert(0, str(REPO / "skills" / "feature-lifecycle" / "scripts"))
import visuals  # noqa: E402

_main = visuals.main


def _quiet_main(argv):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return _main(argv)


visuals.main = _quiet_main


class RunCopy(unittest.TestCase):
    """Each test works on its own copy of the sample record."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.run = self.tmp / "2026-08-22-checkout-guest-flow"
        shutil.copytree(SAMPLE, self.run)
        self.out = self.tmp / "view"

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def visuals(self):
        return json.loads((self.run / "artifacts" / "visuals.json").read_text())

    def write_visuals(self, data):
        (self.run / "artifacts" / "visuals.json").write_text(json.dumps(data))

    def refused(self, fragment):
        with self.assertRaises(visuals.RecordError) as caught:
            visuals.load_record(self.run)
        self.assertIn(fragment, str(caught.exception))


class Check(RunCopy):
    def test_sample_is_valid(self):
        record, sources = visuals.load_record(self.run)
        self.assertEqual([d["num"] for d in record["docs"]], ["01", "02", "03", "04", "05"])
        self.assertIn("artifacts/visuals.json", sources)

    def test_envelope_lists_and_flow_maps(self):
        record, _ = visuals.load_record(self.run)
        design = next(d for d in record["docs"] if d["num"] == "05")["fields"]
        self.assertEqual(design["engines"][1], {"role": "breadth", "cli": "agy"})
        self.assertEqual(design["spawns"], "12")

    def test_refuses_unknown_gate(self):
        path = self.run / "04-spec.md"
        path.write_text(path.read_text().replace("gate: pass", "gate: maybe", 1))
        self.refused("gate: expected one of")

    def test_refuses_sealed_document_without_gate(self):
        path = self.run / "03-verdict.md"
        path.write_text(path.read_text().split("## Gate")[0])
        self.refused("carries a ## Gate section")

    def test_refuses_two_documents_for_one_phase(self):
        shutil.copy(self.run / "02-ideate.md", self.run / "02-ideate-again.md")
        self.refused("one document per phase")

    def test_refuses_script_in_mock(self):
        data = self.visuals()
        data["mocks"][0]["after"]["html"] += "<script>alert(1)</script>"
        self.write_visuals(data)
        self.refused("<script>")

    def test_refuses_outside_css_reference(self):
        for css in ("a{background:url(https://x.test/a.png)}", "a{background:u\\72l(//x.test)}",
                    "@import 'x.css';"):
            data = self.visuals()
            data["mocks"][2]["css"] = css
            self.write_visuals(data)
            self.refused("not allowed")

    def test_allows_data_and_fragment_references(self):
        data = self.visuals()
        data["mocks"][2]["css"] += "i{background:url('data:image/png;base64,AA==')}"
        data["mocks"][2]["after"]["html"] += "<a href='#top'>top</a>"
        self.write_visuals(data)
        visuals.load_record(self.run)

    def test_refuses_alternative_without_caption(self):
        data = self.visuals()
        del data["mocks"][2]["alternatives"][0]["caption"]
        self.write_visuals(data)
        self.refused("alternatives[0].caption: required")

    def test_refuses_five_alternatives(self):
        data = self.visuals()
        data["mocks"][2]["alternatives"] *= 5
        self.write_visuals(data)
        self.refused("1 to 4 screens")

    def test_refuses_edge_to_unknown_node(self):
        data = self.visuals()
        data["diagrams"][0]["edges"].append({"from": "orders", "to": "nowhere"})
        self.write_visuals(data)
        self.refused("expected a node id of this diagram")

    def test_refuses_repeated_id_across_kinds(self):
        data = self.visuals()
        data["diagrams"][0]["id"] = "D-01"
        data["diagrams"].append(copy.deepcopy(data["diagrams"][0]))
        self.write_visuals(data)
        self.refused("D-01 is repeated")

    def test_refuses_visual_for_a_phase_that_did_not_run(self):
        (self.run / "02-ideate.md").unlink()
        self.refused("phase P2 has no document")


class ReviewFindings(RunCopy):
    """Regressions for the PDCA review: each input once crashed or slipped through."""

    def edit(self, name, old, new):
        path = self.run / name
        text = path.read_text()
        self.assertIn(old, text)
        path.write_text(text.replace(old, new, 1))

    def test_refuses_markup_hidden_in_raw_text_inside_svg(self):
        for tag in ("xmp", "textarea", "title", "noembed", "noframes", "noscript", "plaintext"):
            data = self.visuals()
            data["mocks"][2]["after"]["html"] = f"<svg><{tag}><image href='https://e/x'/></{tag}></svg>"
            self.write_visuals(data)
            self.refused("not allowed")

    def test_refuses_character_references_in_foreign_style(self):
        data = self.visuals()
        data["mocks"][2]["after"]["html"] = "<svg><style>&#64;import 'https://e/a.css';</style></svg>"
        self.write_visuals(data)
        self.refused("not allowed")

    def test_refuses_font_face(self):
        data = self.visuals()
        data["mocks"][2]["css"] = "@font-face{font-family:x;src:url(data:font/woff2;base64,AA)}"
        self.write_visuals(data)
        self.refused("@font-face")

    def test_refuses_acs_on_a_p2_visual(self):
        data = self.visuals()
        data["mocks"][0]["acs"] = ["AC-01"]
        self.write_visuals(data)
        self.refused("before acceptance criteria exist")

    def test_refuses_unknown_run_status(self):
        self.edit("RUN.md", "aborted-at-P6", "nonsense")
        self.refused("is not a run status")

    def test_refuses_phase_field_that_disagrees_with_the_file(self):
        self.edit("04-spec.md", "phase: P4_SPEC", "phase: P5_DESIGN")
        self.refused("expected P4")

    def test_refuses_structured_consumes(self):
        self.edit("04-spec.md", "consumes: [03-verdict.md, artifacts/scope-boundary.md]",
                  "consumes: [{path: a.md, why: x}]")
        self.refused("expected a list of paths")

    def test_refuses_list_as_flow_map_key(self):
        self.edit("04-spec.md", "engines: [{ role: hub, cli: claude-code }, { role: judge, cli: claude-code }]",
                  "engines: [{[a]: b}]")
        self.refused("must be a scalar")

    def test_refuses_unclosed_bracket_instead_of_swallowing_fields(self):
        self.edit("04-spec.md", "spawns: 2", "note: [see 1\nspawns: 2")
        self.refused("not closed before spawns")

    def test_bracket_in_quotes_does_not_open_a_value(self):
        self.edit("04-spec.md", "spawns: 2", "note: \"see [1\"\nspawns: 2")
        record, _ = visuals.load_record(self.run)
        spec = next(d for d in record["docs"] if d["num"] == "04")["fields"]
        self.assertEqual(spec["spawns"], "2")

    def test_renders_a_record_with_no_phase_documents(self):
        for doc in self.run.glob("0*.md"):
            doc.unlink()
        (self.run / "artifacts" / "visuals.json").unlink()
        self.assertEqual(visuals.main(["render", str(self.run), "--out", str(self.out)]), 0)

    def test_renders_a_table_of_separators_only(self):
        self.edit("03-verdict.md", "## Findings\n", "## Findings\n|---|---|\n\n")
        self.assertEqual(visuals.main(["render", str(self.run), "--out", str(self.out)]), 0)

    def test_check_view_on_a_binary_file_exits_2(self):
        blob = self.tmp / "blob.html"
        blob.write_bytes(b"\xff\xfe\x00")
        self.assertEqual(visuals.main(["check", str(self.run), "--view", str(blob)]), 2)

    def test_resume_value_continues_on_indented_lines(self):
        # the shape reference/run-record.md § What `resume` Reads shows for **Re-bind:**
        self.edit("RUN.md", "artifacts/scope-boundary.md, artifacts/visuals.json",
                  "artifacts/scope-boundary.md,\n             artifacts/visuals.json")
        record, _ = visuals.load_record(self.run)
        resume = dict(next(ps for name, ps, _ in record["run"]["sections"] if name == "Resume"))
        self.assertTrue(resume["Re-bind"].endswith("artifacts/scope-boundary.md, artifacts/visuals.json"))
        self.assertEqual(resume["Stopped because"], "budget ceiling reached before the loop contract was handed over")

    def test_indented_line_under_the_header_leaves_status_alone(self):
        self.edit("RUN.md", "**Status:** aborted-at-P6\n", "**Status:** aborted-at-P6\n    (resumable; see Resume)\n")
        record, _ = visuals.load_record(self.run)
        self.assertEqual(dict(record["run"]["header"])["Status"], "aborted-at-P6")

    def test_continuation_stops_at_a_key_a_list_item_or_a_blank_line(self):
        self.edit("RUN.md", "**Re-bind:** artifacts/acceptance-criteria.md, artifacts/scope-boundary.md, "
                  "artifacts/visuals.json\n**Stopped because:**",
                  "**Re-bind:** a,\n   **Next:** P6\n**Blockers:**\n  - one\n**Stopped because:** x\n   \n   y\n**Z:**")
        record, _ = visuals.load_record(self.run)
        resume = next(ps for name, ps, _ in record["run"]["sections"] if name == "Resume")
        self.assertEqual(dict(resume)["Re-bind"], "a,")
        self.assertEqual(dict(resume)["Next"], "P6")
        self.assertEqual(dict(resume)["Blockers"], "")
        self.assertEqual(dict(resume)["Stopped because"], "x")

    def test_refuses_an_ac_the_criteria_do_not_define(self):
        data = self.visuals()
        next(m for m in data["mocks"] if m["phase"] == "P5")["acs"] = ["AC-01", "AC-99"]
        self.write_visuals(data)
        self.refused("AC-99 not in artifacts/acceptance-criteria.md")

    def test_ac_ids_are_checked_for_shape_even_without_the_criteria_file(self):
        (self.run / "artifacts" / "acceptance-criteria.md").unlink()
        data = self.visuals()
        mock = next(m for m in data["mocks"] if m["phase"] == "P5")
        mock["acs"] = ["AC-99"]
        self.write_visuals(data)
        visuals.load_record(self.run)  # no file to cross-check against
        mock["acs"] = ["bogus"]
        self.write_visuals(data)
        self.refused("expected AC ids such as AC-01")

    def test_non_string_edge_end_exits_2(self):
        data = self.visuals()
        data["diagrams"][0]["edges"][0]["from"] = ["orders"]
        self.write_visuals(data)
        self.refused("expected a node id of this diagram")
        self.assertEqual(visuals.main(["check", str(self.run)]), 2)

    def test_fence_table_or_heading_ends_a_list(self):
        page = visuals.md_html("- a\n```\nx\n```\n- b\n| h |\n|---|\n| c |\n- d\n## e")
        self.assertEqual(page, "<ul><li>a</li></ul><pre><code>x</code></pre><ul><li>b</li></ul>"
                               "<table><tr><th>h</th></tr><tr><td>c</td></tr></table><ul><li>d</li></ul><h4>e</h4>")

    def test_reads_a_record_checked_out_with_crlf_and_a_bom(self):
        # git's core.autocrlf on Windows writes every Markdown file this way
        for path in self.run.rglob("*"):
            if path.suffix in (".md", ".json"):
                path.write_bytes(b"\xef\xbb\xbf" + path.read_bytes().replace(b"\n", b"\r\n"))
        record, _ = visuals.load_record(self.run)
        self.assertEqual(dict(record["run"]["header"])["Status"], "aborted-at-P6")
        self.assertEqual(next(d for d in record["docs"] if d["num"] == "05")["fields"]["status"], "sealed")
        self.assertEqual(visuals.main(["render", str(self.run), "--out", str(self.out)]), 0)

    def test_a_gate_inside_a_tilde_or_longer_fence_is_not_a_gate(self):
        self.edit("03-verdict.md", "## Gate\n", "~~~\n## Gate\n")
        with open(self.run / "03-verdict.md", "a") as f:
            f.write("~~~\n")
        self.refused("03-verdict.md: a sealed document carries a ## Gate section")
        shutil.copy(SAMPLE / "03-verdict.md", self.run / "03-verdict.md")
        # a ``` line inside a ```` fence is text, not the fence's end
        self.edit("03-verdict.md", "## Gate\n", "````\n```\n## Gate\n")
        with open(self.run / "03-verdict.md", "a") as f:
            f.write("````\n")
        self.refused("03-verdict.md: a sealed document carries a ## Gate section")

    def test_fence_kinds_render_as_code(self):
        self.assertEqual(visuals.md_html("~~~\n## x\n| y |\n~~~\npara"),
                         "<pre><code>## x\n| y |</code></pre><p>para</p>")
        self.assertEqual(visuals.md_html("````md\n```\n- a\n```\n````"),
                         "<pre><code>```\n- a\n```</code></pre>")
        self.assertEqual(visuals.md_html("- a\n~~~\nb\n~~~"), "<ul><li>a</li></ul><pre><code>b</code></pre>")

    def test_envelope_closes_only_on_a_line_of_three_dashes(self):
        # before, "---more" closed the envelope and the fields after it silently became body
        with self.assertRaises(visuals.RecordError) as caught:
            visuals.parse_envelope("---\nrun: x\n---more\nphase: P1\n---\nbody", "f.md")
        self.assertIn("cannot read frontmatter line '---more'", str(caught.exception))
        self.assertEqual(visuals.parse_envelope("---\nrun: x\n--- \nbody\n", "f.md"), ({"run": "x"}, "body\n"))

    def test_link_with_parentheses_shows_only_its_text(self):
        self.assertEqual(visuals.md_inline("see [RFC](https://e.x/a_(b)) now"), "see RFC now")

    def test_link_scan_stays_fast_on_runs_of_brackets(self):
        start = __import__("time").monotonic()
        visuals.md_inline("[" * 20000 + "](" + "()" * 20000)
        self.assertLess(__import__("time").monotonic() - start, 2)

    def test_refuses_a_flow_value_left_open_at_the_end_of_the_envelope(self):
        # the key used to vanish without a word
        with self.assertRaises(visuals.RecordError) as caught:
            visuals.parse_envelope("---\nrun: x\nproduces: [a,\n  b\n---\nbody", "f.md")
        self.assertIn("produces: the flow value is not closed", str(caught.exception))


class DesignSelect(RunCopy):
    """The P5 Design Select step: whole candidate designs, one selected, the rest rejected with a reason."""

    def designs(self, change):
        data = self.visuals()
        change(data["designs"])
        self.write_visuals(data)

    def test_refuses_a_design_id_past_ds_d(self):
        self.designs(lambda ds: ds[1].update(id="DS-E"))
        self.refused("expected DS-A … DS-D")

    def test_refuses_two_selected(self):
        self.designs(lambda ds: ds[1].update(status="selected", selected_by="user"))
        self.refused("more than one design is selected")

    def test_refuses_rejected_without_reason(self):
        self.designs(lambda ds: ds[1].pop("reason"))
        self.refused("carries the reason it lost")

    def test_refuses_selected_beside_an_open_candidate(self):
        self.designs(lambda ds: ds[1].update(status="candidate"))
        self.refused("every other one is rejected")

    def test_refuses_selected_without_who_selected(self):
        self.designs(lambda ds: ds[0].pop("selected_by"))
        self.refused("selected_by")

    def test_refuses_a_p5_visual_outside_every_design(self):
        self.designs(lambda ds: ds[0]["mocks"].remove("M-04"))
        self.refused("M-04 belongs to no design")

    def test_refuses_a_p2_mock_in_a_design(self):
        self.designs(lambda ds: ds[1]["mocks"].append("M-01"))
        self.refused("M-01 is not a P5 mock or diagram")

    def test_refuses_a_visual_in_two_designs(self):
        self.designs(lambda ds: ds[1]["mocks"].append("M-03"))
        self.refused("already belongs to DS-A")

    def test_sealed_design_phase_requires_a_selection(self):
        self.designs(lambda ds: [d.update(status="candidate") for d in ds])
        self.refused("exactly one design is selected")

    def test_open_design_phase_shows_candidates_awaiting_selection(self):
        self.designs(lambda ds: [d.update(status="candidate") for d in ds])
        path = self.run / "05-design.md"
        path.write_text(path.read_text().replace("status: sealed", "status: open", 1))
        self.assertEqual(visuals.main(["render", str(self.run), "--out", str(self.out), "--lang", "en"]), 0)
        page = (self.out / "run.html").read_text()
        self.assertIn("Awaiting selection", page)
        self.assertNotIn("data-copy='DS-", page)

    def test_lone_selected_design_needs_the_reason_no_alternative_existed(self):
        data = self.visuals()
        data["designs"] = [data["designs"][0]]
        data["designs"][0]["mocks"] += ["M-05"]
        data["designs"][0]["diagrams"] += ["D-02"]
        data["designs"][0].pop("reason")
        self.write_visuals(data)
        self.refused("no alternative existed")

    def test_card_facts_are_computed_from_the_record(self):
        visuals.main(["render", str(self.run), "--out", str(self.out), "--lang", "en"])
        page = (self.out / "run.html").read_text()
        self.assertIn("<dd>4/4</dd>", page)
        self.assertIn("<dd>2/4 · not drawn: AC-03, AC-04</dd>", page)
        self.assertIn("<dd>new 3 · changed 4 · removed 1</dd>", page)

    def test_only_the_selected_design_is_handed_on_to_build(self):
        visuals.main(["render", str(self.run), "--out", str(self.out)])
        page = (self.out / "run.html").read_text()
        payload = json.loads(page.split("<script id='llm-data' type='application/json'>")[1].split("</script>")[0])
        self.assertEqual(sorted(payload["designs"]), ["DS-A"])
        self.assertIn("## M-03", payload["designs"]["DS-A"])
        self.assertIn("## M-04", payload["designs"]["DS-A"])
        self.assertNotIn("M-05", payload["items"])
        self.assertNotIn("data-copy='M-05'", page)


class Render(RunCopy):
    def render(self, *extra):
        return visuals.main(["render", str(self.run), "--out", str(self.out), *extra])

    def test_page_draws_every_part(self):
        self.assertEqual(self.render("--lang", "ja"), 0)
        page = (self.out / "run.html").read_text()
        for part in ("id='phases'", "id='flow'", "id='design'", "id='screens'", "id='documents'",
                     "id='M-03'", "id='D-01'", "id='select'", "id='DS-A'", "<svg", "sandbox", "未実行", "Re-entry 1"):
            self.assertIn(part, page)
        # the failed-then-passed design gate shows its re-entry on the phase card
        self.assertIn("1 再突入", page)

    def test_page_loads_nothing_and_allows_one_script(self):
        self.render()
        page = (self.out / "run.html").read_text()
        self.assertIn("default-src 'none'", page)
        self.assertEqual(page.count("<script>"), 1)

    def test_copy_payload_carries_markup_and_guardrails(self):
        self.render()
        page = (self.out / "run.html").read_text()
        payload = page.split("<script id='llm-data' type='application/json'>")[1].split("</script>")[0]
        items = json.loads(payload)["items"]
        self.assertEqual(sorted(items), ["M-01", "M-02", "M-03", "M-04"])
        self.assertIn("No pre-ticked marketing opt-in", items["M-03"])
        self.assertIn("```html", items["M-03"])
        self.assertIn("AC-01, AC-03", items["M-03"])

    def test_view_goes_stale_when_a_source_changes(self):
        self.render()
        view = str(self.out / "run.html")
        self.assertEqual(visuals.main(["check", str(self.run), "--view", view]), 0)
        with open(self.run / "04-spec.md", "a") as f:
            f.write("\nappended\n")
        self.assertEqual(visuals.main(["check", str(self.run), "--view", view]), 2)

    def test_refuses_output_inside_the_record(self):
        self.assertEqual(visuals.main(["render", str(self.run), "--out", str(self.run / "view")]), 2)
        self.assertFalse((self.run / "view").exists())

    def test_removed_and_new_parts_are_marked(self):
        self.render()
        page = (self.out / "run.html").read_text()
        self.assertIn("class='edge removed'", page)
        self.assertIn("class='node new component", page)


    def test_artifact_flow_marker_never_shares_an_id_with_a_diagram(self):
        data = self.visuals()
        data["diagrams"][0]["id"] = "D-00"
        for d in data["designs"]:
            d["diagrams"] = ["D-00" if v == "D-01" else v for v in d["diagrams"]]
        self.write_visuals(data)
        self.render()
        page = (self.out / "run.html").read_text()
        ids = __import__("re").findall(r"<marker id='([^']+)'", page)
        self.assertEqual(len(ids), len(set(ids)))


class Layout(unittest.TestCase):
    def test_cycle_still_ranks_every_node(self):
        nodes = [{"id": n} for n in "abc"]
        edges = [{"from": "a", "to": "b"}, {"from": "b", "to": "c"}, {"from": "c", "to": "a"}]
        layers = visuals.layout(nodes, edges)
        self.assertEqual(sorted(n for layer in layers.values() for n in layer), ["a", "b", "c"])
        self.assertEqual(layers[0], ["a"])

    def test_wrap_cuts_a_word_longer_than_a_line(self):
        lines = visuals._wrap("src/checkout/guest/GuestOrderTokenService.ts", limit=26)
        self.assertTrue(all(len(line) <= 26 for line in lines))
        self.assertEqual("".join(lines), "src/checkout/guest/GuestOrderTokenService.ts")

    def test_back_edges_get_their_own_lanes_and_labels_sit_on_top(self):
        diagram = {"id": "D-01", "title": "t", "nodes": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
                   "edges": [{"from": "a", "to": "b", "label": "reads"}, {"from": "b", "to": "a", "label": "writes"}]}
        svg = visuals.render_diagram(diagram, visuals.LABELS["en"])
        reads = svg.index(">reads<")
        writes = svg.index(">writes<")
        self.assertGreater(min(reads, writes), svg.rindex("<g>"))
        ys = [float(v) for v in __import__("re").findall(r"<text x='[0-9.]+' y='([0-9.]+)' text-anchor='middle'>(?:reads|writes)<", svg)]
        self.assertEqual(len(set(ys)), 2)

    def test_wrap_counts_cjk_as_two_columns(self):
        self.assertEqual(visuals._wrap("あ" * 20, limit=10), ["あ" * 5] * 4)


if __name__ == "__main__":
    unittest.main()
