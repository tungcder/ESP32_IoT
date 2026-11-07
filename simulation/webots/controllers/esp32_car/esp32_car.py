"""Webots bridge. Only the main thread accesses Webots devices."""

from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
import re
import threading
import time
from urllib.parse import urlsplit

from autopilot import AutoPilot

PROJECT = Path(__file__).resolve().parents[4]
PORT = 8081
WHEEL_DIRECTIONS = {
    "STOPPED": (0, 0), "FORWARD": (1, 1), "BACKWARD": (-1, -1),
    "LEFT": (-1, 1), "RIGHT": (1, -1),
}
LED_NAMES = ("front left led", "front right led", "rear left led", "rear right led")


def scanner_position_radians(angle):
    # On the real robot 0 degrees looks left and 180 degrees looks right.
    return math.radians(90 - angle)


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

    def command(self, path):
        movements = {"/forward": "FORWARD", "/backward": "BACKWARD",
                     "/left": "LEFT", "/right": "RIGHT", "/stop": "STOPPED"}
        with self.lock:
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
                self.drive_mode = "AUTO" if path == "/driveauto" else "MANUAL"
                self.movement = "STOPPED"
                self.reset_requested = True
                self.last_command = self.clock()
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
            ok = self.server.state.command(path)
            body = (path if ok else "AUTO mode active" if ok is None else "Not found").encode("utf-8")
            content_type, status = "text/plain; charset=utf-8", 200 if ok else 409 if ok is None else 404
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
            left.setVelocity(l_speed * WHEEL_SPEED)
            right.setVelocity(r_speed * WHEEL_SPEED)
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
