import contextlib
import io
import json
import socket
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from beyondseo.diagnostics import failure_detail
from beyondseo.network import Config, Transport, addresses


def _gaierror(*args, **kwargs):
    raise socket.gaierror(-3, "Temporary failure in name resolution")


class AddressesProxyDnsTests(unittest.TestCase):
    def test_dns_failure_with_proxy_configured_is_named(self):
        with (
            patch("beyondseo.network.socket.getaddrinfo", _gaierror),
            patch(
                "beyondseo.network.getproxies_environment",
                return_value={"https": "http://proxy.example:8080"},
            ),
            patch(
                "beyondseo.network.proxy_bypass_environment",
                return_value=False,
            ),
        ):
            with self.assertRaises(socket.gaierror) as caught:
                addresses("https://example.com/")
        self.assertIn("dns_resolution_failed_with_proxy_configured", str(caught.exception))
        self.assertIn("Temporary failure in name resolution", str(caught.exception))
        self.assertNotIn("proxy.example", str(caught.exception))

    def test_dns_failure_without_proxy_stays_a_gaierror(self):
        with (
            patch("beyondseo.network.socket.getaddrinfo", _gaierror),
            patch("beyondseo.network.getproxies_environment", return_value={}),
        ):
            with self.assertRaises(socket.gaierror):
                addresses("https://example.com/")

    def test_dns_failure_with_proxy_bypassed_stays_a_gaierror(self):
        with (
            patch("beyondseo.network.socket.getaddrinfo", _gaierror),
            patch(
                "beyondseo.network.getproxies_environment",
                return_value={"https": "http://proxy.example:8080"},
            ),
            patch(
                "beyondseo.network.proxy_bypass_environment",
                return_value=True,
            ),
        ):
            with self.assertRaises(socket.gaierror):
                addresses("https://example.com/")


class FailureDetailProxyDnsTests(unittest.TestCase):
    def test_proxy_dns_annotation_preserves_bounded_retry(self):
        transient = socket.gaierror(-3, "dns_resolution_failed_with_proxy_configured: temporary")
        transport = Transport(Config("https://example.com", delay=0, retries=1))
        with (
            patch.object(transport, "once", side_effect=[transient, (200, {}, b"ok")]) as once,
            patch("beyondseo.network.time.sleep"),
        ):
            response = transport.fetch("https://example.com/")
        self.assertEqual(once.call_count, 2)
        self.assertEqual(response.status, 200)
        self.assertEqual(response.attempts, 2)
        self.assertIn(
            "dns_resolution_failed_with_proxy_configured", response.http_events[0]["error"]
        )

    def test_doctor_keeps_exact_failure_and_specific_remediation(self):
        from beyondseo.doctor import check_environment

        transient = socket.gaierror(-3, "dns_resolution_failed_with_proxy_configured: temporary")
        stdout = io.StringIO()
        with (
            tempfile.TemporaryDirectory() as folder,
            patch("beyondseo.network.addresses", side_effect=transient),
            contextlib.redirect_stdout(stdout),
        ):
            code = check_environment("https://example.com", out=folder, check_browser=False)
        report = json.loads(stdout.getvalue())
        target = report["checks"]["target_reachable"]
        self.assertEqual(code, 1)
        self.assertEqual(target["status"], "dns_failure_proxy_configured")
        self.assertIn("temporary", target["failure"]["evidence"])
        self.assertIn("Installing Chromium", target["remediation"])
        self.assertEqual(report["runtime_checks"]["target_http"]["status"], "NOT_TESTED")

    def test_named_dns_proxy_failure_classifies_specifically(self):
        detail = failure_detail("ValueError: dns_resolution_failed_with_proxy_configured")
        self.assertIsNotNone(detail)
        self.assertEqual(detail["code"], "dns_failure_proxy_configured")

    def test_plain_dns_failure_still_classifies_as_dns_failure(self):
        for message in (
            "Temporary failure in name resolution",
            "Could not resolve host: github.com",
        ):
            with self.subTest(message=message):
                detail = failure_detail(message)
                self.assertEqual(detail["code"], "dns_failure")
                self.assertEqual(detail["evidence"], message)

    def test_doctor_suggests_existing_browser_after_work_dns_failure(self):
        from beyondseo.doctor import check_environment

        stdout = io.StringIO()
        with (
            tempfile.TemporaryDirectory() as folder,
            patch(
                "beyondseo.network.addresses",
                side_effect=socket.gaierror(-3, "Temporary failure in name resolution"),
            ),
            contextlib.redirect_stdout(stdout),
        ):
            code = check_environment("https://example.com", out=folder, check_browser=False)
        target = json.loads(stdout.getvalue())["checks"]["target_reachable"]
        self.assertEqual(code, 1)
        self.assertEqual(target["status"], "dns_failure")
        self.assertIn("host browser", target["remediation"])
        self.assertIn("Reinstalling Chromium does not repair", target["remediation"])


if __name__ == "__main__":
    unittest.main()
