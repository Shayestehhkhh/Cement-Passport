"""Automated checks of the illustrative DCP pilot. Run with:  python -m unittest discover -s tests -v"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from generate_qr import make_qr, make_summary_qr  # noqa: E402
from render_passport import render  # noqa: E402
from passport_report import ROLES, a1_a3_total, view  # noqa: E402
from simulate_a3_update import apply_a3_update, demo, message_schema  # noqa: E402
from validate_passport import cas_check_digit_ok, load_schema, validate_record  # noqa: E402


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


class SchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = load_schema()  # also checks the schema against the JSON Schema meta-schema
        cls.valid = load(ROOT / "examples" / "batch-valid.json")
        cls.expected = load(ROOT / "examples" / "expected_rejections.json")

    def test_valid_record_is_accepted(self):
        self.assertEqual(validate_record(self.valid, self.schema), [])

    def test_every_invalid_record_is_rejected_at_the_expected_location(self):
        files = sorted(p.name for p in (ROOT / "examples" / "invalid").glob("*.json"))
        self.assertEqual(files, sorted(self.expected))
        for name, exp in self.expected.items():
            with self.subTest(record=name):
                problems = validate_record(load(ROOT / "examples" / "invalid" / name), self.schema)
                self.assertTrue(problems, f"{name} was accepted")
                self.assertIn(exp["expectedErrorLocation"], [loc for loc, _ in problems])

    def test_cas_check_digit(self):
        for cas in ("65997-16-2", "13397-24-5", "68131-74-8", "7732-18-5"):
            self.assertTrue(cas_check_digit_ok(cas), cas)
        self.assertFalse(cas_check_digit_ok("65997-16-3"))

    def test_every_en197_product_has_a_clinker_rule(self):
        products = self.schema["definitions"]["cementTypeEN197_1"]["enum"]
        self.assertEqual(len(products), 27)
        ruled = {r["if"]["properties"]["cementType"]["const"] for r in self.schema["properties"]["composition"]["allOf"]}
        self.assertEqual(ruled, set(products))


class QrTests(unittest.TestCase):
    def test_qr_encodes_only_the_passport_uri(self):
        record = load(ROOT / "examples" / "batch-valid.json")
        with tempfile.TemporaryDirectory() as tmp:
            path, content = make_qr(record, tmp)
            self.assertTrue(path.exists() and path.stat().st_size > 0)
            self.assertEqual(content, record["passportURI"])
            try:  # optional round trip if OpenCV happens to be installed
                import cv2
            except ImportError:
                return
            decoded, _, _ = cv2.QRCodeDetector().detectAndDecode(cv2.imread(str(path)))
            self.assertEqual(decoded, record["passportURI"])

    def test_summary_qr_shows_the_cement_data(self):
        record = load(ROOT / "examples" / "batch-valid.json")
        with tempfile.TemporaryDirectory() as tmp:
            path, content = make_summary_qr(record, tmp)
            for expected in (record["batchID"], record["composition"]["cementType"],
                             record["composition"]["strengthClass"], "synthetic"):
                self.assertIn(expected, content)
            try:
                import cv2
            except ImportError:
                return
            decoded, _, _ = cv2.QRCodeDetector().detectAndDecode(cv2.imread(str(path)))
            self.assertEqual(decoded, content)

    def test_passport_page_contains_the_cement_data(self):
        record = load(ROOT / "examples" / "batch-valid.json")
        with tempfile.TemporaryDirectory() as tmp:
            page = render(record, tmp).read_text(encoding="utf-8")
            for expected in (record["batchID"], "CEM II/B-V", "42.5N", "Synthetic example", "65997-16-2"):
                self.assertIn(expected, page)

    def test_invalid_record_gets_no_qr(self):
        record = load(ROOT / "examples" / "invalid" / "01-chromium-vi-above-limit.json")
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(ValueError):
            make_qr(record, tmp)


class ViewAndUpdateTests(unittest.TestCase):
    def setUp(self):
        self.record = load(ROOT / "examples" / "batch-valid.json")

    def test_views_are_nested_and_public_view_hides_composition(self):
        sizes = [len(view(self.record, r)) for r in ROLES]
        self.assertEqual(sizes, sorted(sizes))
        self.assertNotIn("constituents", view(self.record, "public"))
        self.assertIn("constituents", view(self.record, "auditor"))

    def test_a1_a3_total_is_sum_of_modules(self):
        entries = self.record["lcaIndicators"]["indicatorsPerModule"]
        expected = sum(e["gwpTotal"] for e in entries if e["module"] in ("A1", "A2", "A3"))
        self.assertAlmostEqual(a1_a3_total(entries), expected)

    def test_a3_update_accepts_valid_and_discards_invalid_messages(self):
        outcomes = {label: problems for label, _, _, problems in demo(ROOT / "examples" / "batch-valid.json")}
        self.assertEqual(outcomes["valid message"], [])
        self.assertTrue(outcomes["negative energy value"])
        self.assertTrue(outcomes["wrong batchID"])

    def test_a3_update_does_not_modify_the_input(self):
        before = json.dumps(self.record, sort_keys=True)
        apply_a3_update(self.record, {"batchID": self.record["batchID"], "module": "A3",
                                      "indicators": {"gwpTotal": 1.0}})
        self.assertEqual(before, json.dumps(self.record, sort_keys=True))


class CrossLayerConsistencyTests(unittest.TestCase):
    """The semantic model (TTL), the JSON Schema and the AsyncAPI payload must agree."""

    @staticmethod
    def schema_keys(node, acc):
        if isinstance(node, dict):
            for k, v in node.get("properties", {}).items():
                acc.add(k)
                CrossLayerConsistencyTests.schema_keys(v, acc)
            for v in node.values():
                if isinstance(v, (dict, list)):
                    CrossLayerConsistencyTests.schema_keys(v, acc)
        elif isinstance(node, list):
            for v in node:
                CrossLayerConsistencyTests.schema_keys(v, acc)
        return acc

    def test_ttl_properties_match_schema_fields(self):
        try:
            import rdflib
        except ImportError:
            self.skipTest("rdflib not installed (optional)")
        g = rdflib.Graph().parse(ROOT / "model" / "CementPassport.ttl", format="turtle")
        samm = rdflib.Namespace("urn:samm:org.eclipse.esmf.samm:meta-model:2.1.0#")
        names = set()
        for prop in g.subjects(rdflib.RDF.type, samm.Property):
            names.add(str(prop).split("#")[1])
        for bnode, payload in g.subject_objects(samm.payloadName):
            names.discard(str(g.value(bnode, samm.property)).split("#")[1])
            names.add(str(payload))
        keys = self.schema_keys(load_schema(), set())
        self.assertEqual(names, keys)

    def test_listing1_excerpt_is_an_exact_subset_of_the_schema(self):
        """The abridged excerpt printed in the article must not differ from the full schema."""
        excerpt = load(ROOT / "schema" / "listing1_excerpt.json")
        full = load_schema()

        def check(a, b, path):
            if isinstance(a, dict):
                self.assertIsInstance(b, dict, path)
                for k, v in a.items():
                    if k != "description":
                        self.assertIn(k, b, f"{path}/{k}")
                        check(v, b[k], f"{path}/{k}")
            elif isinstance(a, list) and path.endswith(("allOf", "required")):
                for item in a:
                    self.assertIn(item, b, path)
            else:
                self.assertEqual(a, b, path)

        check(excerpt, full, "")

    def test_asyncapi_payload_matches_message_schema(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not installed (optional)")
        doc = yaml.safe_load((ROOT / "api" / "dcp-asyncapi.yaml").read_text(encoding="utf-8"))
        payload = doc["components"]["messages"]["a3Update"]["payload"]
        generated = message_schema(load_schema())
        strip = lambda d: json.loads(json.dumps(d), object_hook=lambda o: {k: v for k, v in o.items() if k != "description"})
        self.assertEqual(strip(payload), strip(generated))
        example = doc["components"]["messages"]["a3Update"]["examples"][0]["payload"]
        record = load(ROOT / "examples" / "batch-valid.json")
        self.assertEqual(apply_a3_update(record, example)[1], [])


if __name__ == "__main__":
    unittest.main()
