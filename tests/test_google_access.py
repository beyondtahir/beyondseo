"""Read-only Google transport, consent and evidence contracts without account access."""

import contextlib
import csv
import io
import json
import socket
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit

from beyondseo import google_access as google
from beyondseo.cli import main
from beyondseo.review import lighthouse_review, search_performance


class GoogleAccessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_status_does_not_call_google_or_assume_browser_and_property_access(self):
        with patch.object(google, "request", side_effect=AssertionError("no request")):
            result = google.status(self.root / "state")
        self.assertEqual(result["status"], "not_connected")
        self.assertIn("not_tested", result["property_access"])
        self.assertIn("independent", result["search_access"])
        self.assertFalse((self.root / "state").exists())

    def test_missing_and_wrong_scopes_do_not_attempt_refresh(self):
        with self.assertRaises(google.GoogleFailure) as missing:
            google.credentials(self.root, "analytics")
        self.assertEqual(missing.exception.reason, "not_connected")
        (self.root / "token.json").write_text(
            json.dumps(
                {
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "scopes": [google.SCOPES["search-console"]],
                }
            )
        )
        with self.assertRaises(google.GoogleFailure) as wrong:
            google.credentials(self.root, "analytics")
        self.assertEqual(wrong.exception.reason, "scope_missing")

    def test_untrusted_oauth_endpoints_rejected_before_import_or_browser(self):
        path = self.root / "client.json"
        path.write_text(
            json.dumps(
                {
                    "installed": {
                        "client_id": "test",
                        "auth_uri": "https://example.com/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                    }
                }
            )
        )
        with self.assertRaisesRegex(ValueError, "standard endpoints"):
            google.connect(path, self.root / "state")
        self.assertFalse((self.root / "state").exists())

    def test_consent_requests_only_selected_readonly_service_and_saves_no_output_token(self):
        config = {
            "installed": {
                "client_id": "test",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        }
        path = self.root / "client.json"
        path.write_text(json.dumps(config))
        creds = Mock()
        creds.to_json.return_value = json.dumps(
            {"token": "synthetic-private-value", "scopes": [google.SCOPES["analytics"]]}
        )
        creds.has_scopes.return_value = True
        creds.granted_scopes = [google.SCOPES["analytics"]]
        flow = Mock()
        flow.run_local_server.return_value = creds
        # google-auth-oauthlib sets flow.credentials as part of run_local_server.
        flow.credentials = creds
        factory = Mock(return_value=flow)
        module = SimpleNamespace(InstalledAppFlow=SimpleNamespace(from_client_config=factory))
        with patch.dict("sys.modules", {"google_auth_oauthlib.flow": module}):
            result = google.connect(path, self.root / "state", ["analytics"], "chrome")
        self.assertEqual(factory.call_args.kwargs["scopes"], [google.SCOPES["analytics"]])
        self.assertTrue(factory.call_args.kwargs["autogenerate_code_verifier"])
        self.assertEqual(flow.run_local_server.call_args.kwargs["host"], "127.0.0.1")
        self.assertEqual(flow.run_local_server.call_args.kwargs["browser"], "chrome")
        self.assertEqual(result["property_access"], "not_tested")
        self.assertNotIn("synthetic-private-value", json.dumps(result))
        self.assertTrue((self.root / "state/token.json").is_file())

    def test_granular_consent_preserves_actual_grants_instead_of_requested_scopes(self):
        config = {
            "installed": {
                "client_id": "test",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        }
        path = self.root / "partial-client.json"
        path.write_text(json.dumps(config))
        requested = list(google.SCOPES.values())
        granted = [google.SCOPES["search-console"]]
        creds = Mock()
        # This mirrors the official library: has_scopes can be true while
        # granted_scopes records a narrower actual Google consent.
        creds.has_scopes.return_value = True
        creds.granted_scopes = granted
        creds.to_json.return_value = json.dumps(
            {
                "token": "synthetic-private-value",
                "token_uri": "https://oauth2.googleapis.com/token",
                "scopes": requested,
            }
        )
        flow = Mock()
        flow.run_local_server.return_value = creds
        module = SimpleNamespace(
            InstalledAppFlow=SimpleNamespace(from_client_config=Mock(return_value=flow))
        )
        state = self.root / "partial-state"
        with patch.dict("sys.modules", {"google_auth_oauthlib.flow": module}):
            result = google.connect(path, state)
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["provider_observed_granted_services"], ["search-console"])
        self.assertEqual(result["requested_services"], ["search-console", "analytics"])
        creds.has_scopes.assert_not_called()
        saved = json.loads((state / "token.json").read_text())
        self.assertEqual(saved["scopes"], granted)
        self.assertEqual(saved["beyondseo_requested_scopes"], requested)
        self.assertEqual(saved["beyondseo_granted_scopes"], granted)
        self.assertNotIn("synthetic-private-value", json.dumps(result))
        status = google.status(state)
        self.assertEqual(status["provider_observed_granted_services"], ["search-console"])
        self.assertEqual(status["saved_service_scopes"], ["search-console"])
        with self.assertRaises(google.GoogleFailure) as failure:
            google.credentials(state, "analytics")
        self.assertEqual(failure.exception.reason, "scope_missing")

    def test_scope_refresh_preserves_prior_observation_without_inventing_new_consent(self):
        requested = list(google.SCOPES.values())
        granted = [google.SCOPES["search-console"]]
        previous = {
            "beyondseo_granted_scopes": granted,
            "beyondseo_scope_observed_at": "2026-10-01T00:00:00+00:00",
        }
        creds = Mock()
        creds.granted_scopes = None
        creds.to_json.return_value = json.dumps({"scopes": requested})
        result = google.scope_record(creds, requested, previous)
        self.assertEqual(result["scopes"], granted)
        self.assertEqual(result["beyondseo_scope_evidence"], "previous_provider_observation")
        self.assertEqual(
            result["beyondseo_scope_observed_at"], previous["beyondseo_scope_observed_at"]
        )
        unobserved = google.scope_record(creds, requested)
        self.assertIsNone(unobserved["beyondseo_granted_scopes"])
        self.assertEqual(unobserved["beyondseo_scope_evidence"], "not_returned")
        creds.granted_scopes = []
        denied = google.scope_record(creds, requested, previous)
        self.assertEqual(denied["scopes"], [])
        self.assertEqual(denied["beyondseo_scope_evidence"], "provider_returned")

    def test_properties_can_be_partial_without_faking_all_google_access(self):
        with patch.object(
            google,
            "request",
            side_effect=[
                {"siteEntry": [{"siteUrl": "https://example.com/"}]},
                google.GoogleFailure("scope_missing", "Connect Analytics"),
            ],
        ):
            result = google.properties(self.root)
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["services"]["search-console"]["status"], "verified")
        self.assertEqual(result["services"]["analytics"]["reason"], "scope_missing")

    def test_installed_google_library_accepts_the_native_flow_configuration(self):
        try:
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
        except ImportError:
            self.skipTest("Optional Google extra is not installed")
        config = {
            "installed": {
                "client_id": "synthetic.apps.googleusercontent.com",
                "client_secret": "synthetic",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost"],
            }
        }
        path = self.root / "client.json"
        path.write_text(json.dumps(config))
        creds = Credentials(
            "synthetic-token",
            refresh_token="synthetic-refresh",
            client_id=config["installed"]["client_id"],
            client_secret="synthetic",
            token_uri=config["installed"]["token_uri"],
            scopes=[google.SCOPES["search-console"]],
        )
        # Use the real library's configuration and credentials serialization while
        # replacing the interactive callback; this is not a live Google sign-in.
        with patch.object(InstalledAppFlow, "run_local_server", return_value=creds) as callback:
            result = google.connect(path, self.root / "native-state", ["search-console"])
        self.assertEqual(result["status"], "credentials_saved")
        self.assertEqual(callback.call_args.kwargs["timeout_seconds"], 180)
        self.assertNotIn("synthetic-token", json.dumps(result))

    def test_empty_results_and_malformed_rows_are_different(self):
        with patch.object(google, "request", return_value={}):
            result = google.search_console(
                self.root,
                "sc-domain:example.com",
                "2026-10-01",
                "2026-10-07",
                "page",
                self.root / "empty",
            )
        self.assertEqual(result["status"], "no_results")
        with patch.object(google, "request", return_value={"rows": [{"keys": ["a"]}]}):
            with self.assertRaises(google.GoogleFailure) as error:
                google.search_console(
                    self.root,
                    "sc-domain:example.com",
                    "2026-10-01",
                    "2026-10-07",
                    "page",
                    self.root / "bad",
                )
        self.assertEqual(error.exception.reason, "parsing_failed")
        self.assertFalse((self.root / "bad").exists())

    def test_search_console_export_is_consumed_by_existing_review_without_invented_totals(self):
        data = {
            "rows": [
                {
                    "keys": ["https://example.com/service"],
                    "clicks": 2,
                    "impressions": 200,
                    "ctr": 0.01,
                    "position": 7.2,
                }
            ]
        }
        with patch.object(google, "request", return_value=data) as call:
            result = google.search_console(
                self.root,
                "https://example.com/",
                "2026-10-01",
                "2026-10-07",
                "page",
                self.root / "report",
            )
        self.assertEqual(call.call_args.args[3]["dataState"], "final")
        self.assertIn("https%3A%2F%2Fexample.com%2F", call.call_args.args[2])
        with (self.root / "report/search-console.csv").open() as stream:
            self.assertEqual(list(csv.DictReader(stream))[0]["CTR"], "1.000000%")
        review = search_performance(
            self.root / "report/search-console.csv", self.root / "review", "page"
        )
        self.assertEqual(review["input_rows"], 1)
        self.assertIn("not guaranteed", result["coverage"])

    def test_analytics_request_is_organic_and_retains_provider_metadata(self):
        response = {
            "rows": [
                {
                    "dimensionValues": [{"value": "/service"}],
                    "metricValues": [{"value": "20"}, {"value": "15"}, {"value": "2"}],
                }
            ],
            "metadata": {"subjectToThresholding": True},
        }
        with patch.object(google, "request", return_value=response) as call:
            result = google.analytics(
                self.root, "12345", "2026-10-01", "2026-10-07", self.root / "analytics"
            )
        payload = call.call_args.args[3]
        self.assertEqual(
            payload["dimensionFilter"]["filter"]["stringFilter"]["value"], "Organic Search"
        )
        saved = json.loads((self.root / "analytics/analytics.json").read_text())
        self.assertTrue(saved["raw"]["metadata"]["subjectToThresholding"])
        self.assertIn("tracking configuration", result["coverage"])

    def test_denial_dns_and_http_restriction_preserve_distinct_causes_and_hide_tokens(self):
        errors = [
            (PermissionError("private"), "execution_denied"),
            (URLError(socket.gaierror("private")), "dns_failure"),
            (
                HTTPError("https://example.com", 403, "synthetic-secret", {}, None),
                "access_or_api_restriction",
            ),
        ]
        for error, reason in errors:
            with (
                self.subTest(reason=reason),
                patch.object(
                    google, "credentials", return_value=SimpleNamespace(token="synthetic-secret")
                ),
                patch.object(
                    google,
                    "build_opener",
                    return_value=SimpleNamespace(open=Mock(side_effect=error)),
                ),
            ):
                with self.assertRaises(google.GoogleFailure) as failure:
                    google.request(self.root, "search-console", google.ENDPOINTS["sites"])
                self.assertEqual(failure.exception.reason, reason)
                self.assertNotIn("synthetic-secret", json.dumps(failure.exception.result()))

    def test_cli_disconnection_is_explicit_about_local_removal(self):
        (self.root / "token.json").write_text("{}")
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["google", "disconnect", "--state-dir", str(self.root)]), 0)
        self.assertIn("local_credentials_removed", output.getvalue())
        self.assertFalse((self.root / "token.json").exists())

    def public_response(self, data):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=None)
        response.read.return_value = json.dumps(data).encode()
        return SimpleNamespace(open=Mock(return_value=response))

    def lab_report(self):
        return {
            "lighthouseResult": {
                "requestedUrl": "https://example.com/",
                "finalUrl": "https://example.com/",
                "lighthouseVersion": "12.0.0",
                "fetchTime": "2026-10-30T00:00:00Z",
                "audits": {
                    "largest-contentful-paint": {
                        "numericValue": 2100,
                        "numericUnit": "millisecond",
                        "scoreDisplayMode": "numeric",
                    }
                },
                "categories": {"performance": {"score": 0.8}},
            }
        }

    def test_pagespeed_is_one_unauthenticated_fixed_endpoint_call_and_real_review_input(self):
        opener = self.public_response(self.lab_report())
        with (
            patch.object(
                google, "credentials", side_effect=AssertionError("No OAuth for public PSI")
            ),
            patch.object(google, "build_opener", return_value=opener),
        ):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                code = main(
                    [
                        "google",
                        "pagespeed",
                        "--url",
                        "https://example.com",
                        "--strategy",
                        "desktop",
                        "--out",
                        str(self.root / "psi"),
                    ]
                )
        self.assertEqual(code, 0)
        result = json.loads(output.getvalue())
        self.assertEqual(result["status"], "observed")
        self.assertEqual(result["field_data"], "not assessed")
        opener.open.assert_called_once()
        req = opener.open.call_args.args[0]
        self.assertEqual(urlsplit(req.full_url).hostname, "www.googleapis.com")
        self.assertNotIn("Authorization", req.headers)
        self.assertNotIn("key", parse_qs(urlsplit(req.full_url).query))
        self.assertEqual(parse_qs(urlsplit(req.full_url).query)["strategy"], ["desktop"])
        self.assertEqual(opener.open.call_args.kwargs["timeout"], 45)
        review = lighthouse_review(self.root / "psi/lighthouse.json", self.root / "lab-review")
        self.assertEqual(
            next(m for m in review["metrics"] if m["id"] == "largest-contentful-paint")["value"],
            2100,
        )
        saved = json.loads((self.root / "psi/pagespeed-attempt.json").read_text())
        self.assertEqual(saved["limits"]["requests_attempted"], 1)

    def test_pagespeed_rejects_private_and_credential_targets_without_network(self):
        targets = [
            "http://localhost",
            "https://thing.localhost",
            "http://127.0.0.1",
            "http://10.0.0.1",
            "http://[::1]",
            "http://[::ffff:127.0.0.1]",
            "http://2130706433",
            "http://0x7f.0.0.1",
            "https://user:password@example.com",
        ]
        with patch.object(google, "build_opener", side_effect=AssertionError("no request")):
            for target in targets:
                with self.subTest(target=target), self.assertRaises(ValueError):
                    google.pagespeed(target, "mobile", self.root / "invalid")
        self.assertFalse((self.root / "invalid").exists())

    def test_pagespeed_quota_and_denial_preserve_actual_status_and_provider_evidence(self):
        for code, reason in [
            (429, "quota_or_rate_limited"),
            (403, "provider_access_denied"),
            (302, "provider_redirect_denied"),
        ]:
            error_body = {
                "error": {
                    "code": code,
                    "message": "Synthetic provider restriction",
                    "status": "RESOURCE_EXHAUSTED",
                }
            }
            error = HTTPError(
                google.PSI_ENDPOINT,
                code,
                "Synthetic",
                {},
                io.BytesIO(json.dumps(error_body).encode()),
            )
            with (
                self.subTest(code=code),
                patch.object(
                    google,
                    "build_opener",
                    return_value=SimpleNamespace(open=Mock(side_effect=error)),
                ),
            ):
                result = google.pagespeed("https://example.com", "mobile", self.root / str(code))
            self.assertEqual(result["status"], "unavailable")
            self.assertEqual(result["reason"], reason)
            self.assertEqual(result["http_status"], code)
            self.assertEqual(result["provider_error"]["message"], "Synthetic provider restriction")
            self.assertIn("saved-report", result["action"])
            self.assertFalse((self.root / str(code) / "lighthouse.json").exists())

    def test_pagespeed_malformed_mismatched_and_runtime_failed_reports_never_pass(self):
        malformed = {"lighthouseResult": {"audits": []}}
        mismatched = self.lab_report()
        mismatched["lighthouseResult"]["requestedUrl"] = "https://other.example/"
        runtime = self.lab_report()
        runtime["lighthouseResult"]["runtimeError"] = {
            "code": "NO_FCP",
            "message": "No content painted",
        }
        for index, (payload, reason) in enumerate(
            [
                (malformed, "parsing_failed"),
                (mismatched, "report_target_mismatch"),
                (runtime, "lighthouse_runtime_error"),
            ]
        ):
            with (
                self.subTest(reason=reason),
                patch.object(google, "build_opener", return_value=self.public_response(payload)),
            ):
                result = google.pagespeed(
                    "https://example.com", "mobile", self.root / f"bad-{index}"
                )
            self.assertEqual(result["status"], "unavailable")
            self.assertEqual(result["reason"], reason)
            self.assertEqual(result["http_status"], 200)
        self.assertTrue((self.root / "bad-2/lighthouse.json").exists())

    def test_pagespeed_network_and_parsing_failure_are_not_target_performance_findings(self):
        cases = [
            (URLError(socket.gaierror("Synthetic DNS failure")), "dns_failure"),
            (PermissionError("Synthetic denial"), "execution_denied"),
        ]
        for index, (error, reason) in enumerate(cases):
            with patch.object(
                google, "build_opener", return_value=SimpleNamespace(open=Mock(side_effect=error))
            ):
                result = google.pagespeed(
                    "https://example.com", "mobile", self.root / f"network-{index}"
                )
            self.assertEqual(result["reason"], reason)
            self.assertEqual(result["status"], "unavailable")
            self.assertNotIn("lighthouse_version", result)
            self.assertTrue((self.root / f"network-{index}/pagespeed-attempt.json").exists())

    def test_pagespeed_invalid_json_and_response_budget_do_not_create_measurements(self):
        for index, (body, reason) in enumerate(
            [(b"not a report", "parsing_failed"), (b"x" * (google.PSI_LIMIT + 1), "response_limit")]
        ):
            opener = self.public_response({})
            opener.open.return_value.read.return_value = body
            with patch.object(google, "build_opener", return_value=opener):
                result = google.pagespeed(
                    "https://example.com", "mobile", self.root / f"body-{index}"
                )
            self.assertEqual(result["status"], "unavailable")
            self.assertEqual(result["reason"], reason)
            opener.open.return_value.read.assert_called_once_with(google.PSI_LIMIT + 1)
            self.assertFalse((self.root / f"body-{index}/lighthouse.json").exists())


if __name__ == "__main__":
    unittest.main()
