import pygame
import requests
import time
import sys

# ==========================================
# CONFIGURATION
# ==========================================

# IP hiện tại của ESP32 (xem Serial Monitor). Có thể truyền khi chạy:
#   python gamepad_controller.py 192.168.1.50
ESP32_IP = sys.argv[1] if len(sys.argv) > 1 else "192.168.1.36"
BASE_URL = f"http://{ESP32_IP}"

# Flydigi Dune Fox - Left analog stick
AXIS_HORIZONTAL = 0     
AXIS_VERTICAL = 1

DEADZONE = 0.12
MAX_SPEED = 50

SEND_INTERVAL = 0.05  # Gui lenh moi 50ms
REQUEST_TIMEOUT = 0.4

# Button mapping
BUTTON_A = 0
BUTTON_B = 1
BUTTON_Y = 3

# ==========================================
# INITIALIZATION
# ==========================================

pygame.init()
pygame.joystick.init()

if pygame.joystick.get_count() == 0:
    print("Khong tim thay tay cam!")
    pygame.quit()
    sys.exit()

controller = pygame.joystick.Joystick(0)

print("===================================")
print("GAMEPAD CONTROLLER")
print("Controller:", controller.get_name())
print("===================================")
print("A   : Manual mode")
print("B   : Stop robot")
print("Y   : Auto mode")
print("ESC : Exit")
print("-----------------------------------")

session = requests.Session()

manual_enabled = False
mode_epoch = None
last_send_time = 0
last_print_command = None

# Button edge detection
previous_a = False
previous_b = False
previous_y = False


# ==========================================
# HELPER FUNCTIONS
# ==========================================

def apply_deadzone(value):
    if abs(value) < DEADZONE:
        return 0.0

    # Chuan hoa lai gia tri sau deadzone
    if value > 0:
        return (value - DEADZONE) / (1.0 - DEADZONE)

    return (value + DEADZONE) / (1.0 - DEADZONE)


def send_request(endpoint, params=None):
    global manual_enabled, mode_epoch

    try:
        # Refresh ownership only on an explicit mode selection, never while driving.
        if endpoint in ("drivemanual", "driveauto"):
            status = session.get(f"{BASE_URL}/status", timeout=REQUEST_TIMEOUT)
            status.raise_for_status()
            mode_epoch = status.json()["mode_epoch"]

        if mode_epoch is None:
            return False

        response = session.get(
            f"{BASE_URL}/{endpoint}",
            params=params,
            headers={"X-Mode-Epoch": str(mode_epoch)},
            timeout=REQUEST_TIMEOUT
        )

        if response.status_code == 409:
            manual_enabled = False
            mode_epoch = None
            print("Quyen dieu khien da thay doi (doi mode hoac chon nut tren web). Nhan A de lay lai tay cam.")
            return False

        response.raise_for_status()
        if endpoint in ("drivemanual", "driveauto"):
            mode_epoch = response.json()["mode_epoch"]
        return True

    except (requests.RequestException, ValueError, KeyError) as error:
        print("Loi ket noi ESP32:", error)
        return False


def send_motor_command(left, right):
    global last_print_command

    # LUON gui lenh dinh ky, ke ca khi gia tri khong doi
    success = send_request(
        "gamepad",
        {
            "left": left,
            "right": right
        }
    )

    if success:
        command = (left, right)

        # Chi in khi lenh thay doi de tranh spam Serial
        if command != last_print_command:
            print(f"Left: {left:3d} | Right: {right:3d}")
            last_print_command = command


def stop_robot():
    send_motor_command(0, 0)


def claim_gamepad_input():
    # Bao ESP32 dung nguon lai la tay cam: web hien "Tay cam", nut di chuyen tren web bi khoa.
    return send_request("manualinput", {"source": "gamepad"})


def release_gamepad_input():
    # Tra nguon lai ve nut tren web khi thoat chuong trinh.
    return send_request("manualinput", {"source": "web"})


def select_manual():
    global manual_enabled

    print("Switching to MANUAL mode...")

    if send_request("drivemanual") and claim_gamepad_input():
        manual_enabled = True
        stop_robot()
        print("MANUAL mode enabled (gamepad input)")


def select_auto():
    global manual_enabled

    print("Switching to AUTO mode...")

    # Dung dong co truoc khi chuyen mode
    stop_robot()

    if send_request("driveauto"):
        manual_enabled = False
        print("AUTO mode enabled")


# ==========================================
# MAIN LOOP
# ==========================================

try:
    print("\nConnecting to ESP32...")

    if send_request("drivemanual") and claim_gamepad_input():
        manual_enabled = True
        print("Connected. MANUAL mode enabled (gamepad input).")
    else:
        print("Cannot connect to ESP32.")
        print("Check ESP32 IP and Wi-Fi connection.")
        raise SystemExit

    print("\nReady! Use LEFT STICK to control the robot.\n")

    while True:

        pygame.event.pump()

        # ESC to exit
        for event in pygame.event.get():
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    raise KeyboardInterrupt

        # Read buttons
        a_now = bool(controller.get_button(BUTTON_A))
        b_now = bool(controller.get_button(BUTTON_B))
        y_now = bool(controller.get_button(BUTTON_Y))

        # A: Manual (chi xu ly khi vua nhan)
        if a_now and not previous_a:
            select_manual()

        # Y: Auto
        if y_now and not previous_y:
            select_auto()

        # B: Stop robot, nhung van giu Manual
        if b_now and not previous_b:
            print("STOP!")
            if manual_enabled:
                stop_robot()

        previous_a = a_now
        previous_b = b_now
        previous_y = y_now

        # ==================================
        # ANALOG CONTROL
        # ==================================

        if manual_enabled:

            # Left stick
            horizontal = controller.get_axis(AXIS_HORIZONTAL)
            vertical = controller.get_axis(AXIS_VERTICAL)

            # Up = positive throttle
            throttle = -vertical

            # Right = positive steering
            steering = -horizontal

            throttle = apply_deadzone(throttle)
            steering = apply_deadzone(steering)

            # Differential drive
            left = throttle + steering
            right = throttle - steering

            # Normalize
            scale = max(1.0, abs(left), abs(right))

            left /= scale
            right /= scale

            # Limit motor speed
            left = int(left * MAX_SPEED)
            right = int(right * MAX_SPEED)

            # B is held: force stop
            if b_now:
                left = 0
                right = 0

            # Send command periodically
            now = time.monotonic()

            if now - last_send_time >= SEND_INTERVAL:
                send_motor_command(left, right)
                last_send_time = now

        time.sleep(0.005)


except KeyboardInterrupt:
    print("\nExiting controller...")


finally:
    print("Sending STOP command...")

    if manual_enabled:
        stop_robot()
        release_gamepad_input()

    session.close()
    pygame.quit()

    print("Controller closed.")
