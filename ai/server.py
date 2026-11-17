"""HTTPS dashboard + WebRTC signaling; HTTP only distributes a public CA."""
import argparse
import asyncio
import hmac
import html
import json
from pathlib import Path
import ssl
import time
from urllib.parse import urlsplit

from aiohttp import web
from cryptography import x509
from cryptography.hazmat.primitives import hashes

from .https_setup import CERTS, ensure_current_network
from .service import AIService
from .webrtc import CameraReceiver

WEB = Path(__file__).with_name("web")
SERVICE = web.AppKey("service", AIService)
CAMERA = web.AppKey("camera", CameraReceiver)
INFO = web.AppKey("https_info", dict)
HEADERS = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer"}


def qr_png(value):
    import cv2
    parameters = cv2.QRCodeEncoder_Params()
    parameters.mode = cv2.QRCodeEncoder_MODE_BYTE
    parameters.correction_level = cv2.QRCodeEncoder_CORRECT_LEVEL_M
    qr = cv2.QRCodeEncoder_create(parameters).encode(value)
    qr = cv2.copyMakeBorder(qr, 4, 4, 4, 4, cv2.BORDER_CONSTANT, value=255)
    qr = cv2.resize(qr, None, fx=6, fy=6, interpolation=cv2.INTER_NEAREST)
    ok, png = cv2.imencode(".png", qr)
    if not ok:
        raise ValueError("Không tạo được QR.")
    return png.tobytes()


def json_response(value, status=200):
    return web.Response(text=json.dumps(value, ensure_ascii=False, allow_nan=False), status=status,
                        content_type="application/json", headers=HEADERS)


def authorized(request):
    token = request.headers.get("X-UI-Token", "") or request.query.get("key", "")
    return hmac.compare_digest(token, request.app[SERVICE].ui_token)


@web.middleware
async def errors(request, handler):
    try:
        if request.method == "POST":
            origin = request.headers.get("Origin")
            if origin and origin != f"{request.scheme}://{request.host}":
                return json_response(dict(error="Nguồn yêu cầu không hợp lệ."), 403)
        return await handler(request)
    except web.HTTPException:
        raise
    except (ValueError, TypeError, KeyError) as error:
        return json_response(dict(error=str(error)), 400)
    except (ConnectionResetError, BrokenPipeError, asyncio.CancelledError):
        raise
    except Exception:
        return json_response(dict(error="Chưa thực hiện được. Kiểm tra ESP32, kết nối và log AI."), 409)


async def index(request):
    text = (WEB / "index.html").read_text(encoding="utf-8")
    return web.Response(text=text.replace("__UI_TOKEN__", request.app[SERVICE].ui_token),
                        content_type="text/html", headers=HEADERS)


async def pair(request):
    service = request.app[SERVICE]
    token = request.query.get("token", "")
    if not service.paired(token):
        return web.Response(text="Mã ghép nối đã hết hạn hoặc đã dùng. Quét QR mới trên laptop.", status=403,
                            content_type="text/plain", headers=HEADERS)
    text = (WEB / "pair.html").read_text(encoding="utf-8").replace("__PAIR_TOKEN__", token)
    return web.Response(text=text, content_type="text/html", headers=HEADERS)


async def state(request):
    if not authorized(request):
        return json_response(dict(error="Mở lại bảng AI để lấy phiên giao diện mới."), 403)
    cursor = request.query.get("after_event", "")
    after_event = int(cursor) if cursor.isdigit() and len(cursor) <= 12 else None
    result = await asyncio.to_thread(request.app[SERVICE].snapshot, after_event)
    result["https"] = request.app[INFO]
    return json_response(result)


async def logs(request):
    if not authorized(request):
        return json_response(dict(error="Phiên giao diện không hợp lệ."), 403)
    service = request.app[SERVICE]

    def read():
        with service.lock:
            return service.log_path.read_bytes() if service.log_path.exists() else b""

    return web.Response(body=await asyncio.to_thread(read), content_type="application/x-ndjson", headers=HEADERS)


async def qr(request):
    if not authorized(request):
        return json_response(dict(error="Phiên giao diện không hợp lệ."), 403)
    value = request.app[INFO]["setup_url"] if request.query.get("setup") == "1" else request.app[SERVICE].pair_url()
    return web.Response(body=await asyncio.to_thread(qr_png, value), content_type="image/png", headers=HEADERS)


async def video(request):
    if not authorized(request):
        return json_response(dict(error="Phiên giao diện không hợp lệ."), 403)
    after = request.query.get("after", "")
    sequence_after = int(after) if after.isdigit() and len(after) <= 12 else None
    started = time.monotonic()

    def next_frame():
        frame = request.app[SERVICE].wait_preview(sequence_after)
        # Match the age sample to the worker's completion, so any later event
        # loop/transport delay still counts toward the browser's age limit.
        return frame, time.monotonic()

    frame, sampled_at = await asyncio.to_thread(next_frame)
    wait_ms = int((sampled_at - started) * 1000)
    if frame is None:
        return web.Response(status=204, headers=HEADERS)
    jpeg, sequence, age_ms = frame
    return web.Response(body=jpeg, content_type="image/jpeg",
                        headers={**HEADERS, "X-Frame-Id": str(sequence), "X-Frame-Age-Ms": str(age_ms),
                                 "X-Frame-Wait-Ms": str(wait_ms)})


async def camera_api(request):
    data = await request.json()
    if not isinstance(data, dict):
        raise ValueError("Dữ liệu camera cần là JSON object.")
    camera = request.app[CAMERA]
    if request.path == "/camera/offer":
        return json_response(await camera.offer(data.get("token", ""), data.get("sdp"), data.get("type")))
    owner = data.get("owner", "")
    status = camera.status(owner)
    if request.path == "/camera/stop":
        await camera.close(owner, "iPhone đã tắt camera")
        return json_response(dict(message="Đã dừng camera"))
    return json_response(status)


async def action(request):
    if not authorized(request):
        return json_response(dict(error="Phiên giao diện không hợp lệ."), 403)
    data = await request.json()
    if not isinstance(data, dict):
        raise ValueError("Dữ liệu cần là JSON object.")
    service, camera = request.app[SERVICE], request.app[CAMERA]
    if request.path == "/api/discover":
        return json_response(await asyncio.to_thread(service.find_robots))
    if request.path == "/api/config":
        if data.get("public_url"):
            parsed = urlsplit(str(data["public_url"]))
            if parsed.hostname not in request.app[INFO]["names"] or (parsed.port or 443) != service.port:
                raise ValueError("Địa chỉ QR phải khớp chứng chỉ và cổng server. Chạy setup.ps1 -LaptopIP IP-moi khi đổi mạng.")
        await asyncio.to_thread(service.save_config, data)
    elif request.path == "/api/start":
        await asyncio.to_thread(service.start, data.get("mode", "AI"))
    elif request.path == "/api/stop":
        await asyncio.to_thread(service.stop)
    elif request.path == "/api/estop":
        await asyncio.to_thread(service.emergency)
    elif request.path == "/api/mode":
        await asyncio.to_thread(service.change_mode, data.get("mode"))
    elif request.path == "/api/pair/renew":
        service.rotate_pair()
    elif request.path == "/api/camera/disconnect":
        await camera.close()
    return json_response(dict(message="Đã thực hiện", robot_url=service.config["robot_url"]))


def create_app(service, info):
    app = web.Application(middlewares=[errors], client_max_size=96 * 1024)
    app[SERVICE], app[INFO], app[CAMERA] = service, info, CameraReceiver(service)
    app.add_routes([web.get("/", index), web.get("/pair", pair), web.get("/api/state", state),
                    web.get("/api/logs", logs), web.get("/qr.png", qr), web.get("/frame.jpg", video)])
    for path in ("/camera/offer", "/camera/status", "/camera/stop"):
        app.router.add_post(path, camera_api)
    for path in ("/api/config", "/api/start", "/api/stop", "/api/estop", "/api/mode",
                 "/api/pair/renew", "/api/camera/disconnect", "/api/discover"):
        app.router.add_post(path, action)

    async def shutdown(app):
        await app[CAMERA].shutdown()
        await asyncio.to_thread(service.close)

    app.on_shutdown.append(shutdown)
    return app


def certificate_info(port, setup_port):
    ca = x509.load_pem_x509_certificate((CERTS / "ca.pem").read_bytes())
    cert = x509.load_pem_x509_certificate((CERTS / "server.pem").read_bytes())
    saved = json.loads((CERTS / "info.json").read_text(encoding="utf-8"))
    names = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    return dict(fingerprint=ca.fingerprint(hashes.SHA256()).hex().upper(),
                setup_url=f"http://{saved['ip']}:{setup_port}", public_url=f"https://{saved['ip']}:{port}",
                names=[str(name.value) for name in names], expires=cert.not_valid_after_utc.isoformat())


def bootstrap_app(info):
    app = web.Application()

    async def setup_page(request):
        text = (WEB / "setup.html").read_text(encoding="utf-8")
        text = text.replace("__FINGERPRINT__", html.escape(info["fingerprint"]))
        text = text.replace("__DASHBOARD_URL__", html.escape(info["public_url"]))
        return web.Response(text=text, content_type="text/html", headers=HEADERS)

    async def root_certificate(request):
        return web.Response(body=(CERTS / "iphone-root.cer").read_bytes(),
                            content_type="application/x-x509-ca-cert",
                            headers={**HEADERS, "Content-Disposition": 'attachment; filename="ESP32-Camera-Root.cer"'})

    app.add_routes([web.get("/", setup_page), web.get("/iphone-root.cer", root_certificate)])
    return app


async def serve(args):
    try:
        ensure_current_network(args.port, args.laptop_ip, args.config or Path(__file__).with_name("config.local.json"))
        info = certificate_info(args.port, args.setup_port)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(CERTS / "server.pem", CERTS / "server-key.pem")
    except (OSError, ValueError) as error:
        raise SystemExit(f"Khong chuan bi duoc mang/HTTPS: {error}. Xem ai/README.md.") from None
    service = AIService(args.config, args.port)
    public = service.config.get("public_url") or info["public_url"]
    parsed = urlsplit(public)
    if parsed.hostname not in info["names"] or (parsed.port or 443) != args.port:
        raise SystemExit("IP/port trong config khong khop HTTPS. Chay lai setup.ps1 -LaptopIP IP-LAN -Port cong.")
    service.config["public_url"] = public
    runner = web.AppRunner(create_app(service, info), access_log=None, shutdown_timeout=3)
    setup_runner = web.AppRunner(bootstrap_app(info), access_log=None, shutdown_timeout=1)
    try:
        await runner.setup()
        await setup_runner.setup()
        await web.TCPSite(runner, args.host, args.port, ssl_context=context).start()
        await web.TCPSite(setup_runner, args.host, args.setup_port).start()
        service.launch()
        print(f"Mo AI tren laptop (khong doi theo Wi-Fi): https://localhost:{args.port}", flush=True)
        print("AI dashboard: " + public, flush=True)
        print("IP xe thay doi: bam Tim xe trong Wi-Fi tren bang AI, hoac chay ai/find.ps1.", flush=True)
        print("Cai chung chi iPhone (mot lan): " + info["setup_url"], flush=True)
        print("CA SHA256: " + info["fingerprint"], flush=True)
        print("Quet QR > Bat camera truoc > Cho phep. Xe chi chay khi bam Bat dau bam muc tieu.", flush=True)
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()
        await setup_runner.cleanup()


def main():
    parser = argparse.ArgumentParser(description="YOLOv8n iPhone WebRTC dashboard with HTTPS")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8090)
    parser.add_argument("--setup-port", type=int)
    parser.add_argument("--config")
    parser.add_argument("--laptop-ip", help="Override automatic Wi-Fi address detection")
    args = parser.parse_args()
    args.setup_port = args.setup_port or args.port + 1
    if not 1024 <= args.port <= 65534 or not 1024 <= args.setup_port <= 65535 or args.port == args.setup_port:
        parser.error("Can hai cong rieng trong 1024..65535.")
    try:
        asyncio.run(serve(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
