"""Webots bridge. Only the main thread accesses Webots devices."""

from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
import re
import secrets
import threading
import time
from urllib.parse import parse_qs, urlsplit

from autopilot import AutoPilot

PROJECT = Path(__file__).resolve().parents[4]
PORT = 8081
WHEEL_DIRECTIONS = {
    "STOPPED": (0, 0), "FORWARD": (1, 1), "BACKWARD": (-1, -1),
    "LEFT": (-1, 1), "RIGHT": (1, -1),
}
LED_NAMES = ("front left led", "front right led", "rear left led", "rear right led")


def scanner_position_radians(angle):
    # Match Tung's scanner: 180 degrees looks left and 0 degrees looks right.
    return math.radians(angle - 90)


def config_integer(name):
    config = (PROJECT / "include/config.h").read_text(encoding="utf-8")
    match = re.search(r"\b" + re.escape(name) + r"\s*=\s*(\d+)", config)
    if not match:
        raise ValueError(f"Cannot read {name} from include/config.h")
    return int(match.group(1))


WHEEL_SPEED = 10.0 * config_integer("MOTOR_SPEED_PERCENT") / 100


def controller_page():
    source = (PROJECT / "src/web_page.cpp").read_text(encoding="utf-8")
    match = re.search(r'R"rawliteral\((.*?)\)rawliteral"', source, re.S)
    if not match:
        raise ValueError("Cannot extract webpage from src/web_page.cpp")
    page = match.group(1)
    page = page[:page.lower().rfind("</html>") + len("</html>")]
    panel = Path(__file__).with_name("panel.html").read_text(encoding="utf-8")
    return page.replace("</body>", panel + "\n</body>")


def server_port():
    value = os.environ.get("ESP32_WEBOTS_PORT", str(PORT))
    try:
        port = int(value)
    except ValueError:
        raise ValueError("ESP32_WEBOTS_PORT must be an integer from 1024 to 65535") from None
    if not 1024 <= port <= 65535:
        raise ValueError("ESP32_WEBOTS_PORT must be an integer from 1024 to 65535")
    return port


class BridgeState:
    def __init__(self, clock=time.monotonic):
        self.lock = threading.RLock()
        self.clock = clock
        self.timeout = config_integer("COMMAND_TIMEOUT_MS") / 1000
        self.safe_distance = config_integer("SAFE_DISTANCE_CM")
        self.drive_mode = "MANUAL"
        self.movement = "STOPPED"
        self.leds = [False] * 4
        self.last_command = clock()
        self.mode_epoch = 1
        self.boot_id = secrets.randbits(32)
        self.ai_session = None
        self.ai_sequence = 0
        self.ai_requested = "STOPPED"
        self.ai_speed = 0
        self.ai_hold = True
        self.ai_safety = "idle"
        self.speed_percent = config_integer("MOTOR_SPEED_PERCENT")
        self.distance_cm = 200.0
        self.sim_time = 0.0
        self.pose = None
        self.pilot = AutoPilot(
            self.safe_distance,
            reverse_cm=config_integer("AUTO_REVERSE_CM"),
            retry_reverse_cm=config_integer("AUTO_RETRY_REVERSE_CM"),
            reverse_ms_per_cm=config_integer("AUTO_REVERSE_MS_PER_CM"),
            left_90_ms=config_integer("AUTO_LEFT_90_MS"),
            right_90_ms=config_integer("AUTO_RIGHT_90_MS"))
        self.reset_requested = False
        self.previous_mode = "MANUAL"
        self.events = deque(maxlen=40)
        self.event_id = 0
        self.log("Webots ready")

    def log(self, message):
        self.event_id += 1
        self.events.append({"id": self.event_id, "ms": int(self.clock() * 1000),
                            "mode": self.drive_mode, "message": message})

    def update_leds(self):
        if self.drive_mode != "AI":
            self.speed_percent = (config_integer("MOTOR_TURN_SPEED_PERCENT") if self.movement in ("LEFT", "RIGHT")
                                  else 0 if self.movement == "STOPPED" else config_integer("MOTOR_SPEED_PERCENT"))
        self.leds = list({
            "STOPPED": (False, False, False, False),
            "FORWARD": (True, True, False, False),
            "BACKWARD": (False, False, True, True),
            "LEFT": (True, False, True, False),
            "RIGHT": (False, True, False, True),
        }[self.movement])

    def tick(self):
        if (self.drive_mode == "MANUAL" and self.movement != "STOPPED"
                and self.clock() - self.last_command > self.timeout):
            self.movement = "STOPPED"
            self.update_leds()
            self.log("Manual command timeout")
        if self.drive_mode == "AI" and self.ai_session and self.clock() - self.last_command > self.timeout:
            self.movement = "STOPPED"
            self.ai_session = None
            self.ai_requested = "STOPPED"
            self.speed_percent = 0
            self.ai_safety = "command_timeout"
            self.update_leds()
            self.log("AI command timeout; session revoked")

    def select_mode(self, mode):
        self.movement = "STOPPED"
        self.drive_mode = mode
        self.mode_epoch += 1
        self.ai_session = None
        self.ai_requested = "STOPPED"
        self.ai_hold = True
        self.ai_safety = "idle"
        self.speed_percent = config_integer("MOTOR_SPEED_PERCENT")
        self.reset_requested = True
        self.last_command = self.clock()
        self.update_leds()

    def claim_ai(self, epoch):
        with self.lock:
            self.tick()
            if epoch != self.mode_epoch or self.ai_session:
                return None
            self.select_mode("AI")
            self.ai_session = secrets.token_hex(16)
            self.ai_sequence = 0
            self.log("AI session started")
            return {"session": self.ai_session, "mode_epoch": self.mode_epoch}

    def apply_ai(self):
        movement, speed = self.ai_requested, self.ai_speed
        self.ai_safety = "ok"
        if movement == "FORWARD":
            if not 2 <= self.distance_cm <= 400:
                movement, speed, self.ai_safety = "STOPPED", 0, "invalid_distance"
            else:
                if self.distance_cm <= config_integer("AI_STOP_DISTANCE_CM"):
                    self.ai_hold = True
                if self.distance_cm > config_integer("AI_RESUME_DISTANCE_CM"):
                    self.ai_hold = False
                if self.ai_hold:
                    movement, speed, self.ai_safety = "STOPPED", 0, "distance_hold"
        if speed == 0:
            movement = "STOPPED"
        if self.movement != movement:
            self.movement = movement
            self.log("Movement: " + movement)
        self.speed_percent = speed
        self.update_leds()

    def command_ai(self, session, sequence, movement, speed):
        limit = config_integer("MOTOR_TURN_SPEED_PERCENT") if movement in ("LEFT", "RIGHT") else config_integer("MOTOR_SPEED_PERCENT")
        if movement not in ("FORWARD", "LEFT", "RIGHT", "STOPPED") or not 0 <= speed <= limit or not 0 < sequence <= 0xffffffff:
            raise ValueError("Invalid AI movement, sequence or speed")
        with self.lock:
            self.tick()
            if self.drive_mode != "AI" or not self.ai_session or session != self.ai_session or sequence <= self.ai_sequence:
                return None
            self.ai_sequence = sequence
            self.ai_requested, self.ai_speed = movement, speed
            self.last_command = self.clock()
            self.apply_ai()
            return self.snapshot()

    def release_ai(self, session):
        with self.lock:
            if not self.ai_session or session != self.ai_session or self.drive_mode != "AI":
                return False
            self.ai_session = None
            self.ai_requested, self.movement = "STOPPED", "STOPPED"
            self.speed_percent = 0
            self.ai_safety = "idle"
            self.update_leds()
            self.log("AI session ended")
            return True

    def emergency(self):
        with self.lock:
            self.select_mode("MANUAL")
            self.log("Emergency stop; all ownership revoked")

    def command(self, path, epoch=None):
        movements = {"/forward": "FORWARD", "/backward": "BACKWARD",
                     "/left": "LEFT", "/right": "RIGHT", "/stop": "STOPPED"}
        with self.lock:
            if epoch is not None and epoch != self.mode_epoch:
                return None
            if path in movements:
                if self.drive_mode != "MANUAL":
                    return None
                movement = movements[path]
                if self.movement != movement:
                    self.movement = movement
                    self.log("Movement: " + movement)
                self.last_command = self.clock()
            elif path in ("/driveauto", "/drivemanual"):
                if self.movement != "STOPPED":
                    self.movement = "STOPPED"
                    self.log("Movement: STOPPED")
                self.select_mode("AUTO" if path == "/driveauto" else "MANUAL")
                self.log("Obstacle Auto selected" if self.drive_mode == "AUTO"
                         else "Wi-Fi Manual selected")
            else:
                return False
            self.update_leds()
            return True

    def snapshot(self):
        with self.lock:
            self.tick()
            return {"backend": "webots", "drive_mode": self.drive_mode,
                    "mode_epoch": self.mode_epoch, "boot_id": self.boot_id,
                    "ai_active": bool(self.ai_session), "ai_safety": self.ai_safety,
                    "speed_percent": self.speed_percent,
                    "uptime_ms": int(self.clock() * 1000),
                    "movement": self.movement,
                    "leds": list(self.leds), "distance_cm": round(self.distance_cm, 1),
                    "sim_time": round(self.sim_time, 3), "pose": self.pose,
                    "auto_state": self.pilot.state, "events": list(self.events),
                    "avoidance_algorithm": "center_then_left_right",
                    "scanner_angle_deg": self.pilot.angle if self.drive_mode == "AUTO" else 90,
                    "turn_duration_ms": round(self.pilot.turn_duration * 1000),
                    "timeout_ms": int(self.timeout * 1000)}

    def update_simulation(self, now, distance, pose=None):
        with self.lock:
            self.tick()
            self.sim_time = now
            self.pose = pose
            self.distance_cm = distance if math.isfinite(distance) and distance >= 0 else 0
            angle = 90
            if self.reset_requested or self.previous_mode != self.drive_mode:
                self.pilot.reset(now)
            if self.drive_mode == "AUTO":
                old_state = self.pilot.state
                old_movement = self.movement
                self.movement, angle = self.pilot.update(now, self.distance_cm)
                if old_state != self.pilot.state:
                    self.log("AUTO: " + self.pilot.state)
                if old_movement != self.movement:
                    self.log("Movement: " + self.movement)
            elif self.drive_mode == "AI" and self.ai_session:
                self.apply_ai()
            self.previous_mode = self.drive_mode
            self.reset_requested = False
            self.update_leds()
            return self.movement, angle, tuple(self.leds)


class ControllerServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, address, state):
        self.state = state
        self.page = controller_page().encode("utf-8")
        super().__init__(address, Handler)

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(1)
        return connection, address


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/":
            body, content_type, status = self.server.page, "text/html; charset=utf-8", 200
        elif path in ("/state", "/status"):
            body = json.dumps(self.server.state.snapshot()).encode("utf-8")
            content_type, status = "application/json; charset=utf-8", 200
        else:
            known = path in ("/forward", "/backward", "/left", "/right", "/stop", "/driveauto", "/drivemanual")
            try:
                epoch = int(self.headers.get("X-Mode-Epoch", ""))
            except ValueError:
                epoch = -1
            ok = self.server.state.command(path, epoch=epoch) if known else False
            body = (path if ok else "Stale mode epoch or wrong mode" if ok is None else "Not found").encode("utf-8")
            content_type, status = "text/plain; charset=utf-8", 200 if ok else 409 if ok is None else 404
            if ok and path in ("/driveauto", "/drivemanual"):
                body = json.dumps(self.server.state.snapshot()).encode()
                content_type = "application/json"
        self.reply(status, body, content_type)

    def do_POST(self):
        path = urlsplit(self.path).path
        state = self.server.state
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 <= size <= 4096:
                raise ValueError("Invalid body size")
            data = parse_qs(self.rfile.read(size).decode())
            if path == "/estop":
                state.emergency()
                result = {"stopped": True}
            elif path == "/ai/claim":
                result = state.claim_ai(int(self.headers.get("X-Mode-Epoch", "-1")))
            elif path == "/ai/command":
                result = state.command_ai(data.get("session", [""])[0], int(data.get("seq", ["0"])[0]),
                                          data.get("movement", [""])[0], int(data.get("speed", ["0"])[0]))
            elif path == "/ai/release":
                result = {"released": True} if state.release_ai(data.get("session", [""])[0]) else None
            else:
                self.reply(404, b"Not found", "text/plain")
                return
            self.reply(200 if result else 409, json.dumps(result or {"error": "Stale or expired AI session"}).encode(), "application/json")
        except (ValueError, UnicodeDecodeError):
            self.reply(400, b"Invalid arguments", "text/plain")

    def reply(self, status, body, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, TimeoutError):
            pass


def main():
    from controller import Supervisor

    try:
        port = server_port()
    except ValueError as error:
        print(error, flush=True)
        return
    robot = Supervisor()
    timestep = int(robot.getBasicTimeStep())
    left = robot.getDevice("left wheel motor")
    right = robot.getDevice("right wheel motor")
    scanner = robot.getDevice("scanner motor")
    sonar = robot.getDevice("sonar")
    leds = [robot.getDevice(name) for name in LED_NAMES]
    for motor in (left, right):
        motor.setPosition(float("inf"))
        motor.setVelocity(0)
    scanner.setPosition(0)
    sonar.enable(timestep)
    state = BridgeState()
    try:
        server = ControllerServer(("127.0.0.1", port), state)
    except OSError as error:
        print(f"Cannot start Webots controller on port {port}: {error}", flush=True)
        print("Close the other controller using this port and reset the world.", flush=True)
        return
    thread = threading.Thread(target=server.serve_forever,
                              kwargs={"poll_interval": 0.05}, daemon=True)
    thread.start()
    print(f"Webots controller ready: http://127.0.0.1:{port}", flush=True)
    try:
        while robot.step(timestep) != -1:
            node = robot.getSelf()
            position = node.getPosition()
            orientation = node.getOrientation()
            pose = {"x": position[0], "y": position[1],
                    "heading": math.atan2(orientation[3], orientation[0])}
            movement, angle, lights = state.update_simulation(
                robot.getTime(), sonar.getValue(), pose)
            l_speed, r_speed = WHEEL_DIRECTIONS[movement]
            scale = state.speed_percent / config_integer("MOTOR_SPEED_PERCENT")
            left.setVelocity(l_speed * WHEEL_SPEED * scale)
            right.setVelocity(r_speed * WHEEL_SPEED * scale)
            scanner.setPosition(scanner_position_radians(angle))
            for led, on in zip(leds, lights):
                led.set(on)
    finally:
        left.setVelocity(0)
        right.setVelocity(0)
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


if __name__ == "__main__":
    main()
