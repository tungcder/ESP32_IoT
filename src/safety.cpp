#include <Arduino.h>
#include "config.h"
#include "drive_mode.h"
#include "motor_control.h"
#include "safety.h"
#include "robot_status.h"

namespace {
  unsigned long lastCommandTime = 0;
}
void resetCommandTimer() { lastCommandTime = millis(); }
void checkCommandTimeout() {
  if (getDriveMode() == DriveMode::Manual &&
      isCarMoving() &&
      (unsigned long)(millis() - lastCommandTime) > Config::COMMAND_TIMEOUT_MS) {
    Serial.println("Safety timeout: stopping robot");
    stopCar();
    recordRobotEvent("Manual command timeout");
  }
}
