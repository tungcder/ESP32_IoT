
import pygame
import time
from datetime import datetime

pygame.init()
pygame.joystick.init()

if pygame.joystick.get_count() == 0:
    print("Khong tim thay tay cam!")
    raise SystemExit

controller = pygame.joystick.Joystick(0)
controller.init()

print("Tay cam:", controller.get_name())
print("Bat dau test. Nhan ESC de ket thuc va luu ket qua.")

results = []
last_values = None

try:
    while True:
        pygame.event.pump()

        axes = [
            round(controller.get_axis(i), 3)
            for i in range(controller.get_numaxes())
        ]

        buttons = [
            i for i in range(controller.get_numbuttons())
            if controller.get_button(i)
        ]

        hats = [
            controller.get_hat(i)
            for i in range(controller.get_numhats())
        ]

        values = (axes, buttons, hats)

        if values != last_values:
            line = (
                f"{datetime.now().strftime('%H:%M:%S')} | "
                f"Axes: {axes} | Buttons: {buttons} | Hats: {hats}"
            )
            print(line)
            results.append(line)
            last_values = values

        for event in pygame.event.get():
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    raise KeyboardInterrupt

        time.sleep(0.03)

except KeyboardInterrupt:
    filename = "gamepad_test_results.txt"

    with open(filename, "w", encoding="utf-8") as f:
        f.write("GAMEPAD TEST RESULTS\n")
        f.write(f"Controller: {controller.get_name()}\n\n")
        f.write("\n".join(results))

    print(f"\nDa luu ket qua vao: {filename}")

finally:
    pygame.quit()
