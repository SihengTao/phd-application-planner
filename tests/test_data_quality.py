import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from assets import check_data, data_quality
from assets.data_quality import advisor_id, program_id, validate_result


def _source(source_id="official-funding", claim_paths=None):
    return {
        "id": source_id,
        "url": "https://example.edu/graduate/funding",
        "title": "Graduate funding",
        "publisher": "Example University",
        "sourceType": "official_program",
        "official": True,
        "accessedAt": "2026-07-20",
        "effectiveCycle": "2027",
        "retrievalStatus": "retrieved",
        "claimPaths": claim_paths or [],
    }


def _valid_program():
    funding = _source(
        claim_paths=[
            "facts.stipendUSD",
            "facts.stipendCurrency",
            "facts.meetsFloor",
            "facts.applicationPolicy",
        ]
    )
    food_source = {
        **_source("food-source"),
        "url": "https://example.com/restaurant",
        "title": "Restaurant listing",
        "publisher": "Restaurant",
        "sourceType": "restaurant",
        "official": False,
        "claimPaths": ["nearbyFood.restaurants[0]"],
    }
    return {
        "region": "US",
        "school": "Example University",
        "program": "History PhD",
        "city": "Example City",
        "facts": {
            "stipendUSD": 42000,
            "stipendCurrency": "USD",
            "stipend_foundOfficial": True,
            "meetsFloor": True,
            "applicationPolicy": "multiple_allowed",
            "sources": [funding],
            "claimChecks": [
                {
                    "claimPath": "facts.stipendUSD",
                    "status": "confirmed",
                    "sourceIds": ["official-funding"],
                    "initialValue": 42000,
                    "finalValue": 42000,
                    "checkedAt": "2026-07-20",
                    "conflict": False,
                    "resolution": "Official page agrees.",
                },
                {
                    "claimPath": "facts.meetsFloor",
                    "status": "confirmed",
                    "sourceIds": ["official-funding"],
                    "initialValue": True,
                    "finalValue": True,
                    "checkedAt": "2026-07-20",
                    "conflict": False,
                    "resolution": "Amount exceeds the floor.",
                },
                {
                    "claimPath": "facts.applicationPolicy",
                    "status": "confirmed",
                    "sourceIds": ["official-funding"],
                    "initialValue": "multiple_allowed",
                    "finalValue": "multiple_allowed",
                    "checkedAt": "2026-07-20",
                    "conflict": False,
                    "resolution": "Current policy agrees.",
                },
            ],
        },
        "faculty": {
            "faculty": [
                {
                    "name": "Alex Example",
                    "hIndex": None,
                    "citations": None,
                    "url": "https://example.edu/faculty/alex",
                }
            ]
        },
        "outcomes": {},
        "nearbyFood": {
            "enabled": True,
            "researchStatus": "complete",
            "campusAnchor": {"name": "Main campus", "address": "1 College Ave"},
            "sources": [food_source],
            "restaurants": [
                {
                    "name": "Spicy Garden",
                    "cuisine": "川菜",
                    "address": "2 College Ave",
                    "url": "https://example.com/restaurant",
                    "sourceIds": ["food-source"],
                    "lastVerified": "2026-07-20",
                }
            ],
        },
        "verification": {
            "status": "confirmed",
            "checkedAt": "2026-07-20",
            "conflict": False,
            "initial": {
                "stipendUSD": 42000,
                "meetsFloor": True,
                "applicationPolicy": "multiple_allowed",
            },
            "final": {
                "stipendUSD": 42000,
                "meetsFloor": True,
                "applicationPolicy": "multiple_allowed",
            },
        },
    }


def _valid_result():
    return {
        "schemaVersion": "2.0",
        "generatedAt": "2026-07-20T12:00:00Z",
        "field": "History",
        "regions": [{"key": "US", "label": "United States"}],
        "floor": 35000,
        "currency": "USD",
        "programs": [_valid_program()],
    }


class StableIdTests(unittest.TestCase):
    def test_program_id_is_stable_and_normalized(self):
        first = program_id("US", " Example University ", "History PhD")
        second = program_id("us", "example university", "HISTORY PHD")
        self.assertEqual(first, second)
        self.assertEqual(first, "program_1d6ddfa298189e3d")
        self.assertEqual(
            advisor_id(first, "Alex Li"), "advisor_386bd873824eaf4c"
        )
        self.assertNotEqual(first, program_id("US", "Other", "History PhD"))

    def test_advisor_id_is_program_scoped(self):
        p1 = program_id("US", "A", "History")
        p2 = program_id("US", "B", "History")
        self.assertEqual(advisor_id(p1, "Alex Li"), advisor_id(p1, " alex li "))
        self.assertNotEqual(advisor_id(p1, "Alex Li"), advisor_id(p1, "Alex  Li"))
        self.assertNotEqual(advisor_id(p1, "Alex Li"), advisor_id(p2, "Alex Li"))


class ValidationTests(unittest.TestCase):
    def test_valid_v2_result_has_no_errors(self):
        report = validate_result(_valid_result())
        self.assertTrue(report["valid"])
        self.assertEqual(report["summary"]["errors"], 0)
        self.assertEqual(report["summary"]["programs"], 1)
        self.assertEqual(report["summary"]["advisors"], 1)
        self.assertEqual(report["summary"]["restaurants"], 1)
        self.assertIn("issues", report)

    def test_legacy_list_is_accepted_with_warnings_not_structural_errors(self):
        program = {
            "region": "US",
            "school": "Legacy University",
            "program": "Biology PhD",
            "city": "Town",
            "facts": {
                "stipendUSD": -1,
                "stipend_foundOfficial": False,
                "meetsFloor": False,
                "applicationRestrictions": "Unknown",
                "sources": ["https://example.edu/program"],
            },
            "pis": {"pis": [{"name": "Professor Example", "hIndex": -1}]},
            "out": {},
        }
        report = validate_result([program])
        self.assertTrue(report["valid"])
        self.assertEqual(report["summary"]["errors"], 0)
        codes = {issue["code"] for issue in report["issues"]}
        self.assertIn("legacy_top_level_list", codes)
        self.assertIn("source_legacy_unstructured", codes)
        self.assertIn("stipend_legacy_sentinel", codes)

    def test_detects_duplicates_invalid_policy_types_and_floor_conflict(self):
        result = _valid_result()
        result["programs"].append(json.loads(json.dumps(result["programs"][0])))
        facts = result["programs"][0]["facts"]
        facts["applicationPolicy"] = "sometimes"
        facts["meetsFloor"] = "yes"
        facts["stipend_foundOfficial"] = "true"
        report = validate_result(result)
        codes = {issue["code"] for issue in report["errors"]}
        self.assertIn("program_duplicate", codes)
        self.assertIn("application_policy_invalid", codes)
        self.assertIn("boolean_invalid", codes)
        self.assertFalse(report["valid"])

    def test_detects_bad_url_missing_claim_reference_and_restaurant_date(self):
        result = _valid_result()
        program = result["programs"][0]
        program["facts"]["sources"][0]["url"] = "example.edu/no-scheme"
        program["facts"]["claimChecks"][0]["sourceIds"] = ["missing"]
        restaurant = program["nearbyFood"]["restaurants"][0]
        restaurant.pop("lastVerified")
        restaurant["sourceIds"] = ["unknown-food"]
        report = validate_result(result)
        codes = {issue["code"] for issue in report["issues"]}
        self.assertIn("url_invalid", codes)
        self.assertIn("source_reference_missing", codes)
        self.assertIn("restaurant_date_missing", codes)

    def test_detects_verification_conflicts(self):
        result = _valid_result()
        verification = result["programs"][0]["verification"]
        verification["conflict"] = True
        verification["final"]["stipendUSD"] = 41000
        report = validate_result(result)
        codes = {issue["code"] for issue in report["errors"]}
        self.assertIn("verification_status_conflict", codes)
        self.assertIn("verification_confirmed_but_changed", codes)

    def test_terminal_reconciliation_conflict_supersedes_historical_confirmation(self):
        result = _valid_result()
        program = result["programs"][0]
        historical = {
            "claimPath": "facts.applicationPolicy",
            "status": "confirmed",
            "initialValue": "multiple_allowed",
            "finalValue": "multiple_allowed",
            "sourceIds": ["official-funding"],
            "checkedAt": "2026-07-20T12:00:00Z",
            "conflict": False,
            "resolution": "First pass appeared consistent.",
        }
        terminal = {
            "claimPath": "facts.applicationPolicy",
            "status": "conflict",
            "initialValue": "multiple_allowed",
            "independentValue": "single_only",
            "finalValue": "conflict",
            "sourceIds": ["official-funding"],
            "checkedAt": "2026-07-20T13:00:00Z",
            "conflict": True,
            "resolution": "Applicable official pages disagree.",
        }
        program["facts"]["applicationPolicy"] = "conflict"
        program["provenance"] = {
            "sources": copy.deepcopy(program["facts"]["sources"]),
            "checks": [historical, terminal],
            "conflicts": [
                {
                    "claimPath": "facts.applicationPolicy",
                    "status": "open",
                    "sourceIds": ["official-funding"],
                }
            ],
            "errors": [],
        }
        program["verification"] = {
            **program["verification"],
            "status": "conflict",
            "conflict": True,
            "final": {
                **program["verification"]["final"],
                "applicationPolicy": "conflict",
            },
        }
        report = validate_result(result)
        codes = {issue["code"] for issue in report["errors"]}
        self.assertNotIn("verification_conflicts_unresolved", codes)

    def test_alias_source_and_check_records_are_counted_once(self):
        result = _valid_result()
        program = result["programs"][0]
        program["provenance"] = {
            "sources": copy.deepcopy(program["facts"]["sources"]),
            "checks": copy.deepcopy(program["facts"]["claimChecks"]),
            "conflicts": [],
            "errors": [],
        }
        report = validate_result(result)
        self.assertEqual(report["summary"]["sources"], 2)
        self.assertEqual(report["summary"]["claims"], 3)

    def test_future_date_allows_five_minutes_of_clock_skew(self):
        validator = data_quality._Validator()
        validator._now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        validator.check_date("2026-07-27T12:04:59Z", "$.date")
        self.assertNotIn(
            "date_in_future", {issue["code"] for issue in validator.issues}
        )
        validator.check_date("2026-07-27T12:05:01Z", "$.later")
        self.assertIn(
            "date_in_future", {issue["code"] for issue in validator.issues}
        )

    def test_online_check_skips_dns_resolving_to_private_address(self):
        with mock.patch.object(
            data_quality.socket,
            "getaddrinfo",
            return_value=[
                (
                    data_quality.socket.AF_INET,
                    data_quality.socket.SOCK_STREAM,
                    6,
                    "",
                    ("127.0.0.1", 443),
                )
            ],
        ), mock.patch.object(data_quality, "build_opener") as opener:
            report = validate_result(_valid_result(), online=True)
        self.assertIn(
            "url_unsafe_skipped", {issue["code"] for issue in report["warnings"]}
        )
        opener.assert_not_called()

    def test_redirect_handler_rejects_private_destination(self):
        handler = data_quality._PublicOnlyRedirectHandler(
            data_quality.time.monotonic() + 5
        )
        with self.assertRaises(data_quality.URLError):
            handler.redirect_request(
                data_quality.Request("https://example.edu"),
                None,
                302,
                "Found",
                {},
                "http://127.0.0.1/private",
            )

    def test_online_url_count_is_capped(self):
        validator = data_quality._Validator(online=True)
        validator.urls = {
            "https://{}.example.org".format(index): "$.sources[{}]".format(index)
            for index in range(data_quality.MAX_ONLINE_URLS + 7)
        }
        with mock.patch.object(
            data_quality,
            "_check_url_online",
            return_value=(True, 200, ""),
        ) as checker:
            validator.check_online_urls()
        self.assertEqual(checker.call_count, data_quality.MAX_ONLINE_URLS)
        self.assertIn(
            "url_check_limit", {issue["code"] for issue in validator.issues}
        )

    def test_faculty_mode_reports_eight_grouped_hss_coverage_warnings(self):
        result = _valid_result()
        result["discipline_mode"] = "faculty_based"
        result["disciplineMode"] = "faculty_based"
        report = validate_result(result)
        hss_issues = [
            issue
            for issue in report["warnings"]
            if issue["code"] == "hss_coverage_missing"
        ]
        self.assertEqual(len(hss_issues), 8)
        self.assertEqual(
            {
                issue["details"]["coverage"]
                for issue in hss_issues
            },
            {
                "advising_admissions_model",
                "writing_sample",
                "language",
                "methods_theory",
                "field_qualifying_exam",
                "teaching",
                "dissertation_fieldwork_support",
                "placement_time_to_degree",
            },
        )

    def test_hss_aliases_satisfy_grouped_coverage(self):
        result = _valid_result()
        result["discipline_mode"] = "hybrid"
        facts = result["programs"][0]["facts"]
        facts.update(
            {
                "facultyModel": "central admissions",
                "advisorAssignment": "after year one",
                "writingSample": "20 pages",
                "languageRequirements": "two research languages",
                "methodsTraining": "theory and methods seminar",
                "fieldRequirements": "two field exams",
                "teachingLoad": "two terms",
                "dissertationFormat": "monograph",
                "archiveFieldworkSupport": "competitive travel grants",
            }
        )
        result["programs"][0]["outcomes"] = {
            "placement": "Published placement list",
            "timeToDegree": "6 years",
        }
        report = validate_result(result)
        self.assertNotIn(
            "hss_coverage_missing",
            {issue["code"] for issue in report["warnings"]},
        )

    def test_nearby_food_enabled_status_must_be_consistent(self):
        cases = [
            (False, "complete", True),
            (True, "not_requested", True),
            (False, "not_requested", False),
            (True, "partial", False),
        ]
        for enabled, status, should_error in cases:
            with self.subTest(enabled=enabled, status=status):
                result = _valid_result()
                nearby_food = result["programs"][0]["nearbyFood"]
                nearby_food["enabled"] = enabled
                nearby_food["researchStatus"] = status
                if not enabled:
                    nearby_food["restaurants"] = []
                report = validate_result(result)
                codes = {issue["code"] for issue in report["errors"]}
                self.assertEqual(
                    "nearby_food_status_inconsistent" in codes,
                    should_error,
                )

    def test_online_is_off_by_default(self):
        report = validate_result(_valid_result())
        self.assertFalse(report["summary"]["online"])
        self.assertNotIn(
            "url_reachable", {issue["code"] for issue in report["issues"]}
        )

    def test_input_is_not_mutated(self):
        data = _valid_result()
        before = json.dumps(data, ensure_ascii=False, sort_keys=True)
        validate_result(data)
        after = json.dumps(data, ensure_ascii=False, sort_keys=True)
        self.assertEqual(before, after)


class CliTests(unittest.TestCase):
    def test_cli_writes_report_and_strict_fails_on_warning(self):
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "result.json"
            output_path = Path(directory) / "report.json"
            input_path.write_text(
                json.dumps([], ensure_ascii=False), encoding="utf-8"
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    str(repo / "assets" / "check_data.py"),
                    str(input_path),
                    "--strict",
                    "--output",
                    str(output_path),
                ],
                cwd=repo,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 1)
            report = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertGreater(report["summary"]["warnings"], 0)
            self.assertEqual(report["summary"]["errors"], 0)
            self.assertTrue(report["gate"]["strict"])
            self.assertFalse(report["gate"]["passed"])
            self.assertTrue(report["ok"])

    def test_cli_bad_json_returns_two_with_json_report(self):
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "bad.json"
            input_path.write_text("{bad", encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(repo / "assets" / "check_data.py"),
                    str(input_path),
                ],
                cwd=repo,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 2)
            report = json.loads(completed.stdout)
            self.assertEqual(report["errors"][0]["code"], "input_error")
            self.assertFalse(report["gate"]["passed"])

    def test_report_file_replacement_is_atomic_and_cleans_temp_on_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "report.json"
            output_path.write_text('{"old": true}\n', encoding="utf-8")
            with mock.patch.object(
                check_data.os, "replace", side_effect=OSError("replace failed")
            ):
                with self.assertRaises(OSError):
                    check_data._write_report({"new": True}, str(output_path))
            self.assertEqual(
                output_path.read_text(encoding="utf-8"), '{"old": true}\n'
            )
            self.assertEqual(
                list(Path(directory).glob(".report.json.*.tmp")), []
            )


if __name__ == "__main__":
    unittest.main()
