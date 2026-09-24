"""DOM extraction with BeautifulSoup; findings retain their underlying observations."""

from __future__ import annotations

import hashlib
import json
import re

from bs4 import BeautifulSoup

from .content import markdown_from_html
from .network import normalize_url


def clean(value):
    return re.sub(r"\s+", " ", value or "").strip()


def invalid_json_constant(value):
    raise ValueError("Invalid JSON constant: " + value)


def schema_types(value):
    result = set()
    stack = [value]
    while stack:
        item = stack.pop()
        if isinstance(item, list):
            stack.extend(item)
        elif isinstance(item, dict):
            types = item.get("@type", [])
            if isinstance(types, str):
                types = [types]
            if isinstance(types, list):
                result.update(t for t in types if isinstance(t, str))
            stack.extend(item.values())
    return sorted(result)


def extract(html, url, headers=None, selectors=None):
    headers = headers or {}
    # Bytes let BeautifulSoup honor declared document encodings; HTTP charset wins.
    charset = re.search(r'charset\s*=\s*["\']?([^\s;"\']+)', headers.get("content-type", ""), re.I)
    soup = BeautifulSoup(
        html,
        "html.parser",
        from_encoding=charset.group(1) if charset and isinstance(html, bytes) else None,
    )
    base = url
    b = soup.find("base", href=True)
    if b:
        base = normalize_url(b.get("href"), url, False) or url

    def absolute(v):
        return normalize_url(v, base, False)

    def content(node):
        return clean(node.get_text(" ", strip=True))

    # SVG/MathML title elements label graphics; they are not document titles.
    titles = [content(t) for t in soup.find_all("title") if not t.find_parent(["svg", "math"])]
    metas = {}
    for m in soup.find_all("meta"):
        key = str(m.get("name") or m.get("property") or "").lower()
        if key:
            metas.setdefault(key, []).append(m.get("content", ""))
    links = []
    for a in soup.find_all(["a", "area"], href=True):
        raw = a.get("href", "")
        target = absolute(raw)
        if target:
            links.append(
                {
                    "url": target,
                    "raw_href": raw,
                    "anchor": content(a),
                    "rel": [str(x).lower() for x in a.get("rel", [])],
                    "kind": "anchor",
                }
            )
    canonicals = []
    hreflang = []
    pagination = []
    for link in soup.find_all("link", href=True):
        rel = [str(x).lower() for x in link.get("rel", [])]
        target = absolute(link.get("href"))
        if "canonical" in rel:
            canonicals.append({"raw": link.get("href"), "url": target})
        if "alternate" in rel and link.get("hreflang"):
            hreflang.append({"language": link.get("hreflang"), "url": target})
        if set(rel) & {"next", "prev"} and target:
            pagination.append({"rel": rel, "url": target})
    jsonld = []
    jsonld_errors = []
    types = set()
    for index, script in enumerate(
        soup.find_all("script", attrs={"type": re.compile(r"^application/ld\+json$", re.I)})
    ):
        raw = script.string or script.get_text()
        try:
            value = json.loads(raw, parse_constant=invalid_json_constant)
            jsonld.append(value)
            types.update(schema_types(value))
        except (ValueError, TypeError, RecursionError) as e:
            jsonld_errors.append({"block": index, "error": str(e)})
    microdata = sorted(
        {str(t) for n in soup.find_all(itemtype=True) for t in str(n.get("itemtype", "")).split()}
    )
    images = [
        {
            "src": absolute(n.get("src") or n.get("data-src") or ""),
            "raw_src": n.get("src", ""),
            "srcset": n.get("srcset", ""),
            "alt": n.get("alt"),
            "alt_present": n.has_attr("alt"),
            "width": n.get("width"),
            "height": n.get("height"),
            "loading": n.get("loading"),
            "fetchpriority": n.get("fetchpriority"),
            "sizes": n.get("sizes"),
        }
        for n in soup.find_all("img")
    ]
    custom = {}
    for key, spec in (selectors or {}).items():
        if isinstance(spec, str):
            spec = {"selector": spec}
        attr = spec.get("attribute")
        nodes = soup.select(spec["selector"])
        values = [(n.get(attr) if attr else content(n)) for n in nodes]
        custom[key] = values if spec.get("all", True) else (values[0] if values else None)
    script_count = sum(
        str(tag.get("type", "")).lower().strip()
        in ("", "module", "text/javascript", "application/javascript")
        for tag in soup.find_all("script")
    )
    forms = [
        {
            "action": absolute(f.get("action") or url),
            "method": f.get("method", "get").lower(),
            "fields": len(f.find_all(["input", "select", "textarea"])),
        }
        for f in soup.find_all("form")
    ]
    headings = {f"h{i}": [content(h) for h in soup.find_all(f"h{i}")] for i in range(1, 7)}
    language = soup.html.get("lang", "") if soup.html else ""
    for n in soup.find_all(["script", "style", "noscript", "template", "head", "svg"]):
        n.decompose()
    for n in soup.select('[hidden],[aria-hidden="true"]'):
        if n.parent:
            n.decompose()
    body = soup.body or soup
    text = clean(body.get_text(" ", strip=True))
    main = body.find("main") or body.find(attrs={"role": "main"})
    articles = body.find_all("article")
    if main is None and len(articles) == 1:
        main = articles[0]
    main_words = len(main.get_text(" ", strip=True).split()) if main else 0
    use_main = main is not None and main_words >= 0.35 * len(text.split())
    if use_main:
        main_text = clean(main.get_text(" ", strip=True))
        method = "main_landmark_or_single_article"
    else:
        for n in body.find_all(["nav", "footer", "header", "aside"]):
            n.decompose()
        main_text = clean(body.get_text(" ", strip=True))
        method = "body_without_common_boilerplate"
    return {
        "title": titles[0] if titles else "",
        "titles": titles,
        "meta_descriptions": metas.get("description", []),
        "meta_description": (metas.get("description") or [""])[0],
        "meta": metas,
        "headings": headings,
        "language": language,
        "canonical": canonicals,
        "hreflang": hreflang,
        "pagination": pagination,
        "links": links,
        "images": images,
        "jsonld": jsonld,
        "jsonld_errors": jsonld_errors,
        "schema_types": sorted(types),
        "microdata_types": microdata,
        "forms": forms,
        "script_count": script_count,
        "text": text,
        "main_text": main_text,
        "main_text_method": method,
        "body_word_count": len(text.split()),
        "word_count": len(main_text.split()),
        "content_sha256": hashlib.sha256(main_text.encode()).hexdigest(),
        "markdown": markdown_from_html(html, url),
        "custom": custom,
        "encoding": soup.original_encoding,
        "text_visibility": "HTML heuristic; external CSS, layout and interactions are not evaluated",
    }


def index_signals(data, headers, status, final_url):
    # Preserve directives by agent; do not merge another crawler's restrictions into Google's.
    generic = list(data.get("meta", {}).get("robots", []))
    google = list(data.get("meta", {}).get("googlebot", []))
    raw_header = headers.get("x-robots-tag", "")
    agent = None
    header_generic = []
    header_google = []
    for segment in raw_header.split(","):
        segment = segment.strip()
        match = re.match(r"^([\w-]+)\s*:\s*(.*)$", segment)
        if match and match.group(1).lower() not in (
            "unavailable_after",
            "max-snippet",
            "max-image-preview",
            "max-video-preview",
        ):
            agent = match.group(1).lower()
            segment = match.group(2)
        if agent is None:
            header_generic.append(segment)
        elif agent == "googlebot":
            header_google.append(segment)
    values = generic + google + header_generic + header_google
    tokens = {t for s in values for t in re.split(r"[\s,]+", s.lower()) if t}
    noindex = bool(tokens & {"noindex", "none"})
    canonical = [c["url"] for c in data.get("canonical", []) if c["url"]]
    return {
        "googlebot_noindex_observed": noindex,
        "generic_meta": generic,
        "googlebot_meta": google,
        "x_robots_tag": raw_header,
        "canonical_elsewhere": any(normalize_url(c) != normalize_url(final_url) for c in canonical),
        "indexability_candidate": 200 <= status < 300
        and not noindex
        and not any(normalize_url(c) != normalize_url(final_url) for c in canonical),
        "indexing_status": "not_verified",
        "note": "Candidate only: search-engine robots policy, rendering and actual indexing require separate evidence.",
    }


def page_findings(page):
    from .evidence import capture_quality, combined_index_signals, missing_content, selected_data

    issues = []
    url = page["url"]
    d, representation = selected_data(page)
    quality = capture_quality(page)

    def add(code, severity, evidence, action, confidence="observed"):
        if (
            code
            in {
                "missing_title",
                "missing_description",
                "missing_h1",
                "canonical_not_declared",
                "missing_image_alt",
                "missing_content_candidate",
            }
            and not quality["absence_supported"]
        ):
            return
        issues.append(
            {
                "url": url,
                "code": code,
                "severity": severity,
                "evidence": evidence,
                "action": action,
                "confidence": confidence,
                "representation": representation,
            }
        )

    if page.get("error"):
        add(
            "fetch_failed",
            "high",
            page["error"],
            "Inspect the recorded failure and retry after resolving the cause.",
        )
        return issues
    status = page.get("status", 0)
    if status >= 400:
        add(
            "http_error",
            "high",
            str(status),
            "Restore the intended page or update links to its valid replacement.",
        )
        return issues
    if len(page.get("redirects", [])) > 1:
        add(
            "redirect_chain",
            "medium",
            json.dumps(page["redirects"]),
            "Point internal links directly at the intended final URL.",
        )
    if not d:
        return issues
    if quality["limits"]:
        add(
            "capture_incomplete",
            "medium",
            "; ".join(quality["limits"]),
            "Inspect access and browser evidence, then recapture this URL before assessing missing content.",
        )
    missing = missing_content(page)
    if missing:
        add(
            "missing_content_candidate",
            "high",
            json.dumps(missing),
            "Review the captured missing-content screen, repair referring links and return an appropriate HTTP status.",
            "heuristic",
        )
        return issues
    raw = page.get("data") or {}
    if representation == "rendered" and d.get("word_count", 0) > raw.get("word_count", 0) + 50:
        add(
            "javascript_content",
            "info",
            f"Initial main words: {raw.get('word_count', 0)}; rendered: {d.get('word_count', 0)}.",
            "Main content depends on rendering. Consider delivering essential text and metadata in initial HTML; indexing is not established by this observation.",
            "observed",
        )
    if not d["title"]:
        add(
            "missing_title",
            "medium",
            "No nonempty title extracted.",
            "Write a descriptive title for this page.",
        )
    if len(d["titles"]) > 1:
        add(
            "multiple_titles",
            "medium",
            json.dumps(d["titles"]),
            "Keep one intended document title.",
        )
    if not d["meta_description"]:
        add(
            "missing_description",
            "low",
            "No nonempty meta description.",
            "Add a useful page-specific summary where appropriate.",
        )
    if not d["headings"]["h1"]:
        add(
            "missing_h1",
            "medium",
            "No H1 extracted.",
            "Check that the main page topic has an appropriate visible heading.",
        )
    if len(d["headings"]["h1"]) > 1:
        add(
            "multiple_h1_review",
            "low",
            json.dumps(d["headings"]["h1"]),
            "Review heading hierarchy; multiple H1s alone do not establish an SEO defect.",
            "review",
        )
    if not d["canonical"]:
        add(
            "canonical_not_declared",
            "low",
            "No HTML canonical link.",
            "Review URL variants; add a canonical when useful. HTTP Link canonicals are not parsed.",
            "review",
        )
    if len(d["canonical"]) > 1:
        add(
            "multiple_canonicals",
            "medium",
            json.dumps(d["canonical"]),
            "Resolve conflicting canonical declarations.",
        )
    if d["jsonld_errors"]:
        add(
            "jsonld_syntax_error",
            "medium",
            json.dumps(d["jsonld_errors"]),
            "Fix the JSON syntax; then validate semantic requirements separately.",
        )
    missing = [i for i in d["images"] if not i["alt_present"]]
    if missing:
        add(
            "missing_image_alt",
            "low",
            str(len(missing)) + " images lack an alt attribute.",
            "Describe informative images; use empty alt for decorative images.",
        )
    signals = combined_index_signals(page)
    if signals["googlebot_noindex_observed"]:
        add(
            "noindex_observed",
            "info",
            "A robots noindex/none directive applies.",
            "Confirm the directive matches the purpose of this page; intentional exclusions need no fix.",
            "review",
        )
    if signals["canonical_elsewhere"]:
        add(
            "canonical_elsewhere",
            "info",
            json.dumps(d["canonical"]),
            "Confirm that consolidation to the target page is intended.",
            "review",
        )
    if representation == "http" and d["word_count"] < 80 and d["script_count"]:
        add(
            "possible_js_shell",
            "medium",
            f"{d['word_count']} extracted words and {d['script_count']} scripts.",
            "Compare raw HTML with locally rendered HTML before diagnosing a rendering issue.",
            "heuristic",
        )
    for c in d["canonical"]:
        if c["url"] is None:
            add("invalid_canonical_url", "medium", str(c["raw"]), "Supply a valid canonical URL.")
    for item in deeper_page_findings(page, d, quality):
        add(**item)
    return issues


def deeper_page_findings(page, data, quality):
    """Small structural checks, not a Schema.org/rich-result or CWV validator."""
    result = []

    def add(code, evidence, action, severity="medium", confidence="review"):
        result.append(
            dict(
                code=code,
                severity=severity,
                evidence=json.dumps(evidence, ensure_ascii=False),
                action=action,
                confidence=confidence,
            )
        )

    if len(data.get("meta_descriptions", [])) > 1:
        add(
            "multiple_meta_descriptions",
            data["meta_descriptions"],
            "Keep one intended page description and remove duplicate template output.",
            confidence="observed",
        )
    blocks = data.get("jsonld", [])
    seen = set()
    entities = {}
    for block in blocks:
        fingerprint = json.dumps(block, sort_keys=True)
        if fingerprint in seen:
            add(
                "jsonld_duplicate_block",
                block,
                "Consolidate duplicate JSON-LD blocks without removing distinct entities.",
                confidence="observed",
            )
        seen.add(fingerprint)
        stack = [block]
        while stack:
            entity = stack.pop()
            if isinstance(entity, list):
                stack.extend(entity)
                continue
            if not isinstance(entity, dict):
                continue
            stack.extend(v for v in entity.values() if isinstance(v, (dict, list)))
            types = entity.get("@type", [])
            if isinstance(types, str):
                types = [types]
            if not isinstance(types, list) or any(not isinstance(t, str) for t in types):
                add(
                    "jsonld_invalid_type_shape",
                    entity.get("@type"),
                    "Use a type name or array of type names; verify the vocabulary separately.",
                    confidence="observed",
                )
            identity = entity.get("@id")
            if isinstance(identity, str):
                prior = entities.setdefault(identity, {})
                # Differing lists/descriptions can be legitimate merging; flag identity scalars only.
                for key in ("name", "url", "sku", "gtin"):
                    value = entity.get(key)
                    if isinstance(value, (str, int, float)):
                        if key in prior and prior[key] != value:
                            add(
                                "jsonld_entity_conflict",
                                {"@id": identity, "property": key, "values": [prior[key], value]},
                                "Review the conflicting identity values against visible facts; merge deliberately.",
                            )
                        prior[key] = value
    if quality["absence_supported"]:
        for image in data.get("images", []):
            if not image.get("width") or not image.get("height"):
                add(
                    "image_dimensions_review",
                    {
                        "src": image.get("src"),
                        "width": image.get("width"),
                        "height": image.get("height"),
                    },
                    "Inspect CSS aspect-ratio and rendered layout. Reserve image space where absent; missing HTML dimensions alone do not prove CLS.",
                    severity="low",
                )
            if image.get("loading") == "lazy" and image.get("fetchpriority") == "high":
                add(
                    "image_loading_conflict",
                    image.get("src"),
                    "Check whether this image is above the fold; align lazy loading and fetch priority with its actual role.",
                    severity="low",
                )
    langs = {}
    for alternate in data.get("hreflang", []):
        language = str(alternate.get("language", "")).lower()
        if language != "x-default" and not re.fullmatch(
            r"[a-z]{2,3}(?:-[a-z]{4})?(?:-[a-z]{2}|-\d{3})?", language
        ):
            add(
                "hreflang_format_review",
                alternate,
                "Verify the language/script/region combination against supported hreflang codes. Preserve genuine language support.",
            )
        target = alternate.get("url")
        if not target:
            add(
                "hreflang_invalid_target",
                alternate,
                "Use a valid absolute URL for the intended language page.",
                confidence="observed",
            )
        if language in langs and langs[language] != target:
            add(
                "hreflang_conflicting_target",
                {"language": language, "targets": [langs[language], target]},
                "Use one intended alternate per language-region value on this page.",
                confidence="observed",
            )
        langs[language] = target
    return result
