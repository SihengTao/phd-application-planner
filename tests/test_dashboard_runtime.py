import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(importlib.util.find_spec("marimo"), "marimo is not installed")
class DashboardRuntimeTests(unittest.TestCase):
    def test_faculty_food_and_provenance_fixture_exports_to_html(self):
        program_id = "program_1d6ddfa298189e3d"
        advisor_id = "advisor_9347c58cdd81ac97"
        source_id = "source_program"
        source = {
            "id": source_id,
            "url": "https://example.edu/history",
            "title": "History graduate program",
            "publisher": "Example University",
            "sourceType": "official_program",
            "official": True,
            "claimPaths": ["facts.applicationPolicy"],
            "effectiveCycle": "2027 admission",
            "updatedAt": "2026-07-01",
            "accessedAt": "2026-07-27",
            "retrievalStatus": "retrieved",
        }
        check = {
            "claimPath": "facts.applicationPolicy",
            "status": "confirmed",
            "initialValue": "single_only",
            "finalValue": "single_only",
            "sourceIds": [source_id],
            "checkedAt": "2026-07-27",
            "conflict": False,
            "resolution": "The current-cycle official page agrees.",
        }
        record = {
            "program_id": program_id,
            "region": "US",
            "school": "Example University",
            "program": "History PhD",
            "city": "Philadelphia",
            "facts": {
                "city": "Philadelphia",
                "stipendUSD": 36000,
                "stipendCurrency": "USD",
                "meetsFloor": True,
                "applicationPolicy": "single_only",
                "applicationRestrictions": "One application per cycle.",
                "fitScore": 9,
                "fitRationale": "Strong archive and faculty coverage.",
                "facultyModel": "Primary advisor plus committee.",
                "methodsTraining": "Archival and digital methods.",
                "languageRequirements": "Reading proficiency.",
                "writingSample": "Required.",
            },
            "pis": {
                "pis": [
                    {
                        "advisor_id": advisor_id,
                        "program_id": program_id,
                        "name": "Alex Li",
                        "role": "Associate Professor",
                        "category": "direction-fit",
                        "research": "Modern East Asian history and archives",
                        "whyFit": "Close topic and archive fit.",
                        "methods": ["archival"],
                        "advisingStatus": "unresolved",
                        "hIndex": None,
                        "citations": None,
                    }
                ]
            },
            "out": {
                "careerOutcomes": "Academic and public-history placements.",
                "placement": "See the official placement list.",
            },
            "nearbyFood": {
                "campusAnchor": {
                    "name": "History Department",
                    "address": "1 College Walk",
                },
                "restaurants": [
                    {
                        "name": "Red Pepper",
                        "regionalStyle": ["Sichuan", "Hunan"],
                        "spiceLevel": "very spicy",
                        "price": "$$",
                        "distanceFromCampus": "1.2 miles",
                        "travelMode": "transit",
                        "signatureDishes": ["mapo tofu"],
                        "openStatus": "verify before visiting",
                        "lastVerified": "2026-07-27",
                        "url": "https://example.com/red-pepper",
                    }
                ],
                "sources": [],
                "claimChecks": [],
                "errors": [],
            },
            "provenance": {
                "sources": [source],
                "checks": [check],
                "conflicts": [],
                "errors": [],
                "researchStatus": "complete",
            },
        }
        row = {
            "program_id": program_id,
            "region": "US",
            "school": "Example University",
            "program": "History PhD",
            "city": "Philadelphia",
            "usd": 36000,
            "floor": True,
            "fit": 9,
            "application_policy": "single_only",
            "multi": "⛔ 1 only",
            "cohort": "",
        }
        config = {
            "schema_version": "2.0",
            "intake_complete": True,
            "field": "History",
            "discipline_mode": "faculty_based",
            "advisor_label": "Faculty/advisor",
            "currency": "USD",
            "stipend_floor": 35000,
            "regions": [
                {
                    "key": "US",
                    "label": "United States",
                    "short": "US",
                    "color": "#0F4D92",
                    "order": 0,
                }
            ],
            "region_order": {"US": 0},
            "interest_areas": {
                "Archives": ["archive"],
                "East Asia": ["east asian"],
            },
            "food_preferences": {"enabled": True},
        }
        quality = {
            "schema_version": "2.0",
            "ok": True,
            "summary": {
                "programs": 1,
                "advisors": 1,
                "restaurants": 1,
                "sources": 1,
                "claims": 1,
                "errors": 0,
                "warnings": 0,
                "info": 0,
                "online": False,
            },
            "errors": [],
            "warnings": [],
            "issues": [],
        }

        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary)
            app_path = run_dir / "phd_explorer.py"
            shutil.copy2(ROOT / "assets" / "dashboard_template.py", app_path)
            exporter = ROOT / "assets" / "excel_export.py"
            self.assertTrue(exporter.is_file())
            copied_exporter = run_dir / exporter.name
            shutil.copy2(exporter, copied_exporter)
            shutil.copy2(ROOT / "assets" / "summary_export.py", run_dir / "summary_export.py")
            (run_dir / "_research_data.json").write_text(
                json.dumps({"Example University": [record]}),
                encoding="utf-8",
            )
            (run_dir / "_rows.json").write_text(
                json.dumps([row]), encoding="utf-8"
            )
            (run_dir / "_config.json").write_text(
                json.dumps(config), encoding="utf-8"
            )
            (run_dir / "_quality_report.json").write_text(
                json.dumps(quality), encoding="utf-8"
            )
            output = run_dir / "dashboard.html"
            env = dict(os.environ)
            env["MPLBACKEND"] = "Agg"
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "marimo",
                    "export",
                    "html",
                    str(app_path),
                    "--no-include-code",
                    "--force",
                    "-o",
                    str(output),
                ],
                cwd=run_dir,
                env=env,
                capture_output=True,
                text=True,
                timeout=120,
            )
            output_exists = output.exists()
            output_size = output.stat().st_size if output_exists else 0
            copied_exporter.write_text(
                "EXPORTER_API_VERSION = 1\n", encoding="utf-8"
            )
            stale_output = run_dir / "dashboard_stale_exporter.html"
            stale_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "marimo",
                    "export",
                    "html",
                    str(app_path),
                    "--no-include-code",
                    "--force",
                    "-o",
                    str(stale_output),
                ],
                cwd=run_dir,
                env=env,
                capture_output=True,
                text=True,
                timeout=120,
            )
            stale_html = (
                stale_output.read_text(encoding="utf-8")
                if stale_output.exists()
                else ""
            )

        self.assertEqual(
            completed.returncode,
            0,
            msg=f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}",
        )
        self.assertTrue(output_exists)
        self.assertGreater(output_size, 10_000)
        self.assertEqual(
            stale_completed.returncode,
            0,
            msg=f"stdout:\n{stale_completed.stdout}\nstderr:\n{stale_completed.stderr}",
        )
        self.assertIn("version is incompatible", stale_html)


if __name__ == "__main__":
    unittest.main()
