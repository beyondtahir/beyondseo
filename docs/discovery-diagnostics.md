# Diagnose the failed operation

A skill can be installed while its Python executable, browser or network access is unavailable. A target site can be reachable while a search provider is unavailable. Keep these observations separate.

```sh
beyondseo doctor
# Optional bounded network probes; use a fresh output directory:
beyondseo doctor --target https://example.com --query 'Example company' --out runs/doctor
```

The report separates skill registration (unknown to Python; confirm in the host), native engine, browser runtime, target response, search availability and source-verification runtime. Default `doctor` makes no website requests. Optional probes preserve exact access errors and provider attempts. A successful probe does not promise access to other sites. If the shell itself cannot execute Python, the host must report that denied command: Python cannot diagnose an invocation it never received.

| Observed failure | Minimal next step |
|---|---|
| Missing Python package | Run the existing `scripts/setup.py --venv <approved-runtime>` setup in an allowed execution directory, or install the named dependency in the selected runtime. |
| Chromium executable missing | In that runtime, run `python -m playwright install chromium`. HTTP evidence remains usable. |
| Python/browser execution denied | Confirm the exact executable and path. Use the host-approved execution directory; request permission for that specific operation if supported. Reinstalling browser files does not grant execution permission. |
| Explicit environment network restriction | Ask for the required host/network operation through supported controls, or use `--offline` and supplied evidence. Do not attempt to bypass the policy using another transport. |
| DNS, connection or TLS failure | Inspect the hostname and recorded exception. Retry only after fixing connectivity, DNS or certificate trust; never disable TLS verification. |
| HTTP 401/403 | Preserve status/body evidence. The response alone does not identify a CAPTCHA, provider policy or host policy. Try another independently permitted source if appropriate. |
| Recognized CAPTCHA/challenge | Stop that source; use another permitted source or supplied results. |
| HTTP 429 | Respect the provider's limit; use another permitted source or return later. No retry loop. |
| Robots disallow | Do not fetch that search URL. Another permitted source or a supplied snapshot can be used. |
| Robots policy unavailable | Inspect the nested robots fetch status/error. No disallow rule has been established. |
| `robots_scope_limited` / `redirect_out_of_scope` | Inspect the recorded redirect. For a normal site audit, `--include-www` covers the exact www/non-www pair while preserving robots and public-address checks. Use a fresh output folder when changing scope. Other domains require explicit scope review; this is not a robots-disallow override. |
| Tool unavailable | Use a supported native method or supplied evidence. Do not invent a host tool. |
| Successful empty / own-site-only results | Report `empty_results` / `no_relevant_results`; refine a relevant query or try another source. This is not a network failure. |
| Response received, parser failed | Retain the response snapshot and SHA-256; inspect its structure. Do not report zero backlinks. |
| Cause unknown | Preserve the operation, timestamp, provider, status and error. Do not assign blame without additional evidence. |

## Claude Code

Confirm `/skills` or the installed skill invocation and run `doctor` using the selected Python runtime. Check the actual tools: `WebSearch` and `WebFetch` are distinct from Bash and native Chromium. If WebSearch is denied, use `/permissions` to inspect its specific rule and request that tool when appropriate. A shell or network denial needs the specific command/domain authorization. Do not enable a blanket bypass. Claude's documented WebSearch uses Anthropic's backend; a reported failure is not automatically a Google browser block. Keep its raw tool error.

Official references: [tools](https://code.claude.com/docs/en/tools-reference), [permissions](https://code.claude.com/docs/en/permissions), [sandboxing](https://code.claude.com/docs/en/sandboxing).

## Codex

Confirm the skill appears in the host's skill list. Run `doctor` in the actual task environment. Search-tool availability, shell network permissions and browser execution are separate. Use the current surface's permission control (CLI: `/permissions`) to allow the specific necessary action, within managed policy. A local desktop result does not establish cloud access. No universal Full access setting is required by BeyondSEO.

Official references: [skills](https://learn.chatgpt.com/docs/build-skills), [sandbox and permissions](https://learn.chatgpt.com/docs/sandboxing).

## ChatGPT Work

Confirm that the workspace accepted the skill; format validation alone cannot confirm registration. Run the engine in an execution directory approved by Work, using the installer's `--runtime` path. A save HTTP 422 without details remains an unexplained submission rejection. A later Python “Permission denied” is a separate execution failure.

When an explicit code/shell network restriction is observed and policy permits it, the documented control is **Settings → Data controls → Work network access → Allow public internet access**, when available. Changes apply after the current run finishes and the environment refreshes. Web search and the remote browser have separate controls. Do not change these settings merely because one provider returned an error. If the control is unavailable, use the workspace administrator's supported process or supplied evidence.

Official reference: [code and shell sandboxing](https://learn.chatgpt.com/docs/sandboxing). Other hosts use the same capability checks; their names do not prove compatibility.

## Test boundaries

Automated fixtures cover blocked-source fallback, empty versus parser failure, permission categories, imports, provenance, partial captures and competitor relevance. Local native/browser validation does not certify a hosted skill scanner or another agent's permissions. Report the environments actually exercised for each release. Never describe the system as universally compatible or foolproof.
