"""Bounded HTTP calls. AI release can only stop its own session."""
import json
import errno
from http.client import HTTPException
import time
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, ProxyHandler, build_opener
from urllib.error import HTTPError, URLError


def describe_robot_error(error):
    """Keep the underlying socket failure and request timing visible to operators."""
    if isinstance(error, HTTPError):
        detail = ("phiên đã hết hạn hoặc lệnh bị từ chối" if error.code == 409
                  else str(error.reason))
        message = f"HTTP {error.code}: {detail}"
    else:
        reason = error.reason if isinstance(error, URLError) else error
        code = getattr(reason, "winerror", None) or getattr(reason, "errno", None)
        if isinstance(reason, TimeoutError) or str(reason).lower() == "timed out":
            message = "Hết thời gian chờ kết nối/phản hồi ESP32"
        elif code in (errno.ECONNREFUSED, 10061):
            message = "ESP32 từ chối kết nối; kiểm tra IP và web server trên xe"
        elif code in (errno.ECONNRESET, errno.ECONNABORTED, 10053, 10054):
            message = "Kết nối ESP32 bị ngắt; kiểm tra Wi-Fi và nguồn xe"
        else:
            message = "Lỗi giao tiếp ESP32"
        message += f" ({type(error).__name__}: {reason})"
    if hasattr(error, "robot_request"):
        message += (f"; {error.robot_request}; sau {error.robot_elapsed_ms} ms"
                    f" (timeout socket {error.robot_timeout_ms} ms)")
    return message


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
        started = time.monotonic()
        try:
            with self.http.open(req, timeout=self.timeout) as response:
                body = response.read(65536)
                if response.headers.get_content_type() == "application/json":
                    return json.loads(body)
                return body.decode()
        except (URLError, OSError, HTTPException) as error:
            error.robot_request = f"{req.get_method()} {path}"
            error.robot_elapsed_ms = round((time.monotonic() - started) * 1000)
            error.robot_timeout_ms = round(self.timeout * 1000)
            if isinstance(error, HTTPError):
                error.close()
            raise

    def status(self):
        return self.request("/status")

    def claim(self, epoch):
        return self.request("/ai/claim", {}, epoch)

    def claim_hybrid(self, epoch):
        return self.request("/hybrid/claim", {}, epoch)

    def hybrid_command(self, session, sequence, behavior, movement, speed):
        return self.request("/hybrid/command", dict(session=session, seq=sequence,
                            behavior=behavior, movement=movement, speed=speed))

    def command(self, session, sequence, movement, speed):
        return self.request("/ai/command", dict(session=session, seq=sequence, movement=movement, speed=speed))

    def release(self, session):
        return self.request("/ai/release", dict(session=session))

    def mode(self, mode, epoch=None):
        return self.request("/driveauto" if mode == "AUTO" else "/drivemanual", epoch=epoch)

    def emergency(self):
        return self.request("/estop", {})
