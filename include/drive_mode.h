#pragma once
#include <Arduino.h>

enum class DriveMode : uint8_t { Manual, Auto, AI, Hybrid };

void setDriveMode(DriveMode mode);
DriveMode getDriveMode();
const char* driveModeName(DriveMode mode);
uint32_t getModeEpoch();
