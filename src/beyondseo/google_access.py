"""Optional, read-only Google account access. No browser cookies or embedded credentials."""

from __future__ import annotations

import csv
import importlib.util
import io
import ipaddress
import json
import math
import os
import re
import shutil
import socket
import ssl
import webbrowser
from datetime import date
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .network import normalize_url, utcnow
from .projects import write_private

SCOPES = {
    "search-console": "https://www.googleapis.com/auth/webmasters.readonly",
    "analytics": "https://www.googleapis.com/auth/analytics.readonly",
}
ENDPOINTS = {
    "sites": "https://www.googleapis.com/webmasters/v3/sites",
    "accounts": "https://analyticsadmin.googleapis.com/v1beta/accountSummaries",
    "analytics": "https://analyticsdata.googleapis.com/v1beta/properties/",
}
LIMIT = 2_000_000
PSI_ENDPOINT = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
PSI_LIMIT = 5_000_000


class GoogleFailure(ValueError):
    def __init__(self, reason, action, http_status=None):
        super().__init__(action)
        self.reason, self.action, self.http_status = reason, action, http_status

    def result(self):
        return {
            "status": "unavailable",
            "reason": self.reason,
            "action": self.action,
            "http_status": self.http_status,
        }


def state_path(value=None):
    path = (
        Path(
            value or os.getenv("BEYONDSEO_GOOGLE_HOME") or Path.home() / ".config/beyondseo/google"
        )
        .expanduser()
        .absolute()
    )
    if path.resolve().is_relative_to(Path(__file__).resolve().parents[2]):
        raise ValueError("Keep Google credentials outside the BeyondSEO source/skill folder.")
    if path.is_symlink():
        raise ValueError("Google state folder must not be a symlink.")
    return path


def load_json(path):
    path = Path(path)
    if path.is_symlink() or path.stat().st_size > LIMIT:
        raise ValueError("Use a regular Google input file smaller than 2 MB.")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Google input must be a JSON object.")
    return data


def save(path, data):
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    write_private(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def scope_record(credentials, requested, previous=None):
    """Keep requested scopes separate from provider-observed granted scopes.

    Credentials.has_scopes() checks the requested scopes, so it cannot establish
    granular consent. to_json() also omits granted_scopes and must be augmented.
    A refresh that omits scope retains the last observed grant, not a new proof.
    """
    data = json.loads(credentials.to_json())
    granted = credentials.granted_scopes
    if isinstance(granted, str):
        granted = granted.split()
    if not isinstance(granted, (list, tuple)) or any(not isinstance(s, str) for s in granted):
        granted = None
    if granted is not None:
        granted = list(dict.fromkeys(granted))
        evidence = "provider_returned"
        observed_at = utcnow()
    elif previous and isinstance(previous.get("beyondseo_granted_scopes"), list):
        granted = previous["beyondseo_granted_scopes"]
        evidence = "previous_provider_observation"
        observed_at = previous.get("beyondseo_scope_observed_at")
    else:
        evidence, observed_at = "not_returned", None
    data["scopes"] = granted if granted is not None else list(requested)
    data["beyondseo_requested_scopes"] = list(requested)
    data["beyondseo_granted_scopes"] = granted
    data["beyondseo_scope_evidence"] = evidence
    data["beyondseo_scope_observed_at"] = observed_at
    return data


def status(folder=None):
    folder = state_path(folder)
    try:
        dependencies = importlib.util.find_spec("google_auth_oauthlib") is not None
    except (ImportError, ValueError):
        dependencies = False
    token = folder / "token.json"
    services = []
    granted_services, requested_services, scope_evidence = [], [], "not_tested"
    if token.exists():
        data = load_json(token)
        services = [s for s, scope in SCOPES.items() if scope in data.get("scopes", [])]
        requested = data.get("beyondseo_requested_scopes", data.get("scopes", []))
        requested_services = [s for s, scope in SCOPES.items() if scope in requested]
        granted = data.get("beyondseo_granted_scopes")
        if isinstance(granted, list):
            granted_services = [s for s, scope in SCOPES.items() if scope in granted]
        scope_evidence = data.get("beyondseo_scope_evidence", "legacy_requested_only")
    return {
        "status": "credentials_saved" if token.exists() else "not_connected",
        "optional_dependencies_ready": dependencies,
        "saved_service_scopes": services,
        "requested_services": requested_services,
        "provider_observed_granted_services": granted_services,
        "scope_evidence": scope_evidence,
        "property_access": "not_tested; run google properties",
        "gog_available": shutil.which("gog") is not None,
        "host_connector_access": "inspect the host's actual tools separately",
        "browser_access": "inspect the host's permitted browser separately",
        "search_access": "independent of Search Console and Analytics authorization",
        "next_step": "Use an existing suitable host connection, or google connect --client-json FILE. Optional runtime: python -m pip install -e '.[google]'. Browser exports and CSV remain supported.",
    }


def connect(client_path, folder=None, services=None, browser=None):
    folder = state_path(folder)
    if (folder / "token.json").exists():
        raise ValueError(
            "Credentials already exist. Use them or disconnect before changing account/scopes."
        )
    services = list(dict.fromkeys(services or SCOPES))
    if not services or any(s not in SCOPES for s in services):
        raise ValueError("Choose search-console and/or analytics.")
    config = load_json(client_path)
    installed = config.get("installed", {})
    if (
        not isinstance(installed, dict)
        or not installed.get("client_id")
        or installed.get("auth_uri") != "https://accounts.google.com/o/oauth2/auth"
        or installed.get("token_uri") != "https://oauth2.googleapis.com/token"
    ):
        raise ValueError("Use a Google Desktop OAuth client JSON with Google's standard endpoints.")
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        raise GoogleFailure(
            "missing_dependencies",
            "Install the optional google extra in the engine runtime: python -m pip install -e '.[google]'.",
        ) from None
    try:
        flow = InstalledAppFlow.from_client_config(
            config, scopes=[SCOPES[s] for s in services], autogenerate_code_verifier=True
        )
        original_request = flow.oauth2session.request

        def bounded_request(*args, **kwargs):
            kwargs["timeout"] = 20
            return original_request(*args, **kwargs)

        flow.oauth2session.request = bounded_request
        options = {
            "host": "127.0.0.1",
            "port": 0,
            "open_browser": True,
            "timeout_seconds": 180,
            "access_type": "offline",
            "prompt": "consent",
            "authorization_prompt_message": "Complete Google consent in the browser opened for this request.",
            "success_message": "BeyondSEO received the Google response. Return to your agent to check property access.",
        }
        if browser:
            options["browser"] = browser
        credentials = flow.run_local_server(**options)
        requested_scopes = [SCOPES[s] for s in services]
        data = scope_record(credentials, requested_scopes)
    except GoogleFailure:
        raise
    except PermissionError:
        raise GoogleFailure(
            "execution_denied",
            "The host denied local browser or callback execution. Use an approved connector or browser export.",
        ) from None
    except webbrowser.Error:
        raise GoogleFailure(
            "browser_unavailable",
            "No supported browser could be opened in this runtime. Use the host's approved browser/connector or an exported report.",
        ) from None
    except Exception:
        # OAuth exceptions may contain authorization codes, client secrets or tokens.
        raise GoogleFailure(
            "authorization_incomplete",
            "Google sign-in did not complete. Check consent, client configuration and whether this runtime can receive its local callback. Use a host connector or exports in cloud-only environments.",
        ) from None
    save(folder / "token.json", data)
    granted = data["beyondseo_granted_scopes"]
    granted_services = (
        [s for s, scope in SCOPES.items() if scope in granted] if granted is not None else []
    )
    partial = granted is not None and not set(requested_scopes).issubset(granted)
    return {
        "status": "partial" if partial else "credentials_saved",
        "credentials_saved": True,
        "requested_services": services,
        "provider_observed_granted_services": granted_services,
        "scope_evidence": data["beyondseo_scope_evidence"],
        "property_access": "not_tested",
        "next_step": "Run google properties to verify actual account access. A partial grant remains usable for granted services; reconnect separately for missing services. When scope was not returned, requested scopes are provisional until a service request succeeds. Credentials alone do not establish property access.",
    }


def credentials(folder, service):
    if service not in SCOPES:
        raise ValueError("Unknown Google service.")
    path = state_path(folder) / "token.json"
    if not path.exists():
        raise GoogleFailure(
            "not_connected",
            "Use an authorised host connector, google connect, or an exported report.",
        )
    data = load_json(path)
    if data.get("token_uri") != "https://oauth2.googleapis.com/token":
        raise ValueError("Unexpected token endpoint; reconnect with a valid Google client.")
    granted = data.get("beyondseo_granted_scopes")
    effective_scopes = granted if isinstance(granted, list) else data.get("scopes", [])
    if SCOPES[service] not in effective_scopes:
        raise GoogleFailure(
            "scope_missing",
            "This saved connection does not include "
            + service
            + ". Use a separate state folder or reconnect with that read-only service.",
        )
    try:
        from google.auth.transport.requests import Request as RefreshRequest
        from google.oauth2.credentials import Credentials
    except ImportError:
        raise GoogleFailure(
            "missing_dependencies", "Install the optional google extra in the engine's runtime."
        ) from None
    try:
        creds = Credentials.from_authorized_user_info(data)
        if not creds.valid:
            refresh = RefreshRequest()

            def bounded_refresh(*args, **kwargs):
                kwargs["timeout"] = 20
                return refresh(*args, **kwargs)

            creds.refresh(bounded_refresh)
            updated = scope_record(
                creds, data.get("beyondseo_requested_scopes", data.get("scopes", [])), data
            )
            save(path, updated)
            effective_scopes = updated["scopes"]
            if SCOPES[service] not in effective_scopes:
                raise GoogleFailure(
                    "scope_missing",
                    "Google's refreshed grant does not include "
                    + service
                    + ". Reconnect for that service or continue with the remaining granted access.",
                )
        return creds
    except GoogleFailure:
        raise
    except Exception:
        raise GoogleFailure(
            "refresh_failed",
            "Google credentials could not be refreshed. Check permitted networking and whether the grant was revoked, then reconnect if necessary. No further retries were made.",
        ) from None


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request(folder, service, url, payload=None):
    if not any(url.startswith(endpoint) for endpoint in ENDPOINTS.values()):
        raise ValueError("Unsupported Google endpoint.")
    creds = credentials(folder, service)
    req = Request(
        url,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"Authorization": "Bearer " + creds.token, "Content-Type": "application/json"},
    )
    try:
        with build_opener(NoRedirect()).open(req, timeout=20) as response:
            body = response.read(LIMIT + 1)
        if len(body) > LIMIT:
            raise GoogleFailure(
                "response_limit", "Google returned more than 2 MB. Reduce the report row limit."
            )
        data = json.loads(body)
        if not isinstance(data, dict):
            raise ValueError("not object")
        return data
    except GoogleFailure:
        raise
    except HTTPError as exc:
        reason = {
            401: "authorization_denied",
            403: "access_or_api_restriction",
            429: "rate_limited",
        }.get(exc.code, "google_http_failure")
        raise GoogleFailure(
            reason,
            "Google returned HTTP "
            + str(exc.code)
            + ". For 403, check property permissions, enabled APIs and organisation policy; the exact cause is unknown from this status alone. For 429, retry later within the account quota.",
            exc.code,
        ) from None
    except PermissionError:
        raise GoogleFailure(
            "execution_denied",
            "The environment denied the network operation; use an approved connection or export.",
        ) from None
    except (TimeoutError, socket.timeout):
        raise GoogleFailure(
            "timeout",
            "Google request timed out after 20 seconds. Check the environment's network access.",
        ) from None
    except URLError as exc:
        reason = (
            "execution_denied"
            if isinstance(exc.reason, PermissionError)
            else "dns_failure"
            if isinstance(exc.reason, socket.gaierror)
            else "tls_failure"
            if isinstance(exc.reason, ssl.SSLError)
            else "connection_failure"
        )
        raise GoogleFailure(
            reason,
            "Cannot reach Google from this environment. Check DNS, TLS and approved network routes; browser and connector access are separate.",
        ) from None
    except (json.JSONDecodeError, UnicodeError, ValueError):
        raise GoogleFailure(
            "parsing_failed",
            "Google response could not be parsed as the expected JSON object; no empty-result conclusion was made.",
        ) from None


def properties(folder=None, services=None):
    results = {}
    for service in services or SCOPES:
        if service not in SCOPES:
            raise ValueError("Unknown service.")
        try:
            endpoint = ENDPOINTS["sites" if service == "search-console" else "accounts"]
            data = request(folder, service, endpoint)
            rows = data.get("siteEntry" if service == "search-console" else "accountSummaries", [])
            if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
                raise GoogleFailure(
                    "parsing_failed",
                    "Unexpected property-list response; do not treat it as no accessible properties.",
                )
            results[service] = {
                "status": "verified" if rows else "no_properties_returned",
                "properties": rows,
                "continuation_available": bool(data.get("nextPageToken")),
            }
        except GoogleFailure as exc:
            results[service] = exc.result()
    return {
        "status": "complete"
        if all(r["status"] in {"verified", "no_properties_returned"} for r in results.values())
        else "partial",
        "checked_at": utcnow(),
        "services": results,
        "note": "Choose the exact Search Console property and GA4 property. A GA4 account name alone does not establish a domain match. Lists may be partial.",
    }


def period(start, end):
    if date.fromisoformat(start) > date.fromisoformat(end):
        raise ValueError("Start date must not be after end date.")


def destination(out):
    out = state_path(out)
    if out.exists():
        raise ValueError("Choose a fresh private report folder.")
    return out


def search_console(folder, prop, start, end, dimension, out, limit=1000):
    period(start, end)
    out = destination(out)
    if not (normalize_url(prop) or re.fullmatch(r"sc-domain:[a-zA-Z0-9.-]+", prop)):
        raise ValueError("Use the exact URL-prefix or sc-domain property from google properties.")
    if dimension not in {"query", "page", "country", "device", "date"} or not 1 <= limit <= 25000:
        raise ValueError("Use a supported single dimension and 1–25000 rows.")
    payload = {
        "startDate": start,
        "endDate": end,
        "dimensions": [dimension],
        "type": "web",
        "dataState": "final",
        "rowLimit": limit,
    }
    data = request(
        folder,
        "search-console",
        ENDPOINTS["sites"] + "/" + quote(prop, safe="") + "/searchAnalytics/query",
        payload,
    )
    rows = data.get("rows", [])
    if not isinstance(rows, list) or any(
        not isinstance(r, dict)
        or not isinstance(r.get("keys"), list)
        or len(r["keys"]) != 1
        or not isinstance(r["keys"][0], str)
        or any(k not in r for k in ("clicks", "impressions", "ctr", "position"))
        or any(
            type(r.get(k)) not in (int, float) or not math.isfinite(r[k]) or r[k] < 0
            for k in ("clicks", "impressions", "ctr", "position")
        )
        or r["ctr"] > 1
        for r in rows
    ):
        raise GoogleFailure(
            "parsing_failed", "Unexpected search analytics rows; no report was written."
        )
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(
        [
            {
                "query": "Top queries",
                "page": "Top pages",
                "country": "Country",
                "device": "Device",
                "date": "Date",
            }[dimension],
            "Clicks",
            "Impressions",
            "CTR",
            "Position",
        ]
    )
    for row in rows:
        writer.writerow(
            [
                row["keys"][0],
                row["clicks"],
                row["impressions"],
                f"{float(row['ctr']) * 100:.6f}%",
                row["position"],
            ]
        )
    result = {
        "status": "observed" if rows else "no_results",
        "provider": "Google Search Console API",
        "captured_at": utcnow(),
        "property": prop,
        "request": payload,
        "rows_returned": len(rows),
        "coverage": "Bounded top rows; API results are not guaranteed to include every row. Empty results do not establish no traffic.",
        "raw": data,
    }
    save(out / "search-console.json", result)
    write_private(out / "search-console.csv", stream.getvalue())
    return {k: v for k, v in result.items() if k != "raw"}


def analytics(folder, prop, start, end, out, limit=1000):
    period(start, end)
    out = destination(out)
    prop = str(prop).removeprefix("properties/")
    if not re.fullmatch(r"[0-9]{1,20}", prop) or not 1 <= limit <= 10000:
        raise ValueError("Use the numeric GA4 property ID and 1–10000 rows.")
    payload = {
        "dateRanges": [{"startDate": start, "endDate": end}],
        "dimensions": [{"name": "landingPagePlusQueryString"}],
        "metrics": [{"name": "sessions"}, {"name": "engagedSessions"}, {"name": "keyEvents"}],
        "dimensionFilter": {
            "filter": {
                "fieldName": "sessionDefaultChannelGroup",
                "stringFilter": {"matchType": "EXACT", "value": "Organic Search"},
            }
        },
        "limit": str(limit),
        "returnPropertyQuota": True,
    }
    data = request(folder, "analytics", ENDPOINTS["analytics"] + prop + ":runReport", payload)
    rows = data.get("rows", [])
    if not isinstance(rows, list) or any(
        not isinstance(r, dict)
        or not isinstance(r.get("dimensionValues"), list)
        or len(r["dimensionValues"]) != 1
        or not isinstance(r.get("metricValues"), list)
        or len(r["metricValues"]) != 3
        for r in rows
    ):
        raise GoogleFailure("parsing_failed", "Unexpected Analytics rows; no report was written.")
    result = {
        "status": "observed" if rows else "no_results",
        "provider": "Google Analytics Data API",
        "captured_at": utcnow(),
        "property": "properties/" + prop,
        "request": payload,
        "rows_returned": len(rows),
        "coverage": "Organic Search landing-page report; preserve metadata for thresholding/sampling and row limits. Key events depend on the owner's tracking configuration. No SEO causation or complete funnel is established.",
        "raw": data,
    }
    save(out / "analytics.json", result)
    return {k: v for k, v in result.items() if k != "raw"}


def pagespeed_target(value):
    target = normalize_url(value)
    if not target:
        raise ValueError("Use a public HTTP(S) PageSpeed target without embedded credentials.")
    host = (urlsplit(target).hostname or "").rstrip(".").casefold()
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
        raise ValueError(
            "PageSpeed requires a public target; localhost/private targets are unsupported."
        )
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        # Reject single-label and legacy numeric IP spellings without relying on
        # local DNS. The public provider performs its own network access checks.
        if "." not in host or host.rsplit(".", 1)[-1].isdigit():
            raise ValueError(
                "Use a public domain or globally routable literal IP target."
            ) from None
    else:
        if not address.is_global:
            raise ValueError(
                "PageSpeed requires a public target; private IP targets are unsupported."
            )
    return target


def pagespeed(target, strategy, out):
    """One optional public PSI request; no account, OAuth or required API key.

    Only the returned lab report is retained for lighthouse-review. Provider
    denials, quota failures, runtime failures and parsing errors stay unavailable.
    """
    target = pagespeed_target(target)
    if strategy not in {"mobile", "desktop"}:
        raise ValueError("Choose mobile or desktop PageSpeed strategy.")
    out = destination(out)
    query = {"url": target, "strategy": strategy, "category": "performance"}
    result = {
        "schema_version": 1,
        "provider": "Google PageSpeed Insights API",
        "captured_at": utcnow(),
        "target": target,
        "requested_strategy": strategy,
        "request": {
            "method": "GET",
            "endpoint": PSI_ENDPOINT,
            "query": query,
            "authorization": "none",
        },
        "limits": {
            "requests_attempted": 1,
            "request_budget": 1,
            "timeout_seconds": 45,
            "max_response_bytes": PSI_LIMIT,
        },
        "coverage": "One remote lab measurement of the requested page and strategy. It is not a complete website audit, real-user field measurement, ranking or AI-citation result. Provider access and quota can make this optional route unavailable.",
        "field_data": "not assessed",
        "fallback": "Save a Lighthouse JSON report in an approved browser/tool, then run lighthouse-review --input FILE --out PRIVATE_FOLDER. Continue the native website audit independently.",
    }
    report = None
    try:
        req = Request(PSI_ENDPOINT + "?" + urlencode(query), headers={"Accept": "application/json"})
        with build_opener(NoRedirect()).open(req, timeout=45) as response:
            body = response.read(PSI_LIMIT + 1)
        result["http_status"] = 200
        if len(body) > PSI_LIMIT:
            raise GoogleFailure(
                "response_limit", "PageSpeed response exceeded the bounded 5 MB response limit."
            )
        data = json.loads(body)
        if not isinstance(data, dict):
            raise GoogleFailure(
                "parsing_failed", "PageSpeed did not return the expected JSON object."
            )
        if data.get("captchaResult") not in (None, "CAPTCHA_NOT_NEEDED"):
            raise GoogleFailure(
                "provider_challenge",
                "PageSpeed returned a challenge; no attempt was made to bypass it.",
            )
        report = data.get("lighthouseResult")
        if not isinstance(report, dict) or not isinstance(report.get("audits"), dict):
            raise GoogleFailure(
                "parsing_failed",
                "PageSpeed response lacks a usable lighthouseResult with audits; no empty or passing result was inferred.",
            )
        if normalize_url(report.get("requestedUrl", "")) != target:
            report = None
            raise GoogleFailure(
                "report_target_mismatch",
                "The returned Lighthouse requested URL does not match this request; no metrics were attributed to the target.",
            )
        result["lighthouse_version"] = report.get("lighthouseVersion")
        result["provider_fetch_time"] = report.get("fetchTime")
        result["final_url"] = report.get("finalUrl")
        if report.get("runtimeError"):
            result["runtime_error"] = report["runtimeError"]
            raise GoogleFailure(
                "lighthouse_runtime_error",
                "The provider returned a Lighthouse runtime error; no valid performance measurement was established.",
            )
        if not report["audits"]:
            report = None
            raise GoogleFailure(
                "parsing_failed",
                "PageSpeed returned no audit measurements; do not treat this as a successful check.",
            )
        result["status"] = "observed"
    except HTTPError as exc:
        result.update(
            status="unavailable",
            http_status=exc.code,
            reason="quota_or_rate_limited"
            if exc.code == 429
            else "provider_access_denied"
            if exc.code in (401, 403)
            else "provider_redirect_denied"
            if 300 <= exc.code < 400
            else "provider_http_failure",
            action="PageSpeed returned HTTP "
            + str(exc.code)
            + ". Check the observed provider response and quota; a denied no-key request does not mean a paid subscription is required. Use the saved-report fallback.",
        )
        # The request has no credentials. Retain bounded provider evidence rather
        # than claiming that HTTP 403 alone identifies its underlying cause.
        try:
            error_body = exc.read(64_001)
            if len(error_body) <= 64_000:
                error = json.loads(error_body).get("error")
                if isinstance(error, dict):
                    result["provider_error"] = error
        except (OSError, ValueError, AttributeError, RecursionError):
            pass
        result["underlying_cause"] = "unknown unless established by retained provider_error"
    except GoogleFailure as exc:
        http_status = result.get("http_status")
        result.update(exc.result())
        result["http_status"] = exc.http_status or http_status
    except PermissionError:
        result.update(
            status="unavailable",
            reason="execution_denied",
            action="The environment denied this public request. Use an approved route or a saved report.",
        )
    except (TimeoutError, socket.timeout):
        result.update(
            status="unavailable",
            reason="timeout",
            action="The one public PSI request timed out after 45 seconds. No automatic retry was made.",
        )
    except URLError as exc:
        reason = (
            "execution_denied"
            if isinstance(exc.reason, PermissionError)
            else "dns_failure"
            if isinstance(exc.reason, socket.gaierror)
            else "tls_failure"
            if isinstance(exc.reason, ssl.SSLError)
            else "connection_failure"
        )
        result.update(
            status="unavailable",
            reason=reason,
            action="This environment could not reach the fixed PageSpeed API endpoint; the target's own performance remains unknown.",
        )
    except ssl.SSLError:
        result.update(
            status="unavailable",
            reason="tls_failure",
            action="TLS to the fixed PageSpeed API endpoint failed; certificate verification was not disabled.",
        )
    except OSError:
        result.update(
            status="unavailable",
            reason="connection_failure",
            action="The public PageSpeed connection failed during the request or response. The target's performance remains unknown; use the saved-report fallback.",
        )
    except (json.JSONDecodeError, UnicodeError, ValueError, TypeError, RecursionError):
        report = None
        result.update(
            status="unavailable",
            reason="parsing_failed",
            action="The received PageSpeed response could not be interpreted as the expected report. No measurement was invented.",
        )
    if report is not None:
        save(out / "lighthouse.json", report)
        result["report_file"] = "lighthouse.json"
    save(out / "pagespeed-attempt.json", result)
    return result


def register(sub):
    group = sub.add_parser(
        "google", help="Optional read-only Google consent, properties and bounded reports."
    )
    actions = group.add_subparsers(dest="google_action", required=True)
    public = actions.add_parser(
        "pagespeed",
        help="One optional public PageSpeed lab request; target URL is sent to Google, no OAuth/key required.",
    )
    public.add_argument("--url", required=True)
    public.add_argument("--strategy", choices=["mobile", "desktop"], default="mobile")
    public.add_argument("--out", type=Path, required=True)
    for name in ("status", "connect", "properties", "search-console", "analytics", "disconnect"):
        p = actions.add_parser(name)
        p.add_argument(
            "--state-dir", type=Path, help="Private per-account state outside the source folder."
        )
        if name == "connect":
            p.add_argument("--client-json", type=Path, required=True)
            p.add_argument(
                "--browser", help="Optional browser name supported by Python webbrowser."
            )
        if name in {"connect", "properties"}:
            p.add_argument("--service", action="append", choices=list(SCOPES))
        if name in {"search-console", "analytics"}:
            p.add_argument("--property", required=True)
            p.add_argument("--start", required=True)
            p.add_argument("--end", required=True)
            p.add_argument("--limit", type=int, default=1000)
            p.add_argument("--out", type=Path, required=True)
        if name == "search-console":
            p.add_argument(
                "--dimension",
                choices=["query", "page", "country", "device", "date"],
                default="page",
            )


def execute(args):
    if args.google_action == "pagespeed":
        return pagespeed(args.url, args.strategy, args.out)
    folder = args.state_dir
    if args.google_action == "status":
        return status(folder)
    if args.google_action == "connect":
        return connect(args.client_json, folder, args.service, args.browser)
    if args.google_action == "properties":
        return properties(folder, args.service)
    if args.google_action == "disconnect":
        path = state_path(folder) / "token.json"
        if path.is_symlink():
            raise ValueError("Refusing to remove a symlink.")
        path.unlink(missing_ok=True)
        return {
            "status": "local_credentials_removed",
            "note": "This removes the local saved connection only. Revoke the Google grant in your Google Account connections if desired; existing host/gog connections are unchanged.",
        }
    if args.google_action == "search-console":
        return search_console(
            folder, args.property, args.start, args.end, args.dimension, args.out, args.limit
        )
    return analytics(folder, args.property, args.start, args.end, args.out, args.limit)
