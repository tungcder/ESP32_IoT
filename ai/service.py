"""WebRTC reception, inference and motor control run independently.

Only control_tick/start/stop/mode hold operation_lock while talking to a robot.
No watchdog is refreshed from camera/inference threads.
"""
from collections import deque
from dataclasses import asdict
from datetime import datetime
import json
from pathlib import Path
import secrets
import socket
import threading
import time
from urllib.parse import urlsplit
from urllib.error import HTTPError, URLError

from .follower import Follower
from .robot_client import RobotClient, validate_robot_url
from yolov8n.target_alignment import AlignmentConfig

ROOT = Path(__file__).resolve().parents[1]
FRAME_TIMEOUT = 0.5


def lan_address():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("192.0.2.1", 80))
            return probe.getsockname()[0]
    except OSError:
        return "127.0.0.1"


class AIService:
    def __init__(self, config_path=None, port=8090):
        self.lock = threading.RLock()
        self.operation_lock = threading.RLock()
        self.shutdown_event = threading.Event()
        self.control_wake = threading.Event()
        self.config_path = Path(config_path or ROOT / "ai/config.local.json")
        self.config = dict(robot_url="http://127.0.0.1:8081", public_url="")
        if self.config_path.exists():
            saved = json.loads(self.config_path.read_text(encoding="utf-8"))
            self.config.update({key: saved[key] for key in self.config if key in saved})
        self.validate_config(self.config)
        self.port = port
        self.events = deque(maxlen=500)
        self.event_id = 0
        self.robot_state = None
        self.robot_seen = 0
        self.robot_error = ""
        self.session = None
        self.sequence = 0
        self.follower = None
        self.decision = dict(state="IDLE", movement="STOPPED", reason="Chưa bắt đầu AI")
        self.model_ready = False
        self.alignment_config = None
        self.model_error = ""
        self.camera_error = "Chờ iPhone quét QR và bật camera"
        self.camera_generation = 0
        self.camera_connected = False
        self.frame = None
        self.frame_id = 0
        self.frame_at = 0
        self.result = None
        self.result_at = 0
        self.result_id = 0
        self.jpeg = None
        self.jpeg_at = 0
        self.raw_jpeg = None
        self.raw_jpeg_at = 0
        self.raw_jpeg_id = 0
        self.jpeg_id = 0
        self.pair_token = secrets.token_urlsafe(24)
        self.pair_expires = time.monotonic() + 600
        self.ui_token = secrets.token_urlsafe(32)
        self.log_path = ROOT / "ai/logs" / (datetime.now().strftime("%Y%m%d-%H%M%S") + ".jsonl")
        self.log("Ứng dụng AI sẵn sàng; xe chưa được kích hoạt")
        self.threads = []

    @staticmethod
    def validate_config(config):
        validate_robot_url(config["robot_url"])
        if config.get("public_url"):
            parsed = urlsplit(config["public_url"])
            if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.path not in ("", "/") or parsed.query or parsed.fragment:
                raise ValueError("Địa chỉ QR cần có dạng https://IP-laptop:8090.")
            _ = parsed.port

    def log(self, message, kind="info"):
        with self.lock:
            self.event_id += 1
            event = dict(id=self.event_id, time=datetime.now().astimezone().isoformat(timespec="seconds"),
                         mode="AI", kind=kind, message=message)
            self.events.append(event)
            try:
                self.log_path.parent.mkdir(parents=True, exist_ok=True)
                with self.log_path.open("a", encoding="utf-8") as output:
                    output.write(json.dumps(event, ensure_ascii=False) + "\n")
            except OSError:
                pass  # A full disk cannot prevent STOP or release.

    def launch(self):
        for target in (self.inference_loop, self.control_loop):
            worker = threading.Thread(target=target, daemon=True)
            worker.start()
            self.threads.append(worker)

    def pair_url(self):
        public = self.config.get("public_url") or f"https://{lan_address()}:{self.port}"
        return public.rstrip("/") + "/pair?token=" + self.pair_token

    def paired(self, token):
        return bool(token) and secrets.compare_digest(str(token), self.pair_token) and time.monotonic() < self.pair_expires

    def rotate_pair(self):
        with self.lock:
            self.pair_token = secrets.token_urlsafe(24)
            self.pair_expires = time.monotonic() + 600

    def save_config(self, values):
        with self.operation_lock:
            with self.lock:
                if self.session:
                    raise ValueError("Dừng AI trước khi thay đổi cấu hình.")
                updated = dict(self.config)
                for key in ("robot_url", "public_url"):
                    if key in values:
                        updated[key] = str(values[key]).strip()
                self.validate_config(updated)
                self.robot_seen = 0
                self.robot_state = None
                temp = self.config_path.with_suffix(".tmp")
                temp.write_text(json.dumps(updated, ensure_ascii=False, indent=2), encoding="utf-8")
                temp.replace(self.config_path)
                self.config = updated
            self.log("Đã lưu cấu hình AI")

    def begin_camera(self):
        with self.operation_lock:
            with self.lock:
                if self.session:
                    raise ValueError("Dừng AI trước khi thay camera.")
                self.camera_generation += 1
                self.frame = self.result = self.jpeg = self.raw_jpeg = None
                self.frame_at = self.result_at = 0
                self.camera_connected = True
                self.camera_error = "Đang chờ hình từ iPhone…"
                generation = self.camera_generation
            self.log("iPhone đã ghép nối; đang thiết lập WebRTC")
            return generation

    def receive_frame(self, frame, stamp, generation, preview=None):
        with self.lock:
            if generation != self.camera_generation or not self.camera_connected:
                return False
            if time.monotonic() - stamp > FRAME_TIMEOUT:
                return False
            first = self.frame is None
            self.frame_id += 1
            self.frame, self.frame_at = frame, stamp
            self.camera_error = ""
            if preview:
                self.raw_jpeg = preview
                self.raw_jpeg_at, self.raw_jpeg_id = stamp, self.frame_id
        if first:
            self.log("Đã nhận hình WebRTC từ camera iPhone")
        return True

    def end_camera(self, generation, reason="Camera iPhone đã ngắt"):
        with self.operation_lock:
            with self.lock:
                if generation != self.camera_generation:
                    return
                self.camera_connected = False
                self.camera_error = reason
                self.frame = self.result = self.jpeg = self.raw_jpeg = None
                self.frame_at = self.result_at = 0
                active = bool(self.session)
            if active:
                self.stop(reason + "; kết thúc phiên AI", "FAULT")
            self.log(reason, "warning")

    def inference_loop(self):
        try:
            import cv2
            from yolov8n.robot_ai import TargetAI
            # Runtime guide/control policy overrides legacy alignment metadata.
            ai = TargetAI(weights=ROOT / "yolov8n/best.onnx", alignment=AlignmentConfig())
            with self.lock:
                self.alignment_config = asdict(ai.aligner.config)
                self.model_ready = True
            self.log("YOLOv8n ONNX sẵn sàng (" + ", ".join(ai.providers) + ")")
        except Exception as error:
            with self.lock:
                self.model_error = f"Không nạp được model: {type(error).__name__}. Kiểm tra model và requirements.txt."
            self.log(self.model_error, "error")
            return
        previous = None
        while not self.shutdown_event.wait(0.01):
            with self.lock:
                frame, stamp, sequence, generation = self.frame, self.frame_at, self.frame_id, self.camera_generation
            key = (generation, sequence)
            if frame is None or key == previous or time.monotonic() - stamp > FRAME_TIMEOUT:
                continue
            previous = key
            try:
                if getattr(ai, "camera_generation", None) != generation:
                    ai.stop()
                    ai.camera_generation = generation
                result = ai.process_frame(frame, captured_at=stamp, draw=True)
                success, encoded = cv2.imencode(".jpg", result.annotated_frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
                with self.lock:
                    if generation == self.camera_generation and self.camera_connected:
                        self.result = result.alignment.as_dict()
                        self.result["inference_ms"] = round(result.inference_ms, 1)
                        self.result_at, self.result_id = stamp, sequence
                        if success:
                            self.jpeg, self.jpeg_at = encoded.tobytes(), stamp
                            self.jpeg_id = sequence
            except Exception:
                with self.lock:
                    self.result = None
                    self.model_error = "Lỗi xử lý ảnh; dừng và khởi động lại ứng dụng để kiểm tra."
                    self.model_ready = False
                self.log(self.model_error, "error")
                return

    def start(self):
        with self.operation_lock:
            with self.lock:
                if self.session:
                    raise ValueError("Phiên AI đang hoạt động.")
                if (not self.model_ready or self.result is None or self.camera_error
                        or time.monotonic() - self.result_at > FRAME_TIMEOUT
                        or time.monotonic() - self.frame_at > FRAME_TIMEOUT):
                    raise ValueError("Cần model sẵn sàng và hình iPhone mới trước khi bắt đầu.")
                client = RobotClient(self.config["robot_url"])
                follower = Follower(alignment=self.alignment_config)
            status = client.status()
            if "mode_epoch" not in status:
                raise ValueError("Firmware chưa hỗ trợ mode AI. Nạp firmware mới trước.")
            claim = client.claim(status["mode_epoch"])
            try:
                # Establish the first acknowledged command before returning to the UI.
                # The ESP32 watchdog starts at claim, not at the first control tick.
                stopped = client.command(claim["session"], 1, "STOPPED", 0)
                if not isinstance(stopped, dict) or stopped.get("movement") != "STOPPED":
                    raise ValueError("ESP32 chưa xác nhận lệnh dừng khởi tạo AI.")
            except Exception:
                try:
                    client.release(claim["session"])
                except Exception:
                    pass  # The unchanged firmware watchdog revokes unacknowledged claims.
                raise
            with self.lock:
                self.session = claim["session"]
                self.sequence = 1
                self.follower = follower
                self.robot_state, self.robot_seen = stopped, time.monotonic()
                self.robot_error = ""
                self.decision = dict(state="WAIT_TARGET", movement="STOPPED", reason="Chờ khóa mục tiêu")
            self.control_wake.set()
            self.log("Bắt đầu phiên AI; chờ xác nhận mục tiêu")

    def stop(self, reason="Người dùng dừng AI", final_state="IDLE"):
        with self.operation_lock:
            with self.lock:
                session, self.session = self.session, None
                client = RobotClient(self.config["robot_url"])
                self.decision = dict(self.decision, state=final_state, movement="STOPPED", speed=0, reason=reason)
            if session:
                try:
                    client.release(session)
                    with self.lock:
                        if self.robot_state:
                            self.robot_state = dict(self.robot_state, movement="STOPPED", ai_active=False)
                            self.robot_seen = time.monotonic()
                    self.log("ESP32 đã xác nhận kết thúc quyền điều khiển AI")
                except Exception:
                    with self.lock:
                        self.robot_seen = 0
                    self.log("Không còn xác nhận quyền AI; nếu phiên còn hiệu lực, watchdog AI sẽ dừng sau tối đa 500 ms", "warning")
            self.log(reason, "error" if final_state == "FAULT" else "info")

    def change_mode(self, mode):
        if mode not in ("AUTO", "MANUAL"):
            raise ValueError("Mode không hợp lệ.")
        with self.operation_lock:
            if self.session:
                self.stop("Dừng AI để yêu cầu chuyển sang " + mode)
            client = RobotClient(self.config["robot_url"], timeout=0.8)
            try:
                state = client.status()
                if not isinstance(state, dict) or state.get("drive_mode") not in ("AUTO", "MANUAL", "AI"):
                    raise ValueError("Địa chỉ cấu hình không trả về trạng thái ESP32 hợp lệ.")
                # Old Auto/Manual firmware has no epoch and returns plain text.
                # New firmware must still receive its epoch; never retry without it.
                confirmed = client.mode(mode, state.get("mode_epoch"))
                if "mode_epoch" not in state:
                    if confirmed != "DRIVE " + mode:
                        raise ValueError("Firmware cũ chưa xác nhận lệnh chuyển mode.")
                    confirmed = client.status()
                if not isinstance(confirmed, dict) or confirmed.get("drive_mode") != mode:
                    raise ValueError("ESP32 chưa xác nhận mode " + mode + "; tải lại trạng thái xe.")
            except HTTPError as error:
                raise ValueError(f"ESP32 từ chối chuyển mode (HTTP {error.code}); tải lại trạng thái và thử lại.") from error
            except (URLError, TimeoutError, OSError) as error:
                message = f"Không kết nối được ESP32 tại {client.root}. Kiểm tra IP trong Serial Monitor, nguồn xe và Wi-Fi; cập nhật Địa chỉ ESP32 rồi Lưu cấu hình."
                with self.lock:
                    self.robot_seen = 0
                    self.robot_error = message
                self.log(message, "warning")
                raise ValueError(message) from error
            with self.lock:
                self.robot_state, self.robot_seen = confirmed, time.monotonic()
                self.robot_error = ""
            self.log("ESP32 đã chuyển sang " + mode)

    def emergency(self):
        with self.operation_lock:
            with self.lock:
                self.session = None
                self.decision = dict(state="IDLE", movement="STOPPED", reason="Dừng khẩn cấp")
            RobotClient(self.config["robot_url"]).emergency()
            self.log("ESP32 đã xác nhận dừng khẩn cấp; chuyển về Manual", "warning")

    def control_tick(self):
        with self.operation_lock:
            with self.lock:
                session = self.session
                if not session:
                    return
                now = time.monotonic()
                observation, stamp, frame_id = self.result, self.result_at, self.result_id
                if observation is None or now - stamp > FRAME_TIMEOUT or now - self.frame_at > FRAME_TIMEOUT or self.camera_error:
                    self.stop("Mất hình mới hoặc AI quá chậm; kết thúc phiên", "FAULT")
                    return
                distance = (self.robot_state or {}).get("distance_cm", 0)
                decision = self.follower.step(observation, frame_id, now, distance)
                old = self.decision
                self.decision = asdict(decision)
                client = RobotClient(self.config["robot_url"])
                self.sequence += 1
                sequence = self.sequence
            state = client.command(session, sequence, decision.movement, decision.speed)
            with self.lock:
                self.robot_state, self.robot_seen = state, time.monotonic()
                self.follower.feedback(state["movement"], now=time.monotonic())
            if (old.get("state"), old.get("movement"), old.get("reason")) != (decision.state, decision.movement, decision.reason):
                self.log(f"{decision.state}: {decision.reason}; yêu cầu {decision.movement}")
            if state["movement"] != (old.get("actual_movement")):
                self.log("ESP32 xác nhận: " + state["movement"] + " (" + state.get("ai_safety", "ok") + ")")
            with self.lock:
                self.decision["actual_movement"] = state["movement"]

    def control_loop(self):
        last_poll = 0
        while not self.shutdown_event.is_set():
            cycle_started = time.monotonic()
            self.control_wake.clear()
            try:
                # Decide after taking ownership: a claim may have completed while
                # this worker waited. Never put an idle GET ahead of a new session.
                with self.operation_lock:
                    with self.lock:
                        active = bool(self.session)
                    if active:
                        self.control_tick()
                    elif time.monotonic() - last_poll > 0.75:
                        state = RobotClient(self.config["robot_url"]).status()
                        with self.lock:
                            self.robot_state, self.robot_seen = state, time.monotonic()
                            self.robot_error = ""
                        last_poll = time.monotonic()
            except Exception as error:
                with self.lock:
                    active = bool(self.session)
                    self.robot_seen = 0
                    self.robot_error = f"Không đọc được trạng thái ESP32 tại {self.config['robot_url']}. Kiểm tra nguồn xe, IP trong Serial Monitor và Wi-Fi."
                if active:
                    detail = (f"HTTP {error.code}: phiên đã hết hạn hoặc lệnh bị từ chối"
                              if isinstance(error, HTTPError) else type(error).__name__)
                    self.log("Lỗi giao tiếp ESP32: " + detail, "error")
                    self.stop("ESP32: " + detail + "; kết thúc phiên AI", "FAULT")
                last_poll = time.monotonic()
            # Network time is part of the 100 ms period, not an extra delay.
            self.control_wake.wait(max(0, 0.1 - (time.monotonic() - cycle_started)))

    def snapshot(self):
        with self.lock:
            now = time.monotonic()
            return dict(active=bool(self.session), model_ready=self.model_ready, model_error=self.model_error,
                        camera_ready=self.frame is not None and now - self.frame_at <= FRAME_TIMEOUT and not self.camera_error,
                        inference_ready=self.result is not None and now - self.result_at <= FRAME_TIMEOUT,
                        camera_connected=self.camera_connected, camera_error=self.camera_error, frame_age_ms=round((now - self.frame_at)*1000) if self.frame_at else None,
                        robot_online=now - self.robot_seen < 1.5, robot=self.robot_state, robot_error=self.robot_error,
                        decision=dict(self.decision), detection=self.result,
                        config=dict(self.config), pair_url=self.pair_url(),
                        pair_remaining=max(0, round(self.pair_expires - now)), events=list(self.events))

    def preview(self):
        with self.lock:
            now = time.monotonic()
            if now - self.frame_at > FRAME_TIMEOUT or self.camera_error:
                return None
            if self.model_ready:
                # Do not alternate annotated frames with newer raw frames:
                # raw IDs can overtake inference IDs and make boxes blink.
                if self.jpeg and now - self.jpeg_at <= FRAME_TIMEOUT:
                    return self.jpeg, self.jpeg_id, round((now - self.jpeg_at) * 1000)
                return None
            if self.raw_jpeg and now - self.raw_jpeg_at <= 0.2:
                return self.raw_jpeg, self.raw_jpeg_id, round((now - self.raw_jpeg_at) * 1000)
            return None

    def close(self):
        self.shutdown_event.set()
        self.control_wake.set()
        self.stop("Đóng ứng dụng AI")
        for worker in self.threads:
            worker.join(timeout=1)
