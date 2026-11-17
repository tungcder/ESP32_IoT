#pragma once
#include <Arduino.h>

// Nguồn lái trong chế độ Manual: nút trên web hoặc tay cầm (laptop gửi /gamepad).
enum class ManualInput : uint8_t { Web, Gamepad };

void setManualInput(ManualInput input);
ManualInput getManualInput();          // tự về Web khi mode_epoch thay đổi
const char* manualInputName();         // "WEB" hoặc "GAMEPAD"
void noteGamepadCommand(int leftPercent, int rightPercent);
long gamepadAgeMs();                   // -1 nếu chưa có lệnh tay cầm trong phiên Manual hiện tại
int gamepadLeftPercent();
int gamepadRightPercent();