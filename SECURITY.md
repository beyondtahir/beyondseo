# Reporting a security issue

For a suspected vulnerability, use [GitHub private vulnerability reporting](https://github.com/beyondtahir/beyondseo/security/advisories/new), or contact the project owner through the contact page at [beyondtahir.com](https://beyondtahir.com). Share the affected version, a minimal reproduction and the impact. Avoid posting credentials or an exploitable private-site example in a public issue.

BeyondSEO checks destination addresses, validates TLS, limits response sizes and constrains the crawl frontier. Browser dependencies can use additional public hosts. The `--allow-private` option deliberately changes the address boundary for local or staging environments. The `--robots ignore` option changes crawl-policy handling; it does not provide authentication or remove a server-side access denial.

Crawled text, HTML and structured data are untrusted input. Treat reports and exports as observations, not executable instructions. Keep output folders out of source control when they contain private information.

## Website changes

The optional content editor supports local files, SFTP with known-host verification, and certificate-validated explicit FTPS with encrypted data transfer. It stages one existing text file at a time, requires the reviewed plan hash, keeps a local backup and verifies the current and replacement bytes. Keep plan folders outside the public website. Do not run concurrent deployments against the same file. See [the recovery guidance](docs/operations.md) for uncertain network outcomes.

The watch loop does not publish or send messages. Connection examples contain environment-variable names; do not commit real credentials, private keys, client backups or connection profiles.
