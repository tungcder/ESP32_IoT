#include "manual_input.h"
#include "drive_mode.h"

namespace {
  ManualInput selected = ManualInput::Web;
  uint32_t selectedEpoch = 0;

  bool hasCommand = false;
  uint32_t commandEpoch = 0;
  unsigned long lastCommandMs = 0;
  int lastLeft = 0;
  int lastRight = 0;

  bool commandIsCurrent() {
    return hasCommand && commandEpoch == getModeEpoch();
  }
}

void setManualInput(ManualInput input) {
  selected = input;
  selectedEpoch = getModeEpoch();
  hasCommand = false;
  lastLeft = 0;
  lastRight = 0;
}

ManualInput getManualInput() {
  // Đổi mode (Auto/AI/Hybrid/E-stop/chọn lại Manual) làm mode_epoch tăng,
  // nên lựa chọn cũ tự hết hiệu lực và nút trên web là mặc định an toàn.
  if (getDriveMode() == DriveMode::Manual && selectedEpoch == getModeEpoch()) return selected;
  return ManualInput::Web;
}

const char* manualInputName() {
  return getManualInput() == ManualInput::Gamepad ? "GAMEPAD" : "WEB";
}

void noteGamepadCommand(int leftPercent, int rightPercent) {
  hasCommand = true;
  commandEpoch = getModeEpoch();
  lastCommandMs = millis();
  lastLeft = leftPercent;
  lastRight = rightPercent;
}

long gamepadAgeMs() {
  return commandIsCurrent() ? static_cast<long>(millis() - lastCommandMs) : -1;
}

int gamepadLeftPercent() { return commandIsCurrent() ? lastLeft : 0; }
int gamepadRightPercent() { return commandIsCurrent() ? lastRight : 0; }