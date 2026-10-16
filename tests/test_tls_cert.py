import datetime
import tempfile
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtensionOID, NameOID

import main


def test_ssl_cert_generation_validity_and_sans(monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        monkeypatch.setattr(main, "APP_DATA_DIR", Path(td))

        cert_file, key_file = main._ensure_ssl_cert()

        assert Path(cert_file).exists()
        assert Path(key_file).exists()

        cert_data = Path(cert_file).read_bytes()
        cert = x509.load_pem_x509_certificate(cert_data)

        # 1. Check validity is ~1 year (365 days)
        validity_days = (cert.not_valid_after_utc - cert.not_valid_before_utc).days
        assert 360 <= validity_days <= 366

        # 2. Check Subject Alternative Names (SANs)
        san_ext = cert.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME).value
        dns_names = [name.value for name in san_ext if isinstance(name, x509.DNSName)]
        ip_addresses = [str(name.value) for name in san_ext if isinstance(name, x509.IPAddress)]

        assert "localhost" in dns_names
        assert "127.0.0.1" in ip_addresses


def test_ssl_cert_regenerates_when_expired(monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        ssl_dir = Path(td) / "data" / "output" / "ssl"
        ssl_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(main, "APP_DATA_DIR", Path(td))

        cert_path = ssl_dir / "cert.pem"
        key_path = ssl_dir / "key.pem"

        # Create an expired certificate
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
        two_years_ago = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=730)
        one_year_ago = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=365)

        expired_cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(1)
            .not_valid_before(two_years_ago)
            .not_valid_after(one_year_ago)
            .sign(key, hashes.SHA256())
        )
        cert_path.write_bytes(expired_cert.public_bytes(serialization.Encoding.PEM))
        key_path.write_bytes(key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        ))

        # Check expired detection
        assert main._is_cert_valid_and_current(cert_path) is False

        # _ensure_ssl_cert should regenerate it
        c_res, k_res = main._ensure_ssl_cert()
        assert Path(c_res).exists()

        # The new cert must be currently valid
        new_cert = x509.load_pem_x509_certificate(Path(c_res).read_bytes())
        now = datetime.datetime.now(datetime.timezone.utc)
        assert new_cert.not_valid_after_utc > now
        assert main._is_cert_valid_and_current(Path(c_res)) is True
