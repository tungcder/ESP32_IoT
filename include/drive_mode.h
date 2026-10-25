#pragma once
#include <Arduino.h>

enum class DriveMode : uint8_t { Manual, Auto };

void setDriveMode(DriveMode mode);
DriveMode getDriveMode();
