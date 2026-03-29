"""
SSL certificate generator for Echo-Sign.
Run this script from Sign2Text/scripts to create certs in Sign2Text/.
"""

import subprocess
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent.parent


def generate_ssl_certs():
    """Generate a self-signed SSL certificate and key in the app root."""
    cert_path = APP_DIR / "cert.pem"
    key_path = APP_DIR / "key.pem"

    if cert_path.exists() and key_path.exists():
        print("SSL certificates already exist:")
        print(f"  Certificate: {cert_path}")
        print(f"  Private Key: {key_path}")
        return True

    print("Generating SSL certificates...")

    cmd = [
        "openssl", "req", "-x509",
        "-newkey", "rsa:4096",
        "-nodes",
        "-out", str(cert_path),
        "-keyout", str(key_path),
        "-days", "365",
        "-subj", "/CN=localhost/O=Echo-Sign/C=IN",
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print("SSL certificates generated successfully.")
            print(f"  Certificate: {cert_path}")
            print(f"  Private Key: {key_path}")
            print("Note: Browsers will warn because this is a self-signed certificate.")
            return True

        print(f"OpenSSL error: {result.stderr}")
        return False
    except FileNotFoundError:
        print("OpenSSL not found.")
        print("Attempting Python-based certificate generation...")
        return generate_ssl_with_python(cert_path, key_path)


def generate_ssl_with_python(cert_path, key_path):
    """Fallback: generate SSL certs using the cryptography package."""
    try:
        import datetime

        from cryptography import x509
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID

        key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=4096,
            backend=default_backend(),
        )

        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "IN"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Echo-Sign"),
            x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
        ])

        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.datetime.utcnow())
            .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365))
            .add_extension(
                x509.SubjectAlternativeName([
                    x509.DNSName("localhost"),
                    x509.DNSName("127.0.0.1"),
                ]),
                critical=False,
            )
            .sign(key, hashes.SHA256(), default_backend())
        )

        with open(key_path, "wb") as file_obj:
            file_obj.write(key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            ))

        with open(cert_path, "wb") as file_obj:
            file_obj.write(cert.public_bytes(serialization.Encoding.PEM))

        print("SSL certificates generated successfully using Python.")
        print(f"  Certificate: {cert_path}")
        print(f"  Private Key: {key_path}")
        return True
    except ImportError:
        print("cryptography is not installed. Run: pip install cryptography")
        return False
    except Exception as exc:
        print(f"Error generating certificates: {exc}")
        return False


if __name__ == "__main__":
    success = generate_ssl_certs()
    sys.exit(0 if success else 1)
