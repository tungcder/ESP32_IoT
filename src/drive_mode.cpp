#include "drive_mode.h"
namespace {
  DriveMode currentMode = DriveMode::Manual;
}
void setDriveMode(DriveMode mode) { currentMode = mode; }
DriveMode getDriveMode() { return currentMode; }
