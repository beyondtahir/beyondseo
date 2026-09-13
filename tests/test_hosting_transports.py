"""Optional localhost protocol tests; no real hosting credentials are used."""

import importlib.util
import unittest


class HostingTransportTests(unittest.TestCase):
    @unittest.skipUnless(
        all(importlib.util.find_spec(p) for p in ["paramiko"]),
        "Install the hosting-test extra for localhost protocol tests",
    )
    def test_sftp_stage_apply_verify_rollback(self):
        import os
        import socket
        import tempfile
        import threading
        from pathlib import Path

        import paramiko

        from beyondseo.publishing import RemoteStore, apply_change, stage

        class Auth(paramiko.ServerInterface):
            def check_auth_password(self, u, p):
                return (
                    paramiko.AUTH_SUCCESSFUL
                    if (u, p) == ("fixture", "fixture-only")
                    else paramiko.AUTH_FAILED
                )

            def check_channel_request(self, kind, chanid):
                return paramiko.OPEN_SUCCEEDED

        class Files(paramiko.SFTPServerInterface):
            def local(self, p):
                return root / str(p).lstrip("/")

            def canonicalize(self, p):
                return p

            def stat(self, p):
                return paramiko.SFTPAttributes.from_stat(self.local(p).stat())

            lstat = stat

            def open(self, p, flags, attr):
                try:
                    fd = os.open(self.local(p), flags, 0o600)
                    mode = "r+b" if flags & os.O_RDWR else "wb" if flags & os.O_WRONLY else "rb"
                    f = os.fdopen(fd, mode)
                    h = paramiko.SFTPHandle(flags)
                    h.readfile = f
                    h.writefile = f
                    return h
                except OSError as e:
                    return paramiko.SFTPServer.convert_errno(e.errno)

            def chattr(self, p, attr):
                if attr.st_mode is not None:
                    os.chmod(self.local(p), attr.st_mode)
                return paramiko.SFTP_OK

            def posix_rename(self, a, b):
                os.replace(self.local(a), self.local(b))
                return paramiko.SFTP_OK

            def remove(self, p):
                try:
                    self.local(p).unlink()
                    return paramiko.SFTP_OK
                except OSError as e:
                    return paramiko.SFTPServer.convert_errno(e.errno)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "www").mkdir()
            (root / "www/index.html").write_text("before")
            draft = root / "draft.html"
            draft.write_text("after")
            key = paramiko.RSAKey.generate(2048)
            server = socket.socket()
            server.bind(("127.0.0.1", 0))
            server.listen(1)
            port = server.getsockname()[1]
            known = root / "known_hosts"
            known.write_text(f"[127.0.0.1]:{port} {key.get_name()} {key.get_base64()}\n")
            ready = threading.Event()
            done = threading.Event()

            def serve():
                conn, _ = server.accept()
                t = paramiko.Transport(conn)
                t.add_server_key(key)
                t.set_subsystem_handler("sftp", paramiko.SFTPServer, Files)
                t.start_server(server=Auth())
                ready.set()
                done.wait(30)
                t.close()

            thread = threading.Thread(target=serve, daemon=True)
            thread.start()
            for env_name in ("BEYONDSEO_TEST_USERNAME", "BEYONDSEO_TEST_PASSWORD"):
                old_value = os.environ.get(env_name)
                if old_value is None:
                    self.addCleanup(os.environ.pop, env_name, None)
                else:
                    self.addCleanup(os.environ.__setitem__, env_name, old_value)
            os.environ["BEYONDSEO_TEST_USERNAME"] = "fixture"
            os.environ["BEYONDSEO_TEST_PASSWORD"] = "fixture-only"
            store = RemoteStore(
                {
                    "type": "sftp",
                    "username_env": "BEYONDSEO_TEST_USERNAME",
                    "password_env": "BEYONDSEO_TEST_PASSWORD",
                    "host": "127.0.0.1",
                    "port": port,
                    "root": "/www",
                    "known_hosts": str(known),
                }
            )
            try:
                result = stage(store, "index.html", draft, root / "plan")
                assert (root / "www/index.html").read_text() == "before"
                assert (
                    apply_change(store, root / "plan", result["plan_sha256"])["status"] == "applied"
                )
                assert (root / "www/index.html").read_text() == "after"
                assert (
                    apply_change(store, root / "plan", result["plan_sha256"], True)["status"]
                    == "rolled_back"
                )
                assert (root / "www/index.html").read_text() == "before"
                assert not list((root / "www").glob("*.beyondseo-*"))
            finally:
                store.close()
                done.set()
                server.close()
                thread.join(3)

    @unittest.skipUnless(
        all(importlib.util.find_spec(p) for p in ["paramiko", "pyftpdlib", "OpenSSL"]),
        "Install the hosting-test extra for localhost protocol tests",
    )
    def test_ftps_stage_apply_verify_rollback(self):
        import errno
        import ipaddress
        import json
        import logging
        import os
        import ssl
        import tempfile
        import threading
        from datetime import datetime, timedelta, timezone
        from pathlib import Path
        from unittest.mock import patch

        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID
        from pyftpdlib.authorizers import DummyAuthorizer
        from pyftpdlib.filesystems import AbstractedFS
        from pyftpdlib.handlers import TLS_FTPHandler
        from pyftpdlib.servers import FTPServer

        from beyondseo.publishing import RemoteStore, apply_change, stage

        self.addCleanup(logging.disable, logging.root.manager.disable)
        logging.disable(logging.CRITICAL)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "www").mkdir()
            (root / "www/index.html").write_text("before")
            draft = root / "draft.html"
            draft.write_text("after")
            key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
            now = datetime.now(timezone.utc)
            cert = (
                x509.CertificateBuilder()
                .subject_name(name)
                .issuer_name(name)
                .public_key(key.public_key())
                .serial_number(x509.random_serial_number())
                .not_valid_before(now - timedelta(minutes=5))
                .not_valid_after(now + timedelta(days=1))
                .add_extension(
                    x509.SubjectAlternativeName(
                        [x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
                    ),
                    critical=False,
                )
                .sign(key, hashes.SHA256())
            )
            certfile = root / "cert.pem"
            keyfile = root / "key.pem"
            certfile.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
            keyfile.write_bytes(
                key.private_bytes(
                    serialization.Encoding.PEM,
                    serialization.PrivateFormat.PKCS8,
                    serialization.NoEncryption(),
                )
            )
            authorizer = DummyAuthorizer()
            authorizer.add_user("fixture", "fixture-only", str(root), perm="elradfmwMT")

            class ReplaceFileSystem(AbstractedFS):
                reject_replacement = False

                def rename(self, src, dst):
                    if self.reject_replacement and os.path.exists(dst):
                        raise FileExistsError(errno.EEXIST, "File exists", dst)
                    # Model a server with replacement support on every runner OS.
                    os.replace(src, dst)

            class Handler(TLS_FTPHandler):
                pass

            Handler.abstracted_fs = ReplaceFileSystem
            Handler.authorizer = authorizer
            Handler.certfile = str(certfile)
            Handler.keyfile = str(keyfile)
            Handler.tls_control_required = True
            Handler.tls_data_required = True
            server = FTPServer(("127.0.0.1", 0), Handler)
            port = server.socket.getsockname()[1]
            thread = threading.Thread(
                target=lambda: server.serve_forever(timeout=0.05, handle_exit=False), daemon=True
            )
            thread.start()
            for env_name in ("BEYONDSEO_TEST_USERNAME", "BEYONDSEO_TEST_PASSWORD"):
                old_value = os.environ.get(env_name)
                if old_value is None:
                    self.addCleanup(os.environ.pop, env_name, None)
                else:
                    self.addCleanup(os.environ.__setitem__, env_name, old_value)
            os.environ["BEYONDSEO_TEST_USERNAME"] = "fixture"
            os.environ["BEYONDSEO_TEST_PASSWORD"] = "fixture-only"
            profile = {
                "type": "ftps",
                "username_env": "BEYONDSEO_TEST_USERNAME",
                "password_env": "BEYONDSEO_TEST_PASSWORD",
                "host": "127.0.0.1",
                "port": port,
                "root": "/www",
            }
            try:
                try:
                    RemoteStore(profile)
                    raise AssertionError("Untrusted certificate was accepted")
                except ValueError:
                    pass
                context = ssl.create_default_context(cafile=str(certfile))
                assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname
                with patch("beyondseo.publishing.ssl.create_default_context", return_value=context):
                    store = RemoteStore(profile)
                try:
                    result = stage(store, "index.html", draft, root / "plan")
                    assert (root / "www/index.html").read_text() == "before"
                    assert (
                        apply_change(store, root / "plan", result["plan_sha256"])["status"]
                        == "applied"
                    )
                    assert (root / "www/index.html").read_text() == "after"
                    assert (
                        apply_change(store, root / "plan", result["plan_sha256"], True)["status"]
                        == "rolled_back"
                    )
                    assert (root / "www/index.html").read_text() == "before"
                    assert not list((root / "www").glob("*.beyondseo-*"))
                    # A server without this capability must preserve the live file.
                    ReplaceFileSystem.reject_replacement = True
                    refused = stage(store, "index.html", draft, root / "refused-plan")
                    with self.assertRaisesRegex(ValueError, "needs inspection"):
                        apply_change(store, root / "refused-plan", refused["plan_sha256"])
                    assert (root / "www/index.html").read_text() == "before"
                    assert (root / "refused-plan/before.txt").read_text() == "before"
                    receipt = json.loads((root / "refused-plan/receipt.json").read_text())
                    assert receipt["status"] == "needs_inspection"
                    assert not list((root / "www").glob("*.beyondseo-*"))
                finally:
                    store.close()
            finally:
                server.close_all()
                thread.join(3)
