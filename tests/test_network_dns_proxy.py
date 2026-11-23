import socket
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from beyondseo.diagnostics import failure_detail
from beyondseo.network import addresses


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
            with self.assertRaises(ValueError) as caught:
                addresses("https://example.com/")
        self.assertEqual(str(caught.exception), "dns_resolution_failed_with_proxy_configured")

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
    def test_named_dns_proxy_failure_classifies_specifically(self):
        detail = failure_detail("ValueError: dns_resolution_failed_with_proxy_configured")
        self.assertIsNotNone(detail)
        self.assertEqual(detail["code"], "dns_failure_proxy_configured")

    def test_plain_dns_failure_still_classifies_as_dns_failure(self):
        detail = failure_detail("gaierror: Temporary failure in name resolution")
        self.assertIsNotNone(detail)
        self.assertEqual(detail["code"], "dns_failure")


if __name__ == "__main__":
    unittest.main()
