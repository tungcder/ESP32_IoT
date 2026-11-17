"""Find the laptop and robot on the current LAN without sending drive commands."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import ipaddress
import json
import os
from pathlib import Path
import socket
import subprocess
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, build_opener


def local_network(address=None):
    if address:
        interface = ipaddress.ip_interface(address if "/" in address else address + "/24")
    else:
        interface = None
        if os.name == "nt":
            # Prefer the connected Wi-Fi adapter over VPN and virtual adapters.
            script = """+$ErrorActionPreference = 'Stop'
$rows = @(Get-NetIPConfiguration | Where-Object {
  $_.IPv4DefaultGateway -and $_.IPv4Address -and
  $_.InterfaceAlias -notmatch 'Tailscale|VPN|vEthernet|Virtual|WSL'
} | ForEach-Object {
  foreach ($ip in $_.IPv4Address) {
    [PSCustomObject]@{ip=$ip.IPAddress; prefix=$ip.PrefixLength; name=$_.InterfaceAlias}
  }
})
ConvertTo-Json -InputObject $rows -Compress
"""
            try:
                result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                                        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=3)
                rows = json.loads(result.stdout or "[]")
                rows.sort(key=lambda row: not any(word in row["name"].lower()
                                                 for word in ("wi-fi", "wifi", "wireless", "wlan")))
                for row in rows:
                    candidate = ipaddress.ip_interface(f"{row['ip']}/{row['prefix']}")
                    if candidate.ip.is_private and not candidate.ip.is_loopback and not candidate.ip.is_link_local:
                        interface = candidate
                        break
            except (OSError, ValueError, KeyError, subprocess.TimeoutExpired):
                pass
        if interface is None:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
                    probe.connect(("192.0.2.1", 80))
                    interface = ipaddress.ip_interface(probe.getsockname()[0] + "/24")
            except OSError as error:
                raise ValueError("Chưa tìm được Wi-Fi của laptop. Kết nối Wi-Fi rồi chạy lại AI.") from error
    if (interface.version != 4 or not interface.ip.is_private or interface.ip.is_loopback
            or interface.ip.is_link_local or interface.ip.is_unspecified):
        raise ValueError("Cần IPv4 mạng nội bộ của laptop; dùng -LaptopIP nếu VPN chọn nhầm mạng.")
    return interface


def robot_status(value):
    """Recognize this project's status response, including older firmware."""
    return (isinstance(value, dict) and value.get("drive_mode") in ("AUTO", "MANUAL", "AI", "HYBRID")
            and value.get("movement") in ("STOPPED", "FORWARD", "BACKWARD", "LEFT", "RIGHT")
            and isinstance(value.get("uptime_ms"), int) and not isinstance(value["uptime_ms"], bool)
            and isinstance(value.get("events"), list))


def probe_robot(address, timeout=0.35):
    url = "http://" + str(address)
    try:
        # Numeric local addresses only; no proxies, redirects or control requests.
        from urllib.request import HTTPRedirectHandler

        class NoRedirect(HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None

        with build_opener(ProxyHandler({}), NoRedirect()).open(url + "/status", timeout=timeout) as response:
            if response.headers.get_content_type() != "application/json":
                return None
            data = response.read(65537)
        if len(data) > 65536:
            return None
        status = json.loads(data)
        if robot_status(status):
            return dict(url=url, drive_mode=status["drive_mode"], movement=status["movement"])
    except (OSError, ValueError):
        pass
    return None


def discover_robots(address=None, known_url=""):
    interface = local_network(address)
    # Limit each search to at most 254 nearby addresses, also on large LANs.
    network = (interface.network if interface.network.prefixlen >= 24
               else ipaddress.ip_network(f"{interface.ip}/24", strict=False))
    hosts = [host for host in network.hosts() if host != interface.ip]
    try:
        previous = ipaddress.ip_address(urlsplit(known_url).hostname or "")
        if previous in hosts:
            hosts.remove(previous)
            hosts.insert(0, previous)
    except ValueError:
        pass
    with ThreadPoolExecutor(max_workers=24) as pool:
        found = [value for value in pool.map(probe_robot, hosts) if value]
    return dict(laptop_ip=str(interface.ip), subnet=str(network), robots=found)


def main():
    parser = argparse.ArgumentParser(description="Show current laptop and ESP32 addresses")
    parser.add_argument("--laptop-ip")
    parser.add_argument("--find", action="store_true")
    args = parser.parse_args()
    interface = local_network(args.laptop_ip)
    address = str(interface.ip)
    print("Mo AI tren laptop: https://localhost:8090")
    print(f"Dia chi laptop cho iPhone: https://{address}:8090")
    if args.find:
        path = Path(__file__).with_name("config.local.json")
        saved = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        print("Dang tim xe trong Wi-Fi hien tai...", flush=True)
        result = discover_robots(str(interface), saved.get("robot_url", ""))
        for robot in result["robots"]:
            print("ESP32: " + robot["url"] + " | " + robot["drive_mode"])
        if not result["robots"]:
            print("Chua thay xe. Kiem tra nguon xe va cung Wi-Fi; xem IP trong Serial Monitor.")


if __name__ == "__main__":
    main()
