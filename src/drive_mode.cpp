#include "drive_mode.h"
#include "motor_control.h"
#include "ai_control.h"
namespace {
  DriveMode currentMode = DriveMode::Manual;
  uint32_t epoch = 0;
}
void setDriveMode(DriveMode mode) {
  stopCar();
  invalidateAIControl();
  currentMode = mode;
  ++epoch;
}
DriveMode getDriveMode() { return currentMode; }
uint32_t getModeEpoch() { return epoch; }
const char* driveModeName(DriveMode mode) {
  switch (mode) {
    case DriveMode::Auto: return "AUTO";
    case DriveMode::AI: return "AI";
    default: return "MANUAL";
  }
}
