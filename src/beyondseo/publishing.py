"""Stage, apply and roll back one reviewed UTF-8 content file at a time."""

from __future__ import annotations

import difflib
import hashlib
import io
import json
import os
import posixpath
import ssl
import stat
import tempfile
import uuid
from pathlib import Path, PurePosixPath

from .network import utcnow

LIMIT = 5_000_000
CONTENT_EXTENSIONS = {
    ".html",
    ".htm",
    ".md",
    ".mdx",
    ".txt",
    ".json",
    ".xml",
    ".css",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".php",
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def relative_file(value):
    p = PurePosixPath(value)
    if (
        not value
        or p.is_absolute()
        or "\\" in value
        or any(ord(c) < 32 for c in value)
        or any(x in ("", ".", "..") or x.startswith(".") for x in value.split("/"))
    ):
        raise ValueError(
            "Use an ordinary relative content path without hidden directories or traversal."
        )
    if p.suffix.lower() not in CONTENT_EXTENSIONS or p.name.lower() in (
        "wp-config.php",
        "config.php",
    ):
        raise ValueError(
            "This command accepts website content files, not credentials or server configuration."
        )
    return str(p)


def text_bytes(data):
    if len(data) > LIMIT or b"\0" in data:
        raise ValueError("Content must be UTF-8 text of at most 5 MB.")
    data.decode("utf-8")
    return data


def private_write(path, data):
    path = Path(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())


def state_write(folder, data):
    temp = folder / (".receipt-" + uuid.uuid4().hex)
    private_write(temp, json.dumps(data, indent=2).encode())
    temp.replace(folder / "receipt.json")


class LocalStore:
    def __init__(self, root):
        self.root = Path(root).resolve(strict=True)
        if not self.root.is_dir():
            raise ValueError("Site root must be an existing directory.")
        self.identity = {"type": "local", "root": str(self.root)}

    def path(self, name):
        name = relative_file(name)
        target = self.root
        for part in PurePosixPath(name).parts:
            target = target / part
            if target.is_symlink():
                raise ValueError("Symlink content paths are not supported.")
        if not target.is_file() or not target.resolve().is_relative_to(self.root):
            raise ValueError("Content file must already exist within the site root.")
        return target

    def read(self, name):
        with self.path(name).open("rb") as f:
            return text_bytes(f.read(LIMIT + 1))

    def replace(self, name, data, expected):
        target = self.path(name)
        if digest(self.read(name)) != expected:
            raise ValueError("Content changed since review; make a fresh plan.")
        fd, temp = tempfile.mkstemp(prefix=".beyondseo-", dir=target.parent)
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            os.chmod(temp, stat.S_IMODE(target.stat().st_mode))
            if digest(self.read(name)) != expected:
                raise ValueError("Concurrent change detected before replacement.")
            os.replace(temp, target)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)

    def close(self):
        pass


class RemoteStore:
    """Encrypted file access; supports existing files and server-side rename only."""

    def __init__(self, profile):
        allowed = {
            "type",
            "host",
            "port",
            "root",
            "username_env",
            "password_env",
            "key_file",
            "known_hosts",
        }
        if not isinstance(profile, dict) or set(profile) - allowed:
            raise ValueError(
                "Connection profiles contain host/root and credential references only."
            )
        if profile.get("type") not in ("sftp", "ftps"):
            raise ValueError("Remote access supports SFTP or explicit FTPS.")
        if (
            not profile.get("host")
            or not profile.get("root", "").startswith("/")
            or profile["root"] == "/"
        ):
            raise ValueError("Supply a host and a specific absolute website root, not '/'.")
        self.profile = profile
        self.identity = {k: profile[k] for k in ("type", "host", "root")}
        self.identity["root"] = posixpath.normpath(profile["root"])
        if self.identity["root"] == "/" or any(ord(c) < 32 for c in profile["root"]):
            raise ValueError("Choose a specific website root.")
        self.identity["port"] = int(profile.get("port", 22 if profile["type"] == "sftp" else 21))
        username = os.environ.get(profile.get("username_env", "BEYONDSEO_USERNAME"))
        password = os.environ.get(profile.get("password_env", "BEYONDSEO_PASSWORD"))
        if not username:
            raise ValueError(
                "Set the username environment variable named in the connection profile."
            )
        if not password and (profile["type"] == "ftps" or not profile.get("key_file")):
            raise ValueError(
                "Set the password environment variable or configure an SFTP private key."
            )
        self.client = None
        self.sftp = None
        try:
            if profile["type"] == "sftp":
                import paramiko

                self.client = paramiko.SSHClient()
                self.client.load_system_host_keys()
                if profile.get("known_hosts"):
                    self.client.load_host_keys(str(Path(profile["known_hosts"]).expanduser()))
                self.client.set_missing_host_key_policy(paramiko.RejectPolicy())
                self.client.connect(
                    profile["host"],
                    port=self.identity["port"],
                    username=username,
                    password=password,
                    key_filename=str(Path(profile["key_file"]).expanduser())
                    if profile.get("key_file")
                    else None,
                    timeout=20,
                    banner_timeout=20,
                    auth_timeout=20,
                    look_for_keys=False,
                    allow_agent=False,
                )
                self.sftp = self.client.open_sftp()
                self.sftp.get_channel().settimeout(20)
                if self.sftp.normalize(self.identity["root"]) != self.identity["root"]:
                    raise ValueError("Use the canonical remote website root.")
            else:
                from ftplib import FTP_TLS

                self.client = FTP_TLS(context=ssl.create_default_context(), timeout=20)
                self.client.connect(profile["host"], self.identity["port"])
                self.client.login(username, password)
                self.client.prot_p()
                self.client.cwd(self.identity["root"])
                if self.client.pwd().rstrip("/") != self.identity["root"]:
                    raise ValueError("Use the canonical remote website root.")
        except Exception as e:
            self.close()
            raise ValueError(
                "Remote connection failed. Check the installed transport, credentials, server identity and root."
            ) from e

    def path(self, name):
        name = relative_file(name)
        current = self.identity["root"]
        parts = PurePosixPath(name).parts
        for i, part in enumerate(parts):
            parent = current
            current = posixpath.join(current, part)
            if self.sftp:
                mode = self.sftp.lstat(current).st_mode
                valid = stat.S_ISREG(mode) if i == len(parts) - 1 else stat.S_ISDIR(mode)
            else:
                entry = next(
                    (
                        facts
                        for filename, facts in self.client.mlsd(parent, facts=["type"])
                        if filename == part
                    ),
                    {},
                )
                valid = entry.get("type") == ("file" if i == len(parts) - 1 else "dir")
            if not valid:
                raise ValueError(
                    "Remote path must contain existing ordinary directories and a file; symlinks are not supported."
                )
        return current

    def read(self, name):
        path = self.path(name)
        if self.sftp:
            with self.sftp.open(path, "rb") as f:
                return text_bytes(f.read(LIMIT + 1))
        data = bytearray()

        def collect(chunk):
            data.extend(chunk)
            if len(data) > LIMIT:
                raise ValueError("Remote content exceeds 5 MB.")

        self.client.retrbinary("RETR " + path, collect)
        return text_bytes(bytes(data))

    def replace(self, name, data, expected):
        path = self.path(name)
        if digest(self.read(name)) != expected:
            raise ValueError("Remote content changed since review; make a fresh plan.")
        temp = path + ".beyondseo-" + uuid.uuid4().hex
        try:
            if self.sftp:
                with self.sftp.open(temp, "wx") as f:
                    f.write(data)
                self.sftp.chmod(temp, stat.S_IMODE(self.sftp.stat(path).st_mode))
                with self.sftp.open(temp, "rb") as f:
                    uploaded = f.read(LIMIT + 1)
            else:
                self.client.storbinary("STOR " + temp, io.BytesIO(data))
                content = io.BytesIO()

                def bounded(chunk):
                    if content.tell() + len(chunk) > LIMIT:
                        raise ValueError("Uploaded content exceeds size limit.")
                    content.write(chunk)

                self.client.retrbinary("RETR " + temp, bounded)
                uploaded = content.getvalue()
            if digest(uploaded) != digest(data) or digest(self.read(name)) != expected:
                raise ValueError("Upload verification or concurrent-content check failed.")
            if self.sftp:
                self.sftp.posix_rename(temp, path)
            else:
                self.client.rename(temp, path)
        finally:
            try:
                if self.sftp:
                    self.sftp.remove(temp)
                else:
                    self.client.delete(temp)
            except Exception:
                pass

    def close(self):
        if self.sftp:
            self.sftp.close()
        if self.client:
            self.client.close()


def open_store(site=None, connection=None):
    return (
        LocalStore(site)
        if site
        else RemoteStore(json.loads(Path(connection).read_text(encoding="utf-8")))
    )


def stage(store, name, replacement, out):
    name = relative_file(name)
    out = Path(out).resolve()
    if isinstance(store, LocalStore) and out.is_relative_to(store.root):
        raise ValueError("Keep change plans and backups outside the website root.")
    if out.exists():
        raise ValueError("Choose a new folder for this change plan.")
    before = store.read(name)
    with Path(replacement).open("rb") as f:
        after = text_bytes(f.read(LIMIT + 1))
    if before == after:
        raise ValueError("Draft and current content are identical.")
    plan = {
        "schema_version": 1,
        "created_at": utcnow(),
        "target": store.identity,
        "file": name,
        "before_sha256": digest(before),
        "after_sha256": digest(after),
    }
    encoded = json.dumps(plan, sort_keys=True, indent=2).encode()
    out.mkdir(parents=True, mode=0o700)
    for filename, data in (("before.txt", before), ("after.txt", after), ("plan.json", encoded)):
        private_write(out / filename, data)
    patch = "".join(
        difflib.unified_diff(
            before.decode().splitlines(keepends=True),
            after.decode().splitlines(keepends=True),
            fromfile=name + " (current)",
            tofile=name + " (proposed)",
        )
    )
    private_write(out / "review.diff", patch.encode())
    return {
        "status": "staged",
        "file": name,
        "plan_sha256": digest(encoded),
        "next_step": "Review the diff and replacement, then apply this exact plan hash to the same target.",
    }


def apply_change(store, folder, expected_plan, rollback=False):
    folder = Path(folder)
    if isinstance(store, LocalStore) and folder.resolve().is_relative_to(store.root):
        raise ValueError("Keep plans and backups outside the website root.")
    for filename in ("plan.json", "before.txt", "after.txt"):
        if (folder / filename).is_symlink():
            raise ValueError("Plan artifacts must not be symlinks.")
    raw = (folder / "plan.json").read_bytes()
    if digest(raw) != expected_plan:
        raise ValueError("The plan differs from the reviewed hash.")
    plan = json.loads(raw)
    if plan.get("schema_version") != 1 or plan["target"] != store.identity:
        raise ValueError("Plan and selected website target do not match.")
    name = relative_file(plan["file"])
    before = text_bytes((folder / "before.txt").read_bytes())
    after = text_bytes((folder / "after.txt").read_bytes())
    if digest(before) != plan["before_sha256"] or digest(after) != plan["after_sha256"]:
        raise ValueError("Staged content or backup was changed after review.")
    lock = folder / "change.lock"
    try:
        private_write(lock, str(os.getpid()).encode())
    except FileExistsError as e:
        raise ValueError(
            "This change plan is in use; inspect its lock and receipt before recovery."
        ) from e
    receipt = {
        "plan_sha256": expected_plan,
        "file": name,
        "started_at": utcnow(),
        "operation": "rollback" if rollback else "apply",
        "status": "checking",
    }
    try:
        current = after if rollback else before
        replacement = before if rollback else after
        if digest(store.read(name)) != digest(current):
            raise ValueError(
                "Current content differs from the expected version; review before overwriting."
            )
        receipt["status"] = "writing"
        state_write(folder, receipt)
        try:
            store.replace(name, replacement, digest(current))
            if digest(store.read(name)) != digest(replacement):
                raise ValueError("Post-write content verification failed.")
        except Exception as e:
            receipt["status"] = "needs_inspection"
            state_write(folder, receipt)
            raise ValueError(
                "Write outcome needs inspection. The original backup is retained; check the target before retrying or rolling back."
            ) from e
        receipt.update(
            status="rolled_back" if rollback else "applied",
            verified_sha256=digest(replacement),
            finished_at=utcnow(),
        )
        state_write(folder, receipt)
        return receipt
    finally:
        lock.unlink()
