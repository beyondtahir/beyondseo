"""Scoped HTTP transport, polite scheduling, robots rules, and URL handling."""

from __future__ import annotations

import hashlib
import http.client
import ipaddress
import math
import re
import socket
import ssl
import threading
import time
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote, unquote_plus, urljoin, urlsplit, urlunsplit

from .diagnostics import challenge_signal, classify_access

USER_AGENT = "BeyondSEO/2.1 (+https://beyondtahir.com)"
UNRESERVED = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"
TRACKING = {"gclid", "dclid", "fbclid", "msclkid", "_ga", "mc_cid", "mc_eid"}
ASSETS = re.compile(
    r"\.(?:jpg|jpeg|png|gif|webp|svg|ico|avif|mp4|mp3|wav|webm|woff2?|ttf|eot|css|js|zip|pdf|exe|dmg)(?:$)",
    re.I,
)


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def percent_normalize(s):
    s = quote(s, safe="/%:@!$&'()*+,;=-._~?")

    def fix(m):
        c = chr(int(m.group()[1:], 16))
        return c if c in UNRESERVED else m.group().upper()

    return re.sub(r"%[a-fA-F0-9]{2}", fix, s)


def normalize_url(value, base=None, drop_tracking=True):
    try:
        if not isinstance(value, str) or not value.strip():
            return None
        if any(ord(c) < 32 for c in value) or "\\" in value:
            return None
        p = urlsplit(urljoin(base, value.strip()) if base else value.strip())
        if p.scheme.lower() not in ("http", "https") or not p.hostname or p.username or p.password:
            return None
        host = p.hostname.rstrip(".").encode("idna").decode("ascii").lower()
        port = p.port
        hostpart = "[" + host + "]" if ":" in host else host
        if port and port != (443 if p.scheme.lower() == "https" else 80):
            hostpart += ":" + str(port)
        # Preserve query order, repetitions, reserved characters, path case and trailing slash.
        query = "&".join(
            part
            for part in p.query.split("&")
            if part
            and not (
                drop_tracking
                and (
                    unquote_plus(part.split("=", 1)[0]).lower().startswith("utm_")
                    or unquote_plus(part.split("=", 1)[0]).lower() in TRACKING
                )
            )
        )
        return urlunsplit(
            (
                p.scheme.lower(),
                hostpart,
                percent_normalize(p.path or "/"),
                percent_normalize(query),
                "",
            )
        )
    except (ValueError, UnicodeError):
        return None


def origin(url):
    p = urlsplit(url)
    return p.scheme + "://" + p.netloc


@dataclass
class Config:
    url: str
    max_pages: int = 100
    max_depth: int = 6
    workers: int = 4
    delay: float = 0.5
    timeout: float = 20.0
    retries: int = 2
    max_bytes: int = 5_000_000
    max_discovered: int = 10_000
    max_sitemaps: int = 25
    max_query_variants: int = 20
    allow_hosts: list = field(default_factory=list)
    exclude: list = field(default_factory=list)
    allow_private: bool = False
    sitemaps: bool = True
    drop_tracking: bool = True
    save_html: bool = True
    render: bool = False
    render_wait_ms: int = 1000
    render_max_requests: int = 50
    render_allow_hosts: list = field(default_factory=list)
    render_mode: str = "http"
    robots_policy: str = "respect"
    render_asset_policy: str = "public"
    wait_for_selector: str = ""
    render_settle_ms: int = 1500
    scroll_steps: int = 3
    screenshot: bool = False
    headless: bool = True
    include_www: bool = False

    def __post_init__(self):
        self.url = normalize_url(self.url, drop_tracking=self.drop_tracking)
        if not self.url:
            raise ValueError("Provide a valid http(s) URL without credentials.")
        for k in (
            "max_pages",
            "workers",
            "max_bytes",
            "max_discovered",
            "max_sitemaps",
            "max_query_variants",
            "render_max_requests",
        ):
            if getattr(self, k) < 1:
                raise ValueError(k + " must be positive")
        if not math.isfinite(self.delay) or not math.isfinite(self.timeout):
            raise ValueError("delay and timeout must be finite")
        if (
            self.max_depth < 0
            or self.delay < 0
            or self.timeout <= 0
            or self.retries < 0
            or self.render_wait_ms < 0
        ):
            raise ValueError("Invalid negative limit or timeout")
        if self.workers > 32:
            raise ValueError("workers must be <= 32")
        if self.render_mode not in ("http", "auto", "browser"):
            raise ValueError("mode must be http, auto or browser")
        if self.robots_policy not in ("respect", "ignore"):
            raise ValueError("robots must be respect or ignore")
        if self.render_asset_policy not in ("public", "allowlist"):
            raise ValueError("browser assets must be public or allowlist")
        if not 0 <= self.scroll_steps <= 20:
            raise ValueError("scroll steps must be between 0 and 20")
        if not 0 <= self.render_settle_ms <= 30000:
            raise ValueError("settle time must be between 0 and 30000 ms")
        if self.render:
            self.render_mode = "browser"
        self.allow_hosts = sorted(set(h.lower().rstrip(".") for h in self.allow_hosts))
        if self.include_www:
            hostname = urlsplit(self.url).hostname
            try:
                ipaddress.ip_address(hostname)
            except ValueError:
                if "." in hostname:
                    alternate = hostname[4:] if hostname.startswith("www.") else "www." + hostname
                    self.allow_hosts = sorted({*self.allow_hosts, alternate})
        for pattern in self.exclude:
            re.compile(pattern)

    def in_scope(self, url):
        p = urlsplit(url)
        seed = urlsplit(self.url)
        hosts = {seed.hostname, *self.allow_hosts}
        ports = {seed.port or (443 if seed.scheme == "https" else 80), 80, 443}
        return p.hostname in hosts and (p.port or (443 if p.scheme == "https" else 80)) in ports

    def exclusion(self, url):
        if not self.in_scope(url):
            return "out_of_scope"
        if ASSETS.search(urlsplit(url).path):
            return "asset_extension"
        if any(re.search(p, url) for p in self.exclude):
            return "excluded_pattern"
        return None


def addresses(url, allow_private=False):
    p = urlsplit(url)
    port = p.port or (443 if p.scheme == "https" else 80)
    infos = socket.getaddrinfo(p.hostname, port, type=socket.SOCK_STREAM)
    if not infos:
        raise ValueError("DNS returned no addresses")
    for _, _, _, _, addr in infos:
        ip = ipaddress.ip_address(addr[0].split("%")[0])
        if not allow_private and not ip.is_global:
            raise ValueError("private_or_nonpublic_address")
    return infos


@dataclass
class Response:
    url: str
    final_url: str
    status: int = 0
    headers: dict = field(default_factory=dict)
    body: bytes = b""
    redirects: list = field(default_factory=list)
    error: str = ""
    attempts: int = 0
    http_events: list = field(default_factory=list)
    elapsed_ms: float = 0
    withheld_url: str = ""
    fetched_at: str = field(default_factory=utcnow)


class RateLimiter:
    def __init__(self):
        self.lock = threading.Lock()
        self.next = {}

    def wait(self, url, delay):
        with self.lock:
            now = time.monotonic()
            slot = max(now, self.next.get(origin(url), now))
            self.next[origin(url)] = slot + delay
        time.sleep(max(0, slot - time.monotonic()))


class Transport:
    def __init__(self, config):
        self.config = config
        self.limiter = RateLimiter()

    def once(self, url, request_headers=None, method="GET"):
        """Connect to a verified resolved IP, retaining the original host for TLS SNI."""
        if method not in ("GET", "OPTIONS"):
            raise ValueError("unsupported_http_method")
        p = urlsplit(url)
        deadline = time.monotonic() + self.config.timeout
        infos = addresses(url, self.config.allow_private)
        sock = None
        last = None
        for family, kind, proto, _, addr in infos:
            candidate = socket.socket(family, kind, proto)
            candidate.settimeout(max(0.1, deadline - time.monotonic()))
            try:
                candidate.connect(addr)
                sock = candidate
                break
            except OSError as e:
                last = e
                candidate.close()
        if sock is None:
            raise last or OSError("connect failed")
        conn = http.client.HTTPConnection(
            p.hostname, p.port or (443 if p.scheme == "https" else 80), timeout=self.config.timeout
        )
        try:
            if p.scheme == "https":
                sock = ssl.create_default_context().wrap_socket(sock, server_hostname=p.hostname)
            conn.sock = sock
            path = p.path or "/"
            if p.query:
                path += "?" + p.query
            headers = {
                "Host": p.netloc,
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml,text/xml,text/plain;q=0.9,*/*;q=0.1",
                "Accept-Encoding": "gzip",
                "Connection": "close",
            }
            # Browser-generated public-site requests may need their API/CORS headers.
            # Never persist these values or forward credentials across a redirect origin.
            allowed_headers = {
                "accept",
                "content-type",
                "origin",
                "referer",
                "authorization",
                "apikey",
                "x-client-info",
                "access-control-request-method",
                "access-control-request-headers",
            }
            for k, v in (request_headers or {}).items():
                if k.lower() in allowed_headers:
                    headers[k.title()] = v
            conn.request(method, path, headers=headers)
            resp = conn.getresponse()
            headers = {}
            for k, v in resp.getheaders():
                headers[k.lower()] = (
                    headers.get(k.lower(), "") + (", " if k.lower() in headers else "") + v
                )
            # Redirect bodies are not needed, and may be arbitrarily large.
            if resp.status in (301, 302, 303, 307, 308):
                return resp.status, headers, b""
            limit = self.config.max_bytes
            parts = []
            size = 0
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("response deadline exceeded")
                data = resp.read(min(65536, limit + 1 - size))
                if not data:
                    break
                size += len(data)
                if size > limit:
                    raise ValueError("response_too_large")
                parts.append(data)
            body = b"".join(parts)
            if headers.get("content-encoding", "").lower() == "gzip" or body.startswith(
                b"\x1f\x8b"
            ):
                dec = zlib.decompressobj(16 + zlib.MAX_WBITS)
                body = dec.decompress(body, limit + 1)
                if len(body) > limit or dec.unconsumed_tail:
                    raise ValueError("decompressed_response_too_large")
                if not dec.eof:
                    raise ValueError("incomplete_gzip")
            elif headers.get("content-encoding", "identity").lower() not in ("identity", ""):
                raise ValueError("unsupported_content_encoding")
            return resp.status, headers, body
        finally:
            conn.close()
            if sock:
                sock.close()

    def fetch(self, url, allowed=None, delay_for=None, request_headers=None, method="GET"):
        started = time.monotonic()
        r = Response(url, url)
        seen = set()
        current = url
        for hop in range(11):
            if current in seen:
                r.error = "redirect_loop"
                break
            seen.add(current)
            if not self.config.in_scope(current):
                r.error = "redirect_out_of_scope"
                break
            if any(re.search(p, current) for p in self.config.exclude):
                r.error = "excluded_pattern"
                break
            if allowed and not allowed(current):
                owner = getattr(allowed, "__self__", None)
                reason = getattr(owner, "denial_reason", None)
                r.error = reason(current) if reason else "robots_disallowed"
                r.withheld_url = current
                break
            delay = max(self.config.delay, delay_for(current) if delay_for else 0)
            if delay > 30:
                r.error = "crawl_delay_exceeds_run_wait_budget"
                break
            for retry in range(self.config.retries + 1):
                self.limiter.wait(current, delay)
                r.attempts += 1
                r.final_url = current
                r.error = ""
                attempt_time = utcnow()
                try:
                    r.status, r.headers, r.body = self.once(
                        current,
                        request_headers=request_headers if origin(current) == origin(url) else None,
                        method=method,
                    )
                except (OSError, ValueError, http.client.HTTPException) as e:
                    r.status = 0
                    r.headers = {}
                    r.body = b""
                    r.error = type(e).__name__ + ": " + str(e)
                r.http_events.append(
                    {
                        "url": current,
                        "status": r.status,
                        "error": r.error,
                        "fetched_at": attempt_time,
                        "retry_after": r.headers.get("retry-after"),
                        "challenge_detected": bool(challenge_signal(r.headers, r.body)),
                    }
                )
                if r.error.startswith("ValueError:"):
                    break
                if challenge_signal(r.headers, r.body):
                    r.error = "challenge_response"
                    break
                if not r.error and r.status not in (429, 500, 502, 503, 504):
                    break
                if retry == self.config.retries:
                    break
                wait = 2**retry
                value = r.headers.get("retry-after", "")
                if value:
                    try:
                        wait = max(wait, float(value))
                    except ValueError:
                        try:
                            wait = max(
                                wait,
                                (
                                    parsedate_to_datetime(value) - datetime.now(timezone.utc)
                                ).total_seconds(),
                            )
                        except (ValueError, TypeError, OverflowError):
                            pass
                # Never shorten the server's requested wait: leave it for a later run.
                if wait > 30:
                    break
                time.sleep(wait)
            if r.error:
                break
            if r.status not in (301, 302, 303, 307, 308):
                break
            target = normalize_url(
                r.headers.get("location", ""), current, self.config.drop_tracking
            )
            r.redirects.append(
                {
                    "url": current,
                    "status": r.status,
                    "location": r.headers.get("location", ""),
                    "target": target,
                }
            )
            if not target:
                r.error = "invalid_redirect"
                break
            if hop == 10:
                r.error = "redirect_limit"
                break
            current = target
        r.elapsed_ms = round((time.monotonic() - started) * 1000, 2)
        return r


class RobotsRules:
    def __init__(self, text="", blocked=False, agent="beyondseo"):
        self.blocked = blocked
        self.sitemaps = []
        groups = []
        agents = []
        rules = []
        delays = []
        started = False

        def flush():
            if agents:
                groups.append((agents[:], rules[:], delays[:]))

        for raw in text.lstrip("\ufeff").splitlines():
            line = raw.split("#", 1)[0].strip()
            if ":" not in line:
                continue
            k, v = (x.strip() for x in line.split(":", 1))
            k = k.lower()
            if k == "sitemap":
                self.sitemaps.append(v)
                continue
            if k == "user-agent":
                if started:
                    flush()
                    agents = []
                    rules = []
                    delays = []
                    started = False
                agents.append(v.lower())
            elif agents:
                if k in ("allow", "disallow"):
                    started = True
                    if v:
                        rules.append((k == "allow", percent_normalize(v)))
                elif k == "crawl-delay":
                    started = True
                    try:
                        if float(v) >= 0:
                            delays.append(float(v))
                    except ValueError:
                        pass
        flush()
        selected = [g for g in groups if agent.lower() in g[0]]
        if not selected:
            selected = [g for g in groups if "*" in g[0]]
        self.rules = [r for _, rs, _ in selected for r in rs]
        self.delay = max([d for _, _, ds in selected for d in ds] or [0])

    def allowed(self, url):
        if self.blocked:
            return False
        p = urlsplit(url)
        path = percent_normalize(p.path or "/") + (
            "?" + percent_normalize(p.query) if p.query else ""
        )
        matches = []
        for allow, pattern in self.rules:
            end = pattern.endswith("$")
            pattern = pattern[:-1] if end else pattern
            regex = "^" + ".*".join(re.escape(s) for s in pattern.split("*")) + ("$" if end else "")
            if re.search(regex, path):
                matches.append((len(pattern.replace("*", "").encode("utf-8")), allow))
        return max(matches)[1] if matches else True


class RobotsCache:
    def __init__(self, transport):
        self.transport = transport
        self.cache = {}
        self.evidence = {}
        self.lock = threading.RLock()

    def get(self, url):
        key = origin(url)
        with self.lock:
            if key not in self.cache:
                r = self.transport.fetch(key + "/robots.txt")
                blocked = (
                    bool(r.error) or r.status == 429 or r.status >= 500 or (300 <= r.status < 400)
                )
                text = r.body[:512_000].decode("utf-8", "replace") if r.status == 200 else ""
                self.cache[key] = RobotsRules(text, blocked)
                self.evidence[key] = {
                    "url": key + "/robots.txt",
                    "status": r.status,
                    "error": r.error,
                    "blocked": blocked,
                    "policy_availability": "unreachable"
                    if blocked
                    else "unavailable"
                    if 400 <= r.status < 500
                    else "available",
                    "fetched_at": r.fetched_at,
                    "sha256": hashlib.sha256(r.body).hexdigest(),
                    "text": text,
                    "redirects": r.redirects,
                    "http_events": r.http_events,
                    "access": classify_access(r.status, r.headers, r.body, r.error),
                }
            return self.cache[key]

    def allowed(self, url):
        if self.transport.config.robots_policy == "ignore":
            self.get(url)
            self.evidence[origin(url)]["override"] = "ignore explicitly selected for this run"
            return True
        return self.get(url).allowed(url)

    def delay(self, url):
        return 0 if self.transport.config.robots_policy == "ignore" else self.get(url).delay

    def decision(self, url):
        rules = self.get(url)
        evidence = self.evidence[origin(url)]
        allowed = self.transport.config.robots_policy == "ignore" or rules.allowed(url)
        reason = ""
        if not allowed:
            reason = (
                "robots_scope_limited"
                if evidence.get("error") == "redirect_out_of_scope"
                else "robots_unavailable"
                if rules.blocked
                else "robots_rule_disallowed"
            )
        return {
            "url": url,
            "allowed": allowed,
            "reason": reason,
            "policy_url": evidence["url"],
            "policy_status": evidence["status"],
            "policy_error": evidence["error"],
            "policy_availability": evidence["policy_availability"],
        }

    def denial_reason(self, url):
        return self.decision(url)["reason"]
