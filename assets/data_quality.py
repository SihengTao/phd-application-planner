#!/usr/bin/env python3
"""Validation helpers for ``_wf_result.json``.

The validator deliberately has no third-party dependencies.  It accepts both the
legacy top-level list/object shapes and the provenance-rich v2 shape.  Validation
is offline unless ``online=True`` is requested explicitly.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import hashlib
import ipaddress
import json
from queue import Empty, Queue
import re
import socket
from threading import Thread
import time
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


APPLICATION_POLICY_VALUES = {
    "multiple_allowed",
    "single_only",
    "unknown",
    "conflict",
}
CLAIM_STATUS_VALUES = {
    "confirmed",
    "supported",
    "corrected",
    "conflict",
    "unresolved",
    "not_found",
    "error",
}
VERIFICATION_STATUS_VALUES = {"confirmed", "corrected", "conflict", "unresolved"}
RETRIEVAL_STATUS_VALUES = {
    "retrieved",
    "partial",
    "blocked",
    "not_found",
    "stale",
    "error",
}
SOURCE_COLLECTION_KEYS = {
    "sources",
    "sourceRecords",
    "source_records",
    "sourceLedger",
    "source_ledger",
}
CLAIM_COLLECTION_KEYS = {
    "claimChecks",
    "claim_checks",
    "checks",
    "evidenceChecks",
    "evidence_checks",
}
HIGH_RISK_FIELDS = {
    "stipendUSD",
    "stipendAmount",
    "stipendCurrency",
    "meetsFloor",
    "applicationPolicy",
    "applicationRestrictions",
    "deadlineAndTests",
    "deadline",
    "recruiting",
    "advisingStatus",
}
URL_FIELD_NAMES = {
    "url",
    "sourceUrl",
    "sourceURL",
    "scholarUrl",
    "archiveUrl",
    "officialUrl",
}
DATE_FIELD_NAMES = {
    "accessedAt",
    "accessed_at",
    "checkedAt",
    "checked_at",
    "lastVerified",
    "retrievedAt",
    "updatedAt",
    "publishedOrUpdatedAt",
    "generatedAt",
}
MAX_ONLINE_URLS = 50
ONLINE_GLOBAL_TIMEOUT_SECONDS = 30.0
ONLINE_PER_URL_TIMEOUT_SECONDS = 5.0
DNS_PREFLIGHT_TIMEOUT_SECONDS = 2.0


def _identity_piece(value: Any) -> str:
    """Return the shared Python/JavaScript identity component."""

    if value is None:
        return ""
    return str(value).strip().lower()


def program_id(region: Any, school: Any, program: Any, campus: Any = "") -> str:
    """Return a stable program identifier.

    ``campus`` remains in the public signature for compatibility, but is not part
    of the canonical v2 identity contract.  IDs never depend on list order or
    Python's randomized hash().
    """

    del campus
    payload = "\x1f".join(
        _identity_piece(part) for part in (region, school, program)
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return "program_" + digest


def advisor_id(program_id_value: Any, name: Any) -> str:
    """Return a stable advisor identifier scoped to one program."""

    payload = "\x1f".join(
        (_identity_piece(program_id_value), _identity_piece(name))
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return "advisor_" + digest


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _json_equal(left: Any, right: Any) -> bool:
    try:
        return json.dumps(
            left, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ) == json.dumps(
            right, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        )
    except (TypeError, ValueError):
        return left == right


def _record_fingerprint(value: Mapping[str, Any]) -> str:
    """Fingerprint a JSON record so compatibility aliases are counted once."""

    try:
        return json.dumps(
            value, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        )
    except (TypeError, ValueError):
        return repr(sorted((str(key), repr(item)) for key, item in value.items()))


def _parse_date(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed_date = date.fromisoformat(text)
        except ValueError:
            return None
        parsed = datetime.combine(parsed_date, datetime.min.time())
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _path_join(path: str, key: Any) -> str:
    if isinstance(key, int):
        return "{}[{}]".format(path, key)
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", str(key)):
        return "{}.{}".format(path, key)
    return "{}[{}]".format(path, json.dumps(str(key), ensure_ascii=False))


class _Validator:
    def __init__(self, online: bool = False) -> None:
        self.online = bool(online)
        self.issues: List[Dict[str, Any]] = []
        self.urls: Dict[str, str] = {}
        self.program_count = 0
        self.advisor_count = 0
        self.restaurant_count = 0
        self.source_count = 0
        self.claim_count = 0
        self._now = datetime.now(timezone.utc)
        self._seen_source_records: set = set()
        self._seen_legacy_sources: set = set()
        self._seen_claim_checks: set = set()
        self.discipline_mode: Optional[str] = None

    def add(
        self,
        severity: str,
        code: str,
        path: str,
        message: str,
        **details: Any
    ) -> None:
        issue: Dict[str, Any] = {
            "severity": severity,
            "code": code,
            "path": path,
            "message": message,
        }
        if details:
            issue["details"] = details
        self.issues.append(issue)

    def check_date(
        self,
        value: Any,
        path: str,
        *,
        required: bool = False,
        stale_days: Optional[int] = None
    ) -> Optional[datetime]:
        if value is None or value == "":
            if required:
                self.add("warning", "date_missing", path, "A verification date is required.")
            return None
        parsed = _parse_date(value)
        if parsed is None:
            self.add(
                "error",
                "date_invalid",
                path,
                "Expected an ISO 8601 date or datetime.",
            )
            return None
        if parsed > self._now + timedelta(minutes=5):
            self.add(
                "warning",
                "date_in_future",
                path,
                "The recorded date is in the future.",
                value=value,
            )
        if stale_days is not None and (self._now - parsed).days > stale_days:
            self.add(
                "warning",
                "date_stale",
                path,
                "The recorded verification is stale.",
                age_days=(self._now - parsed).days,
            )
        return parsed

    def check_url(
        self, value: Any, path: str, *, severity: str = "error"
    ) -> Optional[str]:
        if not _is_nonempty_string(value):
            self.add(severity, "url_missing", path, "A non-empty URL is required.")
            return None
        text = value.strip()
        try:
            parsed = urlsplit(text)
            port = parsed.port
        except (TypeError, ValueError):
            parsed = None
            port = None
        if (
            parsed is None
            or parsed.scheme.lower() not in {"http", "https"}
            or not parsed.hostname
            or any(ch.isspace() for ch in parsed.netloc)
            or (port is not None and not 0 < port < 65536)
        ):
            self.add(
                severity,
                "url_invalid",
                path,
                "Expected an absolute http:// or https:// URL with a host.",
                value=value,
            )
            return None
        self.urls.setdefault(text, path)
        return text

    def validate_source_collection(
        self,
        value: Any,
        path: str,
        registry: Dict[str, List[Dict[str, Any]]],
        claim_support: Dict[str, List[str]],
    ) -> None:
        if isinstance(value, Mapping):
            records: List[Tuple[Optional[str], Any, str]] = []
            for key, record in value.items():
                records.append((str(key), record, _path_join(path, key)))
        elif isinstance(value, list):
            records = [
                (None, record, _path_join(path, index))
                for index, record in enumerate(value)
            ]
        else:
            self.add(
                "error",
                "sources_type",
                path,
                "Sources must be an array or an ID-to-source object.",
            )
            return

        legacy_reported = False
        for implied_id, record, record_path in records:
            if isinstance(record, str):
                if record in self._seen_legacy_sources:
                    continue
                self._seen_legacy_sources.add(record)
                self.check_url(record, record_path, severity="warning")
                if not legacy_reported:
                    self.add(
                        "warning",
                        "source_legacy_unstructured",
                        path,
                        "Legacy URL strings cannot record claim, access-date, or official-source metadata.",
                    )
                    legacy_reported = True
                continue
            if not isinstance(record, Mapping):
                self.add(
                    "error",
                    "source_record_type",
                    record_path,
                    "Each structured source must be an object.",
                )
                continue
            fingerprint = _record_fingerprint(record)
            if fingerprint in self._seen_source_records:
                continue
            self._seen_source_records.add(fingerprint)

            self.source_count += 1
            source_id_value = (
                record.get("id")
                or record.get("sourceId")
                or record.get("source_id")
                or implied_id
            )
            source_id_text = (
                str(source_id_value).strip() if source_id_value is not None else ""
            )
            if not source_id_text:
                self.add(
                    "warning",
                    "source_id_missing",
                    record_path,
                    "Structured sources should have a stable ID.",
                )

            url_value = (
                record.get("url")
                or record.get("sourceUrl")
                or record.get("source_url")
            )
            url_text = self.check_url(
                url_value, _path_join(record_path, "url"), severity="error"
            )
            for field_name in ("title", "publisher"):
                if not _is_nonempty_string(record.get(field_name)):
                    self.add(
                        "warning",
                        "source_field_missing",
                        _path_join(record_path, field_name),
                        "Structured source field {!r} is missing.".format(field_name),
                    )

            official_value = (
                record.get("official")
                if "official" in record
                else record.get("isOfficial")
            )
            if official_value is None:
                self.add(
                    "warning",
                    "source_official_missing",
                    _path_join(record_path, "official"),
                    "State explicitly whether this is an official source.",
                )
            elif not isinstance(official_value, bool):
                self.add(
                    "error",
                    "boolean_invalid",
                    _path_join(record_path, "official"),
                    "official must be true or false, not a string or number.",
                )

            accessed_value = record.get("accessedAt", record.get("retrievedAt"))
            accessed_at = self.check_date(
                accessed_value,
                _path_join(record_path, "accessedAt"),
                required=True,
            )
            retrieval_status = record.get(
                "retrievalStatus", record.get("status")
            )
            if retrieval_status is None:
                self.add(
                    "warning",
                    "retrieval_status_missing",
                    _path_join(record_path, "retrievalStatus"),
                    "Structured sources should record retrievalStatus.",
                )
            elif retrieval_status not in RETRIEVAL_STATUS_VALUES:
                self.add(
                    "error",
                    "retrieval_status_invalid",
                    _path_join(record_path, "retrievalStatus"),
                    "retrievalStatus must be one of {}.".format(
                        ", ".join(sorted(RETRIEVAL_STATUS_VALUES))
                    ),
                    value=retrieval_status,
                )

            effective_cycle = record.get("effectiveCycle")
            if effective_cycle is not None and not isinstance(effective_cycle, str):
                self.add(
                    "error",
                    "effective_cycle_invalid",
                    _path_join(record_path, "effectiveCycle"),
                    "effectiveCycle must be a string or null.",
                )

            claims_value = record.get("claimPaths", record.get("claims", []))
            if claims_value is None:
                claims_value = []
            if not isinstance(claims_value, list) or any(
                not _is_nonempty_string(item) for item in claims_value
            ):
                self.add(
                    "error",
                    "claim_paths_invalid",
                    _path_join(record_path, "claimPaths"),
                    "claimPaths must be an array of non-empty strings.",
                )
                claims_value = []
            for claim_path in claims_value:
                claim_support.setdefault(claim_path.strip(), []).append(source_id_text)

            internal = {
                "id": source_id_text,
                "url": url_text,
                "official": official_value is True,
                "accessedAt": accessed_at,
                "retrievalStatus": retrieval_status,
                "path": record_path,
            }
            if source_id_text:
                prior = registry.setdefault(source_id_text, [])
                if prior and not any(item.get("url") == url_text for item in prior):
                    self.add(
                        "error",
                        "source_id_conflict",
                        record_path,
                        "The same source ID points to different URLs.",
                        source_id=source_id_text,
                    )
                prior.append(internal)

    def scan_sources(
        self,
        node: Any,
        path: str,
        registry: Dict[str, List[Dict[str, Any]]],
        claim_support: Dict[str, List[str]],
        seen: Optional[set] = None,
    ) -> None:
        if seen is None:
            seen = set()
        if isinstance(node, (dict, list)):
            marker = id(node)
            if marker in seen:
                return
            seen.add(marker)
        if isinstance(node, Mapping):
            for key, value in node.items():
                child_path = _path_join(path, key)
                if key in SOURCE_COLLECTION_KEYS:
                    self.validate_source_collection(
                        value, child_path, registry, claim_support
                    )
                else:
                    self.scan_sources(value, child_path, registry, claim_support, seen)
        elif isinstance(node, list):
            for index, value in enumerate(node):
                self.scan_sources(
                    value, _path_join(path, index), registry, claim_support, seen
                )

    def _resolve_source_ids(
        self,
        value: Any,
        path: str,
        registry: Dict[str, List[Dict[str, Any]]],
    ) -> Tuple[List[str], List[Dict[str, Any]]]:
        if value is None:
            return [], []
        if isinstance(value, str):
            values = [value]
        elif isinstance(value, list):
            values = value
        else:
            self.add(
                "error",
                "source_ids_type",
                path,
                "sourceIds must be an array of source IDs.",
            )
            return [], []
        ids: List[str] = []
        records: List[Dict[str, Any]] = []
        for index, item in enumerate(values):
            item_path = _path_join(path, index)
            if not _is_nonempty_string(item):
                self.add(
                    "error",
                    "source_id_invalid",
                    item_path,
                    "Each source ID must be a non-empty string.",
                )
                continue
            text = item.strip()
            if text.startswith(("http://", "https://")):
                self.check_url(text, item_path)
                ids.append(text)
                continue
            ids.append(text)
            matches = registry.get(text, [])
            if not matches:
                self.add(
                    "error",
                    "source_reference_missing",
                    item_path,
                    "The claim references an unknown source ID.",
                    source_id=text,
                )
            records.extend(matches)
        return ids, records

    def validate_claim_collection(
        self,
        value: Any,
        path: str,
        registry: Dict[str, List[Dict[str, Any]]],
        claim_support: Dict[str, List[str]],
        *,
        provenance_checks: bool = False,
    ) -> None:
        if not isinstance(value, list):
            self.add(
                "error",
                "claim_checks_type",
                path,
                "Claim checks must be an array.",
            )
            return
        for index, check in enumerate(value):
            check_path = _path_join(path, index)
            if not isinstance(check, Mapping):
                self.add(
                    "error",
                    "claim_check_type",
                    check_path,
                    "Each claim check must be an object.",
                )
                continue
            fingerprint = _record_fingerprint(check)
            if fingerprint in self._seen_claim_checks:
                continue
            self._seen_claim_checks.add(fingerprint)
            self.claim_count += 1
            claim_path_value = (
                check.get("claimPath")
                or check.get("field")
                or check.get("path")
            )
            if not _is_nonempty_string(claim_path_value):
                self.add(
                    "error",
                    "claim_path_missing",
                    _path_join(check_path, "claimPath"),
                    "Each claim check needs a claimPath.",
                )
                claim_path_value = ""
            else:
                claim_path_value = claim_path_value.strip()

            status = check.get("status")
            if status not in CLAIM_STATUS_VALUES:
                self.add(
                    "error",
                    "claim_status_invalid",
                    _path_join(check_path, "status"),
                    "Claim status must be one of {}.".format(
                        ", ".join(sorted(CLAIM_STATUS_VALUES))
                    ),
                    value=status,
                )

            source_ids_value = check.get(
                "sourceIds", check.get("source_ids", check.get("sources"))
            )
            source_ids, records = self._resolve_source_ids(
                source_ids_value,
                _path_join(check_path, "sourceIds"),
                registry,
            )
            if claim_path_value:
                claim_support.setdefault(claim_path_value, []).extend(source_ids)

            high_risk = self._is_high_risk_claim(claim_path_value)
            if (
                high_risk
                and status in {"confirmed", "supported", "corrected"}
                and not source_ids
            ):
                self.add(
                    "warning",
                    "high_risk_claim_source_missing",
                    check_path,
                    "A confirmed high-risk claim needs claim-level source IDs.",
                    claim_path=claim_path_value,
                )
            if (
                high_risk
                and status in {"confirmed", "supported", "corrected"}
                and source_ids
                and not any(
                    record.get("official")
                    and record.get("retrievalStatus") in {"retrieved", "partial"}
                    for record in records
                )
            ):
                self.add(
                    "warning",
                    "high_risk_official_source_missing",
                    check_path,
                    "A confirmed high-risk claim has no explicitly official source.",
                    claim_path=claim_path_value,
                )

            has_initial = "initialValue" in check or "priorValue" in check
            has_final = "finalValue" in check
            initial = check.get("initialValue", check.get("priorValue"))
            final = check.get("finalValue")
            if status == "confirmed" and has_initial and has_final and not _json_equal(initial, final):
                self.add(
                    "error",
                    "verification_confirmed_but_changed",
                    check_path,
                    "A confirmed check cannot change the initial value.",
                )
            if status == "corrected" and has_initial and has_final and _json_equal(initial, final):
                self.add(
                    "warning",
                    "verification_corrected_but_unchanged",
                    check_path,
                    "A corrected check records no value change.",
                )
            self.check_date(
                check.get("checkedAt"),
                _path_join(check_path, "checkedAt"),
                required=True,
            )
            conflict = check.get("conflict")
            if conflict is not None and not isinstance(conflict, bool):
                self.add(
                    "error",
                    "boolean_invalid",
                    _path_join(check_path, "conflict"),
                    "Claim-check conflict must be true or false.",
                )
            elif (
                status in {"confirmed", "corrected", "supported"}
                and conflict is True
            ) or (status == "conflict" and conflict is False):
                self.add(
                    "error",
                    "claim_status_conflict",
                    check_path,
                    "Claim status conflicts with the conflict flag.",
                )

    def scan_claims(
        self,
        node: Any,
        path: str,
        registry: Dict[str, List[Dict[str, Any]]],
        claim_support: Dict[str, List[str]],
        seen: Optional[set] = None,
    ) -> None:
        if seen is None:
            seen = set()
        if isinstance(node, (dict, list)):
            marker = id(node)
            if marker in seen:
                return
            seen.add(marker)
        if isinstance(node, Mapping):
            for key, value in node.items():
                child_path = _path_join(path, key)
                if key in CLAIM_COLLECTION_KEYS:
                    self.validate_claim_collection(
                        value,
                        child_path,
                        registry,
                        claim_support,
                        provenance_checks=(key == "checks"),
                    )
                elif key in {"claimSources", "claim_sources"}:
                    self.validate_claim_sources(
                        value, child_path, registry, claim_support
                    )
                elif key not in SOURCE_COLLECTION_KEYS:
                    self.scan_claims(
                        value, child_path, registry, claim_support, seen
                    )
        elif isinstance(node, list):
            for index, value in enumerate(node):
                self.scan_claims(
                    value, _path_join(path, index), registry, claim_support, seen
                )

    def validate_claim_sources(
        self,
        value: Any,
        path: str,
        registry: Dict[str, List[Dict[str, Any]]],
        claim_support: Dict[str, List[str]],
    ) -> None:
        if not isinstance(value, Mapping):
            self.add(
                "error",
                "claim_sources_type",
                path,
                "claimSources must map claim paths to source IDs.",
            )
            return
        for claim_path_value, refs in value.items():
            claim_path = str(claim_path_value).strip()
            ids, records = self._resolve_source_ids(
                refs, _path_join(path, claim_path_value), registry
            )
            claim_support.setdefault(claim_path, []).extend(ids)
            if self._is_high_risk_claim(claim_path) and ids and records and not any(
                record.get("official") for record in records
            ):
                self.add(
                    "warning",
                    "high_risk_official_source_missing",
                    _path_join(path, claim_path_value),
                    "A high-risk claim has no explicitly official source.",
                    claim_path=claim_path,
                )

    @staticmethod
    def _is_high_risk_claim(claim_path: Any) -> bool:
        if not isinstance(claim_path, str):
            return False
        collapsed = re.sub(r"[^a-z0-9]", "", claim_path.casefold())
        return any(
            re.sub(r"[^a-z0-9]", "", field.casefold()) in collapsed
            for field in HIGH_RISK_FIELDS
        )

    def _claim_has_source(
        self, claim_support: Mapping[str, Sequence[str]], field_name: str
    ) -> bool:
        return bool(self._claim_source_ids(claim_support, field_name))

    def _claim_source_ids(
        self, claim_support: Mapping[str, Sequence[str]], field_name: str
    ) -> List[str]:
        target = re.sub(r"[^a-z0-9]", "", field_name.casefold())
        found: List[str] = []
        for claim_path, source_ids in claim_support.items():
            collapsed = re.sub(r"[^a-z0-9]", "", claim_path.casefold())
            if target in collapsed and source_ids:
                found.extend(str(source_id) for source_id in source_ids)
        return found

    @staticmethod
    def _has_available_official_source(
        source_ids: Sequence[str],
        registry: Mapping[str, Sequence[Mapping[str, Any]]],
    ) -> bool:
        for source_id_value in source_ids:
            for record in registry.get(source_id_value, []):
                if (
                    record.get("official")
                    and record.get("retrievalStatus") in {"retrieved", "partial"}
                ):
                    return True
        return False

    def validate_root_metadata(self, root: Mapping[str, Any], path: str) -> Tuple[Any, Any]:
        camel_version = root.get("schemaVersion")
        snake_version = root.get("schema_version")
        schema_version = (
            camel_version if camel_version is not None else snake_version
        )
        if schema_version is None:
            self.add(
                "info",
                "legacy_schema",
                path,
                "No schemaVersion was supplied; legacy compatibility rules were used.",
            )
        elif not _is_nonempty_string(schema_version):
            self.add(
                "error",
                "schema_version_invalid",
                _path_join(path, "schemaVersion"),
                "schemaVersion must be a non-empty string.",
            )
        if (
            camel_version is not None
            and snake_version is not None
            and camel_version != snake_version
        ):
            self.add(
                "error",
                "schema_version_conflict",
                path,
                "schemaVersion and schema_version disagree.",
                schemaVersion=camel_version,
                schema_version=snake_version,
            )

        snake_mode = root.get("discipline_mode")
        camel_mode = root.get("disciplineMode")
        discipline_mode = snake_mode if snake_mode is not None else camel_mode
        if (
            snake_mode is not None
            and camel_mode is not None
            and snake_mode != camel_mode
        ):
            self.add(
                "error",
                "discipline_mode_conflict",
                path,
                "discipline_mode and disciplineMode disagree.",
                discipline_mode=snake_mode,
                disciplineMode=camel_mode,
            )
        if discipline_mode is not None:
            if discipline_mode not in {"lab_based", "faculty_based", "hybrid"}:
                self.add(
                    "error",
                    "discipline_mode_invalid",
                    _path_join(path, "discipline_mode"),
                    "discipline_mode must be lab_based, faculty_based, or hybrid.",
                    value=discipline_mode,
                )
            else:
                self.discipline_mode = discipline_mode

        if "generatedAt" in root:
            self.check_date(
                root.get("generatedAt"), _path_join(path, "generatedAt"), required=True
            )
        elif str(schema_version or "").startswith("2"):
            self.add(
                "warning",
                "generated_at_missing",
                _path_join(path, "generatedAt"),
                "Schema v2 results should record generatedAt.",
            )

        currency = root.get("currency")
        if currency is None:
            self.add(
                "warning",
                "currency_missing",
                _path_join(path, "currency"),
                "Top-level currency is missing; stipend comparisons are ambiguous.",
            )
        elif not isinstance(currency, str) or not re.fullmatch(r"[A-Za-z]{3}", currency.strip()):
            self.add(
                "error",
                "currency_invalid",
                _path_join(path, "currency"),
                "currency must be a three-letter ISO-style code.",
                value=currency,
            )
        elif currency != currency.upper():
            self.add(
                "warning",
                "currency_not_normalized",
                _path_join(path, "currency"),
                "Use an uppercase currency code.",
                value=currency,
            )

        floor = root.get("floor", root.get("stipend_floor"))
        if floor is None:
            self.add(
                "warning",
                "stipend_floor_missing",
                _path_join(path, "floor"),
                "Top-level stipend floor is missing.",
            )
        elif not _is_number(floor) or floor < 0:
            self.add(
                "error",
                "stipend_floor_invalid",
                _path_join(path, "floor"),
                "The stipend floor must be a non-negative number.",
                value=floor,
            )

        regions = root.get("regions")
        if regions is not None and not isinstance(regions, list):
            self.add(
                "error",
                "regions_type",
                _path_join(path, "regions"),
                "regions must be an array.",
            )
        return floor, currency

    def validate_facts(
        self,
        facts: Any,
        path: str,
        floor: Any,
        currency: Any,
        claim_support: Mapping[str, Sequence[str]],
        registry: Mapping[str, Sequence[Mapping[str, Any]]],
    ) -> None:
        if facts is None:
            self.add(
                "warning",
                "facts_missing",
                path,
                "Program facts are missing.",
            )
            return
        if not isinstance(facts, Mapping):
            self.add("error", "facts_type", path, "facts must be an object.")
            return

        stipend_key = (
            "stipendUSD"
            if "stipendUSD" in facts
            else "stipendAmount"
            if "stipendAmount" in facts
            else None
        )
        stipend = facts.get(stipend_key) if stipend_key else None
        if stipend_key is None:
            self.add(
                "warning",
                "stipend_missing",
                _path_join(path, "stipendUSD"),
                "No stipend amount was recorded.",
            )
        elif isinstance(stipend, bool):
            self.add(
                "error",
                "stipend_type",
                _path_join(path, stipend_key),
                "A boolean is not a stipend amount.",
            )
        elif stipend is None:
            pass
        elif not _is_number(stipend):
            code = "stipend_numeric_string" if isinstance(stipend, str) else "stipend_type"
            self.add(
                "warning" if code == "stipend_numeric_string" else "error",
                code,
                _path_join(path, stipend_key),
                "Stipend must be a number or null.",
                value=stipend,
            )
        elif stipend < 0:
            self.add(
                "warning",
                "stipend_legacy_sentinel",
                _path_join(path, stipend_key),
                "Use null instead of a negative missing-value sentinel.",
                value=stipend,
            )

        meets_floor = facts.get("meetsFloor")
        if "meetsFloor" not in facts:
            self.add(
                "warning",
                "meets_floor_missing",
                _path_join(path, "meetsFloor"),
                "meetsFloor is missing.",
            )
        elif meets_floor is not None and not isinstance(meets_floor, bool):
            self.add(
                "error",
                "boolean_invalid",
                _path_join(path, "meetsFloor"),
                "meetsFloor must be true, false, or null.",
                value=meets_floor,
            )
        elif (
            _is_number(stipend)
            and stipend >= 0
            and _is_number(floor)
            and isinstance(meets_floor, bool)
            and meets_floor != (stipend >= floor)
        ):
            self.add(
                "error",
                "stipend_floor_mismatch",
                _path_join(path, "meetsFloor"),
                "meetsFloor conflicts with the stipend amount and top-level floor.",
                stipend=stipend,
                floor=floor,
                recorded=meets_floor,
            )
        elif (
            (stipend is None or (_is_number(stipend) and stipend < 0))
            and isinstance(meets_floor, bool)
        ):
            self.add(
                "warning",
                "meets_floor_unknown_stipend",
                _path_join(path, "meetsFloor"),
                "meetsFloor should be null when the stipend is unknown.",
            )

        found_official_key = (
            "stipend_foundOfficial"
            if "stipend_foundOfficial" in facts
            else "stipendFoundOfficial"
            if "stipendFoundOfficial" in facts
            else None
        )
        if (
            found_official_key
            and facts.get(found_official_key) is not None
            and not isinstance(facts.get(found_official_key), bool)
        ):
            self.add(
                "error",
                "boolean_invalid",
                _path_join(path, found_official_key),
                "{} must be true or false.".format(found_official_key),
            )

        record_currency = facts.get(
            "stipendCurrency", facts.get("currency", facts.get("convertedCurrency"))
        )
        if record_currency is not None:
            if not isinstance(record_currency, str) or not re.fullmatch(
                r"[A-Za-z]{3}", record_currency.strip()
            ):
                self.add(
                    "error",
                    "currency_invalid",
                    _path_join(path, "stipendCurrency"),
                    "Stipend currency must be a three-letter code.",
                    value=record_currency,
                )
            elif (
                isinstance(currency, str)
                and record_currency.upper() != currency.upper()
            ):
                self.add(
                    "error",
                    "currency_mismatch",
                    _path_join(path, "stipendCurrency"),
                    "Program stipend currency conflicts with the top-level currency.",
                    top_level=currency,
                    program=record_currency,
                )
        elif stipend_key == "stipendUSD" and isinstance(currency, str) and currency.upper() != "USD":
            self.add(
                "warning",
                "stipend_currency_ambiguous",
                _path_join(path, "stipendUSD"),
                "stipendUSD is ambiguous when the selected currency is not USD.",
                currency=currency,
            )

        if "applicationPolicy" in facts:
            policy = facts.get("applicationPolicy")
            if policy not in APPLICATION_POLICY_VALUES:
                self.add(
                    "error",
                    "application_policy_invalid",
                    _path_join(path, "applicationPolicy"),
                    "applicationPolicy must be one of {}.".format(
                        ", ".join(sorted(APPLICATION_POLICY_VALUES))
                    ),
                    value=policy,
                )
        elif "applicationRestrictions" in facts:
            self.add(
                "warning",
                "application_policy_legacy",
                _path_join(path, "applicationRestrictions"),
                "Legacy free text should be normalized to applicationPolicy.",
            )
        else:
            self.add(
                "warning",
                "application_policy_missing",
                _path_join(path, "applicationPolicy"),
                "No application policy was recorded.",
            )

        for field_name in HIGH_RISK_FIELDS:
            if field_name in facts:
                source_ids = self._claim_source_ids(claim_support, field_name)
                if not source_ids:
                    self.add(
                        "warning",
                        "high_risk_claim_source_missing",
                        _path_join(path, field_name),
                        "This high-risk fact has no claim-level source.",
                        claim_path="facts." + field_name,
                    )
                elif not self._has_available_official_source(source_ids, registry):
                    self.add(
                        "warning",
                        "high_risk_official_source_missing",
                        _path_join(path, field_name),
                        "This high-risk fact has no retrieved official source.",
                        claim_path="facts." + field_name,
                    )

    def _advisor_list(self, value: Any, path: str) -> Tuple[List[Any], str]:
        if value is None:
            return [], path
        if isinstance(value, list):
            return value, path
        if not isinstance(value, Mapping):
            self.add(
                "error",
                "faculty_type",
                path,
                "faculty/pis must be an object or an array.",
            )
            return [], path
        for key in ("faculty", "advisors", "pis"):
            if key in value:
                nested = value.get(key)
                nested_path = _path_join(path, key)
                if not isinstance(nested, list):
                    self.add(
                        "error",
                        "faculty_list_type",
                        nested_path,
                        "{} must be an array.".format(key),
                    )
                    return [], nested_path
                return nested, nested_path
        return [], path

    def validate_advisors(
        self,
        value: Any,
        path: str,
        program_identifier: str,
        claim_support: Mapping[str, Sequence[str]],
    ) -> None:
        advisors, list_path = self._advisor_list(value, path)
        seen: Dict[str, str] = {}
        for index, advisor in enumerate(advisors):
            advisor_path = _path_join(list_path, index)
            if not isinstance(advisor, Mapping):
                self.add(
                    "error",
                    "advisor_type",
                    advisor_path,
                    "Each advisor must be an object.",
                )
                continue
            self.advisor_count += 1
            name = advisor.get("name")
            if not _is_nonempty_string(name):
                self.add(
                    "error",
                    "advisor_name_missing",
                    _path_join(advisor_path, "name"),
                    "Advisor name is required.",
                )
                continue
            generated_id = advisor_id(program_identifier, name)
            explicit_id = advisor.get("advisor_id", advisor.get("advisorId"))
            if explicit_id is not None and explicit_id != generated_id:
                self.add(
                    "warning",
                    "advisor_id_mismatch",
                    _path_join(advisor_path, "advisor_id"),
                    "Stored advisor ID does not match the stable helper.",
                    expected=generated_id,
                    actual=explicit_id,
                )
            if generated_id in seen:
                self.add(
                    "warning",
                    "advisor_duplicate",
                    advisor_path,
                    "The same advisor is repeated within one program.",
                    first_path=seen[generated_id],
                )
            else:
                seen[generated_id] = advisor_path

            for field_name in ("hIndex", "citations", "fitScore"):
                metric = advisor.get(field_name)
                if metric is None:
                    continue
                if isinstance(metric, bool) or not _is_number(metric):
                    self.add(
                        "error",
                        "advisor_metric_invalid",
                        _path_join(advisor_path, field_name),
                        "{} must be a number or null.".format(field_name),
                        value=metric,
                    )
                elif metric < 0:
                    self.add(
                        "warning",
                        "advisor_metric_legacy_sentinel",
                        _path_join(advisor_path, field_name),
                        "Use null instead of a negative missing-value sentinel.",
                    )
            for field_name in URL_FIELD_NAMES:
                if field_name in advisor and advisor.get(field_name):
                    self.check_url(
                        advisor.get(field_name),
                        _path_join(advisor_path, field_name),
                        severity="warning",
                    )
            if "recruiting" in advisor and not self._claim_has_source(
                claim_support, "recruiting"
            ):
                self.add(
                    "warning",
                    "high_risk_claim_source_missing",
                    _path_join(advisor_path, "recruiting"),
                    "Recruiting status needs claim-level evidence.",
                )

    def validate_verification(self, value: Any, path: str) -> None:
        if value is None:
            self.add(
                "warning",
                "verification_missing",
                path,
                "No independent verification record was provided.",
            )
            return
        if not isinstance(value, Mapping):
            self.add(
                "error",
                "verification_type",
                path,
                "verification must be an object.",
            )
            return
        status = value.get("status")
        if status not in VERIFICATION_STATUS_VALUES:
            self.add(
                "error",
                "verification_status_invalid",
                _path_join(path, "status"),
                "verification.status must be one of {}.".format(
                    ", ".join(sorted(VERIFICATION_STATUS_VALUES))
                ),
                value=status,
            )
        self.check_date(
            value.get("checkedAt"),
            _path_join(path, "checkedAt"),
            required=True,
        )
        conflict = value.get("conflict")
        if conflict is not None and not isinstance(conflict, bool):
            self.add(
                "error",
                "boolean_invalid",
                _path_join(path, "conflict"),
                "verification.conflict must be true or false.",
            )
        if status in {"confirmed", "corrected"} and conflict is True:
            self.add(
                "error",
                "verification_status_conflict",
                path,
                "A confirmed/corrected verification cannot also set conflict=true.",
            )
        if status == "conflict" and conflict is False:
            self.add(
                "error",
                "verification_status_conflict",
                path,
                "A conflict verification cannot set conflict=false.",
            )
        initial = value.get("initial")
        final = value.get("final")
        if initial is not None and not isinstance(initial, Mapping):
            self.add(
                "error",
                "verification_initial_type",
                _path_join(path, "initial"),
                "verification.initial must be an object.",
            )
            initial = None
        if final is not None and not isinstance(final, Mapping):
            self.add(
                "error",
                "verification_final_type",
                _path_join(path, "final"),
                "verification.final must be an object.",
            )
            final = None
        if isinstance(initial, Mapping) and isinstance(final, Mapping):
            keys = set(initial) | set(final)
            changed = any(
                not _json_equal(initial.get(key), final.get(key)) for key in keys
            )
            if status == "confirmed" and changed:
                self.add(
                    "error",
                    "verification_confirmed_but_changed",
                    path,
                    "Confirmed verification has different initial and final values.",
                )
            if status == "corrected" and not changed:
                self.add(
                    "warning",
                    "verification_corrected_but_unchanged",
                    path,
                    "Corrected verification has identical initial and final values.",
                )

    def validate_provenance(self, value: Any, path: str) -> None:
        if value is None:
            return
        if not isinstance(value, Mapping):
            self.add(
                "error", "provenance_type", path, "provenance must be an object."
            )
            return
        conflicts = value.get("conflicts")
        if conflicts is not None and not isinstance(conflicts, list):
            self.add(
                "error",
                "conflicts_type",
                _path_join(path, "conflicts"),
                "conflicts must be an array.",
            )
        errors = value.get("errors")
        if errors is not None and not isinstance(errors, list):
            self.add(
                "error",
                "research_errors_type",
                _path_join(path, "errors"),
                "provenance.errors must be an array.",
            )
        checks = value.get("checks")
        if isinstance(conflicts, list) and isinstance(checks, list):
            unresolved_paths = set()
            for index, conflict_record in enumerate(conflicts):
                conflict_path = _path_join(_path_join(path, "conflicts"), index)
                if not isinstance(conflict_record, Mapping):
                    self.add(
                        "error",
                        "conflict_record_type",
                        conflict_path,
                        "Each conflict must be an object.",
                    )
                    continue
                if conflict_record.get("status") in {
                    None,
                    "conflict",
                    "unresolved",
                    "open",
                }:
                    unresolved_paths.add(str(conflict_record.get("claimPath") or ""))
            terminal_checks: Dict[str, Mapping[str, Any]] = {}
            for check in checks:
                if not isinstance(check, Mapping):
                    continue
                claim_path_value = str(check.get("claimPath") or "")
                if claim_path_value:
                    terminal_checks[claim_path_value] = check
            confirmed_paths = {
                claim_path_value
                for claim_path_value, check in terminal_checks.items()
                if check.get("status") in {"confirmed", "corrected"}
                and check.get("conflict") is not True
            }
            overlap = sorted(
                path_value
                for path_value in unresolved_paths & confirmed_paths
                if path_value
            )
            if overlap:
                self.add(
                    "error",
                    "verification_conflicts_unresolved",
                    _path_join(path, "conflicts"),
                    "A claim is both confirmed/corrected and still in unresolved conflicts.",
                    claim_paths=overlap,
                )

    @staticmethod
    def _coverage_value_present(value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, (list, tuple, dict, set)):
            return bool(value)
        return True

    def validate_hss_coverage(
        self, program: Mapping[str, Any], path: str
    ) -> None:
        if self.discipline_mode not in {"faculty_based", "hybrid"}:
            return
        facts_value = program.get("facts")
        facts = facts_value if isinstance(facts_value, Mapping) else {}
        outcome_records = [
            value
            for value in (program.get("outcomes"), program.get("out"))
            if isinstance(value, Mapping)
        ]

        def facts_have(*fields: str) -> bool:
            return any(
                self._coverage_value_present(facts.get(field)) for field in fields
            )

        def outcomes_have(*fields: str) -> bool:
            return any(
                self._coverage_value_present(record.get(field))
                for record in outcome_records
                for field in fields
            )

        groups: List[Tuple[str, Dict[str, bool], List[str]]] = [
            (
                "advising_admissions_model",
                {
                    "admissions_model": facts_have(
                        "admissionsModel", "facultyModel", "applicationRoute"
                    ),
                    "advising_model": facts_have(
                        "advisorSelection",
                        "advisorAssignment",
                        "advisorContactPolicy",
                        "committeeStructure",
                    ),
                },
                [
                    "admissionsModel|facultyModel|applicationRoute",
                    "advisorSelection|advisorAssignment|advisorContactPolicy|committeeStructure",
                ],
            ),
            (
                "writing_sample",
                {
                    "writing_sample": facts_have(
                        "writingSampleRequirements", "writingSample"
                    )
                },
                ["writingSampleRequirements|writingSample"],
            ),
            (
                "language",
                {"language": facts_have("languageRequirements")},
                ["languageRequirements"],
            ),
            (
                "methods_theory",
                {
                    "methods_theory": facts_have(
                        "methodsOrTheoryTraining", "methodsTraining"
                    )
                },
                ["methodsOrTheoryTraining|methodsTraining"],
            ),
            (
                "field_qualifying_exam",
                {
                    "field_qualifying_exam": facts_have(
                        "qualifyingOrFieldExamStructure", "fieldRequirements"
                    )
                },
                ["qualifyingOrFieldExamStructure|fieldRequirements"],
            ),
            (
                "teaching",
                {
                    "teaching": facts_have(
                        "teachingRequirements", "teachingLoad"
                    )
                    or outcomes_have("teachingPreparation")
                },
                ["teachingRequirements|teachingLoad|outcomes.teachingPreparation"],
            ),
            (
                "dissertation_fieldwork_support",
                {
                    "dissertation": facts_have("dissertationFormat"),
                    "fieldwork_support": facts_have(
                        "archiveFieldworkSupport",
                        "archiveSupport",
                        "fieldworkSupport",
                    ),
                },
                [
                    "dissertationFormat",
                    "archiveFieldworkSupport|archiveSupport|fieldworkSupport",
                ],
            ),
            (
                "placement_time_to_degree",
                {
                    "placement": outcomes_have(
                        "careerOutcomes",
                        "placement",
                        "placementTransparency",
                        "namedPlacements",
                        "placementYears",
                    ),
                    "time_to_degree": outcomes_have("timeToDegree")
                    or facts_have("timeToDegree"),
                },
                [
                    "outcomes.careerOutcomes|placement|placementTransparency|namedPlacements",
                    "outcomes.timeToDegree|facts.timeToDegree",
                ],
            ),
        ]
        for coverage, components, accepted_fields in groups:
            missing_components = [
                component
                for component, present in components.items()
                if not present
            ]
            if missing_components:
                self.add(
                    "warning",
                    "hss_coverage_missing",
                    path,
                    "Humanities/social-science coverage is incomplete for {}.".format(
                        coverage.replace("_", " ")
                    ),
                    coverage=coverage,
                    missing_components=missing_components,
                    accepted_fields=accepted_fields,
                )

    def _restaurant_container(self, program: Mapping[str, Any]) -> Tuple[Any, str]:
        if "nearbyFood" in program:
            return program.get("nearbyFood"), "nearbyFood"
        if "restaurants" in program:
            value = program.get("restaurants")
            if isinstance(value, Mapping):
                return value, "restaurants"
            return {"restaurants": value}, "restaurants"
        return None, "nearbyFood"

    def validate_restaurants(
        self,
        program: Mapping[str, Any],
        program_path: str,
        registry: Dict[str, List[Dict[str, Any]]],
    ) -> None:
        container, key = self._restaurant_container(program)
        container_path = _path_join(program_path, key)
        if container is None:
            return
        if not isinstance(container, Mapping):
            self.add(
                "error",
                "restaurants_type",
                container_path,
                "nearbyFood/restaurants must be an object or restaurant array.",
            )
            return
        if key == "nearbyFood":
            enabled = container.get("enabled")
            research_status = container.get("researchStatus")
            if "enabled" not in container:
                self.add(
                    "warning",
                    "nearby_food_enabled_missing",
                    _path_join(container_path, "enabled"),
                    "nearbyFood.enabled is missing.",
                )
            elif not isinstance(enabled, bool):
                self.add(
                    "error",
                    "boolean_invalid",
                    _path_join(container_path, "enabled"),
                    "nearbyFood.enabled must be true or false.",
                )
            if "researchStatus" not in container:
                self.add(
                    "warning",
                    "nearby_food_status_missing",
                    _path_join(container_path, "researchStatus"),
                    "nearbyFood.researchStatus is missing.",
                )
            elif research_status not in {
                "not_requested",
                "complete",
                "partial",
                "failed",
            }:
                self.add(
                    "error",
                    "nearby_food_status_invalid",
                    _path_join(container_path, "researchStatus"),
                    "nearbyFood.researchStatus has an invalid value.",
                    value=research_status,
                )
            elif isinstance(enabled, bool) and (
                (not enabled and research_status != "not_requested")
                or (enabled and research_status == "not_requested")
            ):
                self.add(
                    "error",
                    "nearby_food_status_inconsistent",
                    container_path,
                    "researchStatus must be not_requested iff nearby-food research is disabled.",
                    enabled=enabled,
                    researchStatus=research_status,
                )
        anchor = container.get("campusAnchor")
        if anchor is not None and not isinstance(anchor, Mapping):
            self.add(
                "error",
                "campus_anchor_type",
                _path_join(container_path, "campusAnchor"),
                "campusAnchor must be an object.",
            )
        elif isinstance(anchor, Mapping):
            if not _is_nonempty_string(anchor.get("name")):
                self.add(
                    "warning",
                    "campus_anchor_name_missing",
                    _path_join(container_path, "campusAnchor.name"),
                    "Campus anchor name is missing.",
                )
            if "sourceUrl" in anchor and anchor.get("sourceUrl"):
                self.check_url(
                    anchor.get("sourceUrl"),
                    _path_join(container_path, "campusAnchor.sourceUrl"),
                    severity="warning",
                )

        restaurants = container.get("restaurants")
        if not isinstance(restaurants, list):
            self.add(
                "error",
                "restaurants_list_type",
                _path_join(container_path, "restaurants"),
                "restaurants must be an array.",
            )
            return
        seen: Dict[str, str] = {}
        for index, restaurant in enumerate(restaurants):
            restaurant_path = _path_join(
                _path_join(container_path, "restaurants"), index
            )
            if not isinstance(restaurant, Mapping):
                self.add(
                    "error",
                    "restaurant_type",
                    restaurant_path,
                    "Each restaurant must be an object.",
                )
                continue
            self.restaurant_count += 1
            name = restaurant.get("name")
            if not _is_nonempty_string(name):
                self.add(
                    "error",
                    "restaurant_name_missing",
                    _path_join(restaurant_path, "name"),
                    "Restaurant name is required.",
                )
            else:
                duplicate_key = "|".join(
                    (
                        _identity_piece(name),
                        _identity_piece(restaurant.get("address")),
                    )
                )
                if duplicate_key in seen:
                    self.add(
                        "warning",
                        "restaurant_duplicate",
                        restaurant_path,
                        "The same restaurant is listed more than once.",
                        first_path=seen[duplicate_key],
                    )
                else:
                    seen[duplicate_key] = restaurant_path

            source_ids_value = restaurant.get(
                "sourceIds", restaurant.get("source_ids")
            )
            source_ids, source_records = self._resolve_source_ids(
                source_ids_value,
                _path_join(restaurant_path, "sourceIds"),
                registry,
            )
            direct_url = restaurant.get("url") or restaurant.get("sourceUrl")
            if direct_url:
                self.check_url(
                    direct_url,
                    _path_join(restaurant_path, "url"),
                    severity="warning",
                )
            if not source_ids and not direct_url and not restaurant.get("sources"):
                self.add(
                    "warning",
                    "restaurant_source_missing",
                    restaurant_path,
                    "Restaurant recommendations need a source URL or source ID.",
                )

            date_value = None
            date_key = "lastVerified"
            for candidate in ("lastVerified", "accessedAt", "checkedAt", "retrievedAt"):
                if restaurant.get(candidate):
                    date_key = candidate
                    date_value = restaurant.get(candidate)
                    break
            if date_value is None:
                source_dates = [
                    record.get("accessedAt")
                    for record in source_records
                    if record.get("accessedAt") is not None
                ]
                if not source_dates:
                    self.add(
                        "warning",
                        "restaurant_date_missing",
                        _path_join(restaurant_path, "lastVerified"),
                        "Restaurant recommendations need a verification/access date.",
                    )
            else:
                self.check_date(
                    date_value,
                    _path_join(restaurant_path, date_key),
                    required=True,
                    stale_days=548,
                )

    def validate_program(
        self,
        program: Any,
        path: str,
        floor: Any,
        currency: Any,
        root_registry: Dict[str, List[Dict[str, Any]]],
        seen_programs: Dict[str, str],
    ) -> None:
        if not isinstance(program, Mapping):
            self.add(
                "error",
                "program_type",
                path,
                "Each program must be an object.",
            )
            return
        self.program_count += 1
        missing_identity = False
        for field_name in ("school", "program"):
            if not _is_nonempty_string(program.get(field_name)):
                self.add(
                    "error",
                    "program_identity_missing",
                    _path_join(path, field_name),
                    "{} is required.".format(field_name),
                )
                missing_identity = True
        for field_name in ("region", "city"):
            if not _is_nonempty_string(program.get(field_name)):
                self.add(
                    "warning",
                    "program_field_missing",
                    _path_join(path, field_name),
                    "{} is missing.".format(field_name),
                )

        identifier = program_id(
            program.get("region"),
            program.get("school"),
            program.get("program"),
            program.get("campus", program.get("campusName", "")),
        )
        explicit_id = program.get("program_id", program.get("programId"))
        if explicit_id is not None and explicit_id != identifier:
            self.add(
                "warning",
                "program_id_mismatch",
                _path_join(path, "program_id"),
                "Stored program ID does not match the stable helper.",
                expected=identifier,
                actual=explicit_id,
            )
        if not missing_identity and identifier in seen_programs:
            self.add(
                "error",
                "program_duplicate",
                path,
                "The same region/school/program/campus combination is duplicated.",
                first_path=seen_programs[identifier],
                program_id=identifier,
            )
        else:
            seen_programs[identifier] = path

        registry: Dict[str, List[Dict[str, Any]]] = {
            key: list(values) for key, values in root_registry.items()
        }
        claim_support: Dict[str, List[str]] = {}
        self.scan_sources(program, path, registry, claim_support)
        self.scan_claims(program, path, registry, claim_support)

        facts = program.get("facts")
        self.validate_facts(
            facts,
            _path_join(path, "facts"),
            floor,
            currency,
            claim_support,
            registry,
        )
        faculty_key = (
            "faculty"
            if "faculty" in program
            else "pis"
            if "pis" in program
            else "advisors"
        )
        self.validate_advisors(
            program.get(faculty_key),
            _path_join(path, faculty_key),
            identifier,
            claim_support,
        )
        self.validate_verification(
            program.get("verification"),
            _path_join(path, "verification"),
        )
        self.validate_provenance(
            program.get("provenance"), _path_join(path, "provenance")
        )
        self.validate_hss_coverage(program, path)
        self.validate_restaurants(program, path, registry)

    def check_online_urls(self) -> None:
        url_items = list(self.urls.items())
        if len(url_items) > MAX_ONLINE_URLS:
            self.add(
                "warning",
                "url_check_limit",
                "$",
                "Online URL checking was capped to avoid an unbounded run.",
                checked=MAX_ONLINE_URLS,
                skipped=len(url_items) - MAX_ONLINE_URLS,
            )
            url_items = url_items[:MAX_ONLINE_URLS]
        deadline = time.monotonic() + ONLINE_GLOBAL_TIMEOUT_SECONDS
        for index, (url, path) in enumerate(url_items):
            if time.monotonic() >= deadline:
                self.add(
                    "warning",
                    "url_check_deadline",
                    "$",
                    "The global online-check deadline was reached.",
                    checked=index,
                    skipped=len(url_items) - index,
                )
                break
            reachable, status, error_text = _check_url_online(
                url,
                timeout=ONLINE_PER_URL_TIMEOUT_SECONDS,
                deadline=deadline,
            )
            if reachable:
                self.add(
                    "info",
                    "url_reachable",
                    path,
                    "URL responded successfully.",
                    url=url,
                    status=status,
                )
            else:
                code = (
                    "url_unsafe_skipped"
                    if error_text.startswith("unsafe ")
                    else "url_unreachable"
                )
                self.add(
                    "warning",
                    code,
                    path,
                    (
                        "URL was skipped because its target is not public."
                        if code == "url_unsafe_skipped"
                        else "URL could not be verified online."
                    ),
                    url=url,
                    status=status,
                    error=error_text,
                )

    def validate(self, data: Any) -> None:
        root: Mapping[str, Any]
        programs: Any
        root_path = "$"
        if isinstance(data, list):
            root = {}
            programs = data
            self.add(
                "info",
                "legacy_top_level_list",
                "$",
                "Accepted legacy top-level program array.",
            )
            floor = None
            currency = None
        elif isinstance(data, Mapping):
            if "programs" in data:
                root = data
                programs = data.get("programs")
            elif "result" in data and isinstance(data.get("result"), (list, Mapping)):
                self.add(
                    "info",
                    "workflow_wrapper_unwrapped",
                    "$.result",
                    "Unwrapped a workflow result envelope.",
                )
                nested = data.get("result")
                if isinstance(nested, list):
                    root = {}
                    programs = nested
                    root_path = "$.result"
                else:
                    root = nested
                    programs = nested.get("programs")
                    root_path = "$.result"
            else:
                self.add(
                    "error",
                    "programs_missing",
                    "$.programs",
                    "Top-level object must contain a programs array.",
                )
                return
            floor, currency = self.validate_root_metadata(root, root_path)
        else:
            self.add(
                "error",
                "root_type",
                "$",
                "Workflow result must be an object or a program array.",
            )
            return

        if not isinstance(programs, list):
            self.add(
                "error",
                "programs_type",
                _path_join(root_path, "programs"),
                "programs must be an array.",
            )
            return
        if not programs:
            self.add(
                "warning",
                "programs_empty",
                _path_join(root_path, "programs"),
                "No programs were returned.",
            )

        root_registry: Dict[str, List[Dict[str, Any]]] = {}
        root_claim_support: Dict[str, List[str]] = {}
        root_without_programs = {
            key: value for key, value in root.items() if key != "programs"
        }
        self.scan_sources(
            root_without_programs, root_path, root_registry, root_claim_support
        )
        self.scan_claims(
            root_without_programs, root_path, root_registry, root_claim_support
        )
        seen_programs: Dict[str, str] = {}
        for index, program in enumerate(programs):
            self.validate_program(
                program,
                _path_join(_path_join(root_path, "programs"), index),
                floor,
                currency,
                root_registry,
                seen_programs,
            )
        if self.online:
            self.check_online_urls()

    def report(self) -> Dict[str, Any]:
        errors = [issue for issue in self.issues if issue["severity"] == "error"]
        warnings = [
            issue for issue in self.issues if issue["severity"] == "warning"
        ]
        info = [issue for issue in self.issues if issue["severity"] == "info"]
        return {
            "schema_version": "2.0",
            "ok": not errors,
            "valid": not errors,
            "summary": {
                "programs": self.program_count,
                "advisors": self.advisor_count,
                "restaurants": self.restaurant_count,
                "sources": self.source_count,
                "claims": self.claim_count,
                "errors": len(errors),
                "warnings": len(warnings),
                "info": len(info),
                "online": self.online,
            },
            "errors": errors,
            "warnings": warnings,
            "info": info,
            "issues": list(self.issues),
        }


def _resolved_addresses(
    host: str, port: int, timeout: float
) -> Tuple[List[str], str]:
    """Resolve in a daemon thread so a slow resolver cannot defeat the deadline."""

    results: Queue = Queue(maxsize=1)

    def resolve() -> None:
        try:
            infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
            addresses = sorted({str(info[4][0]) for info in infos if info[4]})
            results.put((addresses, ""))
        except (OSError, UnicodeError, ValueError) as exc:
            results.put(([], str(exc)))

    Thread(target=resolve, daemon=True).start()
    try:
        return results.get(timeout=max(0.01, timeout))
    except Empty:
        return [], "DNS resolution timed out"


def _public_url_problem(url: str, timeout: float) -> Optional[str]:
    """Return why a URL must not be requested, or None for a public target."""

    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").rstrip(".").lower()
        port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
    except (TypeError, ValueError) as exc:
        return "unsafe target: invalid URL ({})".format(exc)
    if parsed.scheme.lower() not in {"http", "https"} or not host:
        return "unsafe target: only absolute HTTP(S) URLs are allowed"
    if host == "localhost" or host.endswith(".localhost"):
        return "unsafe target: localhost is not allowed"

    address_texts: List[str]
    try:
        literal = ipaddress.ip_address(host.split("%", 1)[0])
    except ValueError:
        address_texts, resolution_error = _resolved_addresses(host, port, timeout)
        if resolution_error:
            return "DNS preflight failed: {}".format(resolution_error)
        if not address_texts:
            return "DNS preflight failed: no addresses returned"
    else:
        address_texts = [str(literal)]

    for address_text in address_texts:
        try:
            address = ipaddress.ip_address(address_text.split("%", 1)[0])
        except ValueError:
            return "DNS preflight failed: invalid address {}".format(address_text)
        if not address.is_global:
            return "unsafe target: {} resolves to non-public address {}".format(
                host, address
            )
    return None


class _PublicOnlyRedirectHandler(HTTPRedirectHandler):
    """Apply the same public-address preflight to every redirect destination."""

    def __init__(self, deadline: float) -> None:
        super().__init__()
        self.deadline = deadline

    def redirect_request(
        self,
        req: Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> Optional[Request]:
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise URLError("global online-check deadline exceeded")
        problem = _public_url_problem(
            newurl, min(DNS_PREFLIGHT_TIMEOUT_SECONDS, remaining)
        )
        if problem:
            if problem.startswith("unsafe "):
                raise URLError(
                    "unsafe redirect target: {}".format(problem[len("unsafe target: ") :])
                )
            raise URLError("redirect {}".format(problem))
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _check_url_online(
    url: str,
    timeout: float = ONLINE_PER_URL_TIMEOUT_SECONDS,
    deadline: Optional[float] = None,
) -> Tuple[bool, Optional[int], str]:
    """Safely check one public URL; GET is a fallback for HEAD-hostile sites."""

    if deadline is None:
        deadline = time.monotonic() + max(timeout * 2, timeout)
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        return False, None, "global online-check deadline exceeded"
    problem = _public_url_problem(
        url, min(DNS_PREFLIGHT_TIMEOUT_SECONDS, remaining)
    )
    if problem:
        return False, None, problem

    last_status: Optional[int] = None
    last_error = ""
    opener = build_opener(_PublicOnlyRedirectHandler(deadline))
    for method in ("HEAD", "GET"):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False, last_status, "global online-check deadline exceeded"
        headers = {
            "User-Agent": "phd-application-planner-data-check/2.0",
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.1",
        }
        if method == "GET":
            headers["Range"] = "bytes=0-0"
        request = Request(url, headers=headers, method=method)
        try:
            with opener.open(request, timeout=min(timeout, remaining)) as response:
                status = getattr(response, "status", None) or response.getcode()
                if status is None or 200 <= int(status) < 400:
                    return True, int(status) if status is not None else None, ""
                last_status = int(status)
                last_error = "HTTP {}".format(status)
        except HTTPError as exc:
            last_status = int(exc.code)
            last_error = "HTTP {}".format(exc.code)
            if method == "HEAD" and exc.code in {400, 403, 405, 429, 501}:
                continue
            return False, last_status, last_error
        except (URLError, TimeoutError, OSError, ValueError) as exc:
            last_error = str(getattr(exc, "reason", exc))
            if last_error.startswith("unsafe "):
                return False, last_status, last_error
            if method == "HEAD":
                continue
            return False, last_status, last_error
    return False, last_status, last_error or "No response"


def validate_result(data: Any, *, online: bool = False) -> Dict[str, Any]:
    """Validate a parsed workflow result and return a JSON-serializable report.

    The input is never mutated.  Structural/type contradictions are errors;
    missing provenance in legacy data is generally a warning so old result files
    remain usable while clearly showing what should be refreshed.
    """

    validator = _Validator(online=online)
    validator.validate(data)
    return validator.report()


__all__ = [
    "APPLICATION_POLICY_VALUES",
    "advisor_id",
    "program_id",
    "validate_result",
]
