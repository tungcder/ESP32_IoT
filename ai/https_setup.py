"""Create a private local CA and a server certificate; never install trust silently."""
import argparse
from datetime import datetime, timedelta, timezone
import ipaddress
import json
from pathlib import Path
import socket

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

CERTS = Path(__file__).with_name(".certs")
CONFIG = Path(__file__).with_name("config.local.json")


def default_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("192.0.2.1", 80))
            return probe.getsockname()[0]
    except OSError:
        raise ValueError("Khong tim duoc IP LAN. Chay setup.ps1 -LaptopIP IP-WiFi-laptop.") from None


def save_key(path, key):
    path.write_bytes(key.private_bytes(serialization.Encoding.PEM,
                                     serialization.PrivateFormat.PKCS8,
                                     serialization.NoEncryption()))


def create_certificates(address, port=8090, directory=CERTS):
    if not 1024 <= port <= 65534:
        raise ValueError("Cong HTTPS can nam trong 1024..65534; cong tiep theo danh cho cai dat.")
    address = str(ipaddress.IPv4Address(address))
    if ipaddress.ip_address(address).is_loopback or address == "0.0.0.0":
        raise ValueError("Can IP LAN cua laptop, khong dung localhost hay 0.0.0.0.")
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    ca_key_path, ca_path = directory / "ca-key.pem", directory / "ca.pem"
    if ca_path.exists() != ca_key_path.exists():
        raise ValueError("Thieu khoa hoac chung chi CA. Khoi phuc ca.pem va ca-key.pem cung cap.")
    if ca_path.exists():
        ca = x509.load_pem_x509_certificate(ca_path.read_bytes())
        ca_key = serialization.load_pem_private_key(ca_key_path.read_bytes(), password=None)
        if (ca.not_valid_after_utc < now + timedelta(days=370)
                or ca.public_key().public_numbers() != ca_key.public_key().public_numbers()):
            raise ValueError("CA sap het han hoac khong khop khoa. Tao bo CA moi va cai lai tren iPhone.")
    else:
        ca_key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "ESP32 Robot Camera Local CA")])
        ca = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
              .public_key(ca_key.public_key()).serial_number(x509.random_serial_number())
              .not_valid_before(now - timedelta(days=1)).not_valid_after(now + timedelta(days=3650))
              .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
              .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False,
                                          key_encipherment=False, data_encipherment=False,
                                          key_agreement=False, key_cert_sign=True, crl_sign=True,
                                          encipher_only=False, decipher_only=False), critical=True)
              .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), critical=False)
              .sign(ca_key, hashes.SHA256()))
        save_key(ca_key_path, ca_key)
        ca_path.write_bytes(ca.public_bytes(serialization.Encoding.PEM))
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, address)])
    certificate = (x509.CertificateBuilder().subject_name(name).issuer_name(ca.subject)
                   .public_key(key.public_key()).serial_number(x509.random_serial_number())
                   .not_valid_before(now - timedelta(hours=1)).not_valid_after(now + timedelta(days=365))
                   .add_extension(x509.SubjectAlternativeName([
                       x509.IPAddress(ipaddress.ip_address(address)),
                       x509.IPAddress(ipaddress.ip_address("127.0.0.1")), x509.DNSName("localhost")]), critical=False)
                   .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
                   .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
                   .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False,
                                               key_encipherment=True, data_encipherment=False,
                                               key_agreement=False, key_cert_sign=False, crl_sign=False,
                                               encipher_only=False, decipher_only=False), critical=True)
                   .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
                   .sign(ca_key, hashes.SHA256()))
    save_key(directory / "server-key.pem", key)
    (directory / "server.pem").write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    (directory / "iphone-root.cer").write_bytes(ca.public_bytes(serialization.Encoding.DER))
    fingerprint = ca.fingerprint(hashes.SHA256()).hex().upper()
    metadata = dict(ip=address, port=port, fingerprint=fingerprint,
                    public_url=f"https://{address}:{port}", expires=certificate.not_valid_after_utc.isoformat())
    (directory / "info.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def main():
    parser = argparse.ArgumentParser(description="Create local HTTPS certificate for iPhone camera")
    parser.add_argument("--ip", default="")
    parser.add_argument("--port", type=int, default=8090)
    args = parser.parse_args()
    info = create_certificates(args.ip or default_ip(), args.port)
    saved = json.loads(CONFIG.read_text(encoding="utf-8")) if CONFIG.exists() else {}
    config = {key: saved[key] for key in ("robot_url",) if key in saved}
    config["public_url"] = info["public_url"]
    temp = CONFIG.with_suffix(".tmp")
    temp.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(CONFIG)
    print("HTTPS: " + info["public_url"])
    print("iPhone setup: http://" + info["ip"] + ":" + str(args.port + 1))
    print("CA SHA256: " + info["fingerprint"])
    print("Public certificate: " + str(CERTS / "iphone-root.cer"))
    print("Read ai/README.md to trust the certificate on iPhone and Windows once.")


if __name__ == "__main__":
    main()
