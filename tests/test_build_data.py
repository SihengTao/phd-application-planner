import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from assets import build_data
from assets.data_quality import advisor_id, program_id


class BuildDataTests(unittest.TestCase):
    def setUp(self):
        self.report = {
            "schema_version": "2.0",
            "ok": True,
            "errors": [],
            "warnings": [],
            "issues": [],
        }
        self.validator = mock.Mock(side_effect=lambda data, online=False: dict(self.report))
        self.api_patch = mock.patch.object(
            build_data,
            "_quality_api",
            return_value=(program_id, advisor_id, self.validator),
        )
        self.api_patch.start()
        self.addCleanup(self.api_patch.stop)

    @staticmethod
    def _read(path):
        return json.loads(Path(path).read_text(encoding="utf-8"))

    def test_same_names_receive_distinct_stable_ids(self):
        data = {
            "programs": [
                {
                    "region": "US",
                    "school": "School A",
                    "program": "History PhD",
                    "facts": {},
                    "pis": {"pis": [{"name": "Alex Lee"}]},
                },
                {
                    "region": "US",
                    "school": "School B",
                    "program": "History PhD",
                    "facts": {},
                    "pis": {"pis": [{"name": "Alex Lee"}]},
                },
            ]
        }
        with tempfile.TemporaryDirectory() as temporary:
            research, rows = build_data.build_outputs(data, temporary)

        self.assertNotEqual(rows[0]["program_id"], rows[1]["program_id"])
        advisor_a = research["School A"][0]["pis"]["pis"][0]
        advisor_b = research["School B"][0]["pis"]["pis"][0]
        self.assertNotEqual(advisor_a["advisor_id"], advisor_b["advisor_id"])
        self.assertEqual(advisor_a["program_id"], rows[0]["program_id"])
        self.assertEqual(advisor_b["program_id"], rows[1]["program_id"])
        self.assertEqual(research["School A"][0]["program_id"], rows[0]["program_id"])
        self.assertEqual(rows[0]["program_id"], "program_38832c028b4f0e00")
        self.assertEqual(advisor_a["advisor_id"], "advisor_bae240a7be4e6fc5")

    def test_real_quality_id_golden_vectors(self):
        pid = program_id("US", "School A", "History PhD")
        self.assertEqual(pid, "program_38832c028b4f0e00")
        self.assertEqual(
            program_id(" us ", " SCHOOL A ", " HISTORY PHD "),
            "program_38832c028b4f0e00",
        )
        self.assertEqual(
            advisor_id(pid, "Alex Lee"),
            "advisor_bae240a7be4e6fc5",
        )

    def test_root_list_and_cli_create_output_directory(self):
        data = [
            {
                "region": "UK",
                "school": "Example",
                "program": "Sociology PhD",
                "facts": {"applicationPolicy": "unknown"},
                "pis": [],
            }
        ]
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "input.json"
            source.write_text(json.dumps(data), encoding="utf-8")
            destination = base / "nested" / "output"
            self.assertEqual(
                build_data.main([str(source), str(destination)]),
                0,
            )
            rows = self._read(destination / "_rows.json")
            research = self._read(destination / "_research_data.json")
            report = self._read(destination / "_quality_report.json")

        self.assertEqual(rows[0]["program"], "Sociology PhD")
        self.assertEqual(research["Example"][0]["program_id"], rows[0]["program_id"])
        self.assertTrue(report["ok"])
        self.validator.assert_called_with(data, online=False)

    def test_workflow_result_wrapper_is_unwrapped_with_nested_metadata(self):
        data = {
            "result": {
                "floor": 35000,
                "currency": "USD",
                "programs": [
                    {
                        "region": "US",
                        "school": "Wrapped University",
                        "program": "Economics PhD",
                        "facts": {
                            "stipendUSD": 36000,
                            "stipendCurrency": "USD",
                            "meetsFloor": None,
                        },
                        "pis": [],
                    }
                ],
            }
        }
        with tempfile.TemporaryDirectory() as temporary:
            research, rows = build_data.build_outputs(data, temporary)

        self.assertIn("Wrapped University", research)
        self.assertEqual(rows[0]["program"], "Economics PhD")
        self.assertTrue(rows[0]["floor"])
        self.validator.assert_called_with(data, online=False)

    def test_root_faculty_list_is_canonicalized_without_loss(self):
        faculty = [
            {
                "name": "Dana Smith",
                "role": "Professor",
                "research": "Political institutions",
            }
        ]
        data = {
            "programs": [
                {
                    "region": "US",
                    "school": "Faculty University",
                    "program": "Political Science PhD",
                    "facts": {},
                    "faculty": faculty,
                }
            ]
        }
        with tempfile.TemporaryDirectory() as temporary:
            research, _ = build_data.build_outputs(data, temporary)

        record = research["Faculty University"][0]
        self.assertEqual(record["faculty"], faculty)
        self.assertEqual(record["pis"]["pis"][0]["name"], "Dana Smith")
        self.assertEqual(
            record["pis"]["pis"][0]["advisor_id"],
            advisor_id(record["program_id"], "Dana Smith"),
        )

    def test_negative_sentinels_become_null_and_floor_is_unknown(self):
        data = {
            "floor": 35000,
            "currency": "USD",
            "programs": [
                {
                    "region": "US",
                    "school": "Example",
                    "program": "English PhD",
                    "facts": {
                        "stipendUSD": -1,
                        "stipendCurrency": "USD",
                        "meetsFloor": False,
                    },
                    "pis": {
                        "pis": [
                            {"name": "Morgan Lee", "hIndex": -1, "citations": -1}
                        ]
                    },
                }
            ],
        }
        with tempfile.TemporaryDirectory() as temporary:
            research, rows = build_data.build_outputs(data, temporary)

        record = research["Example"][0]
        self.assertIsNone(record["facts"]["stipendUSD"])
        self.assertIsNone(record["facts"]["meetsFloor"])
        self.assertIsNone(record["pis"]["pis"][0]["hIndex"])
        self.assertIsNone(record["pis"]["pis"][0]["citations"])
        self.assertIsNone(rows[0]["usd"])
        self.assertIsNone(rows[0]["floor"])

    def test_false_string_is_not_truthy(self):
        data = {
            "programs": [
                {
                    "school": "Example",
                    "program": "Political Science PhD",
                    "facts": {"meetsFloor": "false", "stipendUSD": True},
                    "pis": {"pis": []},
                }
            ]
        }
        with tempfile.TemporaryDirectory() as temporary:
            research, rows = build_data.build_outputs(data, temporary)

        self.assertFalse(rows[0]["floor"])
        self.assertFalse(research["Example"][0]["facts"]["meetsFloor"])
        self.assertIsNone(rows[0]["usd"])

    def test_floor_recomputed_only_for_comparable_currency(self):
        data = {
            "floor": 35000,
            "currency": "USD",
            "programs": [
                {
                    "school": "Comparable",
                    "program": "PhD",
                    "facts": {
                        "stipendUSD": 34000,
                        "stipendCurrency": "USD",
                        "meetsFloor": "true",
                    },
                    "pis": [],
                },
                {
                    "school": "Different currency",
                    "program": "PhD",
                    "facts": {
                        "stipendUSD": 50000,
                        "stipendCurrency": "CAD",
                        "meetsFloor": None,
                    },
                    "pis": [],
                },
            ],
        }
        with tempfile.TemporaryDirectory() as temporary:
            _, rows = build_data.build_outputs(data, temporary)

        self.assertFalse(rows[0]["floor"])
        self.assertIsNone(rows[1]["floor"])

    def test_application_enum_wins_and_legacy_negation_is_conservative(self):
        restrictions = [
            (
                "Canonical",
                {
                    "applicationPolicy": "multiple_allowed",
                    "applicationRestrictions": "Applicants cannot apply to multiple programs.",
                },
            ),
            (
                "Negation",
                {"applicationRestrictions": "Applicants cannot apply to multiple programs."},
            ),
            (
                "Unpublished",
                {"applicationRestrictions": "No restriction is published for this cycle."},
            ),
            (
                "Conflict",
                {
                    "applicationPolicy": "conflict",
                    "applicationRestrictions": "Sources disagree.",
                },
            ),
        ]
        data = {
            "programs": [
                {"school": school, "program": "PhD", "facts": facts, "pis": []}
                for school, facts in restrictions
            ]
        }
        with tempfile.TemporaryDirectory() as temporary:
            research, rows = build_data.build_outputs(data, temporary)

        self.assertEqual(
            [row["application_policy"] for row in rows],
            ["multiple_allowed", "single_only", "unknown", "conflict"],
        )
        self.assertEqual(
            [row["multi"] for row in rows],
            ["✅ multi", "⛔ 1 only", "", ""],
        )
        self.assertEqual(
            research["Canonical"][0]["facts"]["applicationRestrictions"],
            "Applicants cannot apply to multiple programs.",
        )

    def test_provenance_food_and_research_status_are_preserved(self):
        nearby_food = {
            "campusAnchor": {"name": "Main campus"},
            "restaurants": [{"name": "Spicy House", "cuisine": ["Sichuan"]}],
        }
        legacy_restaurants = [{"name": "Canton Garden", "cuisine": ["Cantonese"]}]
        provenance = {"sources": [{"id": "source_1", "url": "https://example.edu"}]}
        data = {
            "programs": [
                {
                    "school": "Example",
                    "program": "Anthropology PhD",
                    "facts": {},
                    "pis": {"pis": []},
                    "nearbyFood": nearby_food,
                    "restaurants": legacy_restaurants,
                    "provenance": provenance,
                    "researchStatus": "partial",
                }
            ]
        }
        with tempfile.TemporaryDirectory() as temporary:
            research, _ = build_data.build_outputs(data, temporary)

        record = research["Example"][0]
        self.assertEqual(record["nearbyFood"], nearby_food)
        self.assertEqual(record["restaurants"], legacy_restaurants)
        self.assertEqual(record["provenance"], provenance)
        self.assertEqual(record["researchStatus"], "partial")

    def test_quality_errors_write_report_and_block_outputs(self):
        self.report = {
            "schema_version": "2.0",
            "ok": False,
            "errors": ["programs[0].school is missing"],
            "warnings": [],
            "issues": [],
        }
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "out"
            with self.assertRaises(build_data.BuildBlocked):
                build_data.build_outputs({"programs": [{}]}, destination)

            report = self._read(destination / "_quality_report.json")
            self.assertFalse(report["ok"])
            self.assertFalse((destination / "_research_data.json").exists())
            self.assertFalse((destination / "_rows.json").exists())

    def test_strict_mode_blocks_warnings(self):
        self.report = {
            "schema_version": "2.0",
            "ok": True,
            "errors": [],
            "warnings": ["source freshness is unknown"],
            "issues": [],
        }
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "out"
            with self.assertRaises(build_data.BuildBlocked):
                build_data.build_outputs(
                    {"programs": []},
                    destination,
                    strict=True,
                    online=True,
                )
            self.assertTrue((destination / "_quality_report.json").exists())
            self.assertFalse((destination / "_rows.json").exists())
        self.validator.assert_called_with({"programs": []}, online=True)

    def test_second_replace_failure_rolls_back_both_derived_files(self):
        old_data = {
            "programs": [
                {
                    "region": "US",
                    "school": "Old University",
                    "program": "Old PhD",
                    "facts": {},
                    "pis": [],
                }
            ]
        }
        new_data = {
            "programs": [
                {
                    "region": "US",
                    "school": "New University",
                    "program": "New PhD",
                    "facts": {},
                    "pis": [],
                }
            ]
        }
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "out"
            build_data.build_outputs(old_data, destination)
            old_research = (destination / "_research_data.json").read_bytes()
            old_rows = (destination / "_rows.json").read_bytes()

            real_replace = os.replace
            failed = False

            def fail_second_stage(source, target):
                nonlocal failed
                source_path = Path(source)
                target_path = Path(target)
                if (
                    not failed
                    and source_path.name == "staged-rows.json"
                    and source_path.parent.name.startswith(".build-data-")
                    and target_path.name == "_rows.json"
                ):
                    failed = True
                    raise OSError("simulated second replace failure")
                return real_replace(source, target)

            with mock.patch.object(build_data.os, "replace", side_effect=fail_second_stage):
                with self.assertRaises(OSError):
                    build_data.build_outputs(new_data, destination)

            self.assertTrue(failed)
            self.assertEqual(
                (destination / "_research_data.json").read_bytes(),
                old_research,
            )
            self.assertEqual((destination / "_rows.json").read_bytes(), old_rows)
            self.assertEqual(list(destination.glob(".build-data-*")), [])

    def test_cli_exit_codes_distinguish_gate_json_and_operational_failures(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            valid_source = base / "valid.json"
            valid_source.write_text('{"programs": []}', encoding="utf-8")
            invalid_source = base / "invalid.json"
            invalid_source.write_text("{bad json", encoding="utf-8")

            self.report = {
                "schema_version": "2.0",
                "ok": False,
                "errors": ["blocked by quality gate"],
                "warnings": [],
                "issues": [],
            }
            with redirect_stderr(io.StringIO()):
                gate_code = build_data.main(
                    [str(valid_source), str(base / "gate-output")]
                )
                json_code = build_data.main(
                    [str(invalid_source), str(base / "json-output")]
                )
            self.assertEqual(gate_code, 1)
            self.assertEqual(json_code, 2)

            with mock.patch.object(
                build_data,
                "build_outputs",
                side_effect=OSError("simulated filesystem failure"),
            ):
                with redirect_stderr(io.StringIO()):
                    operational_code = build_data.main(
                        [str(valid_source), str(base / "operational-output")]
                    )
            self.assertEqual(operational_code, 2)


if __name__ == "__main__":
    unittest.main()
