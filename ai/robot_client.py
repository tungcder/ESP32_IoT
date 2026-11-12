"""Bounded HTTP calls. AI release can only stop its own session."""
import json
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, ProxyHandler, build_opener
from urllib.error import HTTPError


def validate_robot_url(value):
    value = value.strip().rstrip("/")
    url = urlsplit(value)
    if url.scheme != "http" or not url.hostname or url.username or url.password or url.path or url.query or url.fragment:
        raise ValueError("Địa chỉ xe cần có dạng http://IP-ESP32 hoặc http://127.0.0.1:8081.")
    _ = url.port
    return value


class RobotClient:
    def __init__(self, root, timeout=0.3):
        self.root = validate_robot_url(root)
        self.timeout = timeout
        # Vehicle traffic stays on the LAN, including on laptops with a system proxy.
        self.http = build_opener(ProxyHandler({}))

    def request(self, path, data=None, epoch=None):
        headers = {}
        if epoch is not None:
            headers["X-Mode-Epoch"] = str(epoch)
        payload = None if data is None else urlencode(data).encode()
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = Request(self.root + path, data=payload, headers=headers)
        try:
            with self.http.open(req, timeout=self.timeout) as response:
                body = response.read(65536)
                if response.headers.get_content_type() == "application/json":
                    return json.loads(body)
                return body.decode()
        except HTTPError as error:
            error.close()
            raise

    def status(self):
        return self.request("/status")

    def claim(self, epoch):
        return self.request("/ai/claim", {}, epoch)

    def command(self, session, sequence, movement, speed):
        return self.request("/ai/command", dict(session=session, seq=sequence, movement=movement, speed=speed))

    def release(self, session):
        return self.request("/ai/release", dict(session=session))

    def mode(self, mode, epoch=None):
        return self.request("/driveauto" if mode == "AUTO" else "/drivemanual", epoch=epoch)

    def emergency(self):
        return self.request("/estop", {})
