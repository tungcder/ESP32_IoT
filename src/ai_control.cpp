#include "ai_control.h"
#include "config.h"
#include "drive_mode.h"
#include "motor_control.h"
#include "servo_scan.h"
#include "ultrasonic.h"
#include <esp_system.h>
#include <string.h>

namespace {
  String owner;
  uint32_t lastSequence = 0;
  unsigned long lastCommand = 0, lastSensor = 0, centeredAt = 0;
  int distance = 0;
  bool nearTarget = true;
  RobotMovement requested = RobotMovement::Stopped;
  uint8_t speed = 0;
  const char* reason = "idle";
  const char* sensorState = "idle";
  unsigned long lastValidSensor = 0, lastSensorPrint = 0;

  void apply() {
    if (requested == RobotMovement::Forward) {
      if (distance < 2 || distance > 400) { reason = "invalid_distance"; stopCar(); return; }
      if (distance <= Config::AI_STOP_DISTANCE_CM) nearTarget = true;
      if (distance > Config::AI_RESUME_DISTANCE_CM) nearTarget = false;
      if (nearTarget) { reason = "distance_hold"; stopCar(); return; }
    }
    reason = "ok";
    applyAIMovement(requested, speed);
  }
}

void invalidateAIControl() {
  owner = "";
  requested = RobotMovement::Stopped;
  speed = 0;
  distance = 0;
  nearTarget = true;
  reason = "idle";
  sensorState = "idle";
  lastValidSensor = 0;
}

String beginAIControl() {
  char value[33];
  snprintf(value, sizeof(value), "%08lx%08lx%08lx%08lx",
           (unsigned long)esp_random(), (unsigned long)esp_random(),
           (unsigned long)esp_random(), (unsigned long)esp_random());
  owner = value;
  lastSequence = 0;
  lastCommand = millis();
  lastSensor = millis() - Config::AI_SENSOR_INTERVAL_MS;
  setServoAngle(90);
  centeredAt = millis();
  sensorState = "warming_up";
  lastValidSensor = 0;
  lastSensorPrint = millis() - 1000;
  recordRobotEvent("AI session started");
  return owner;
}

bool ownsAIControl(const String& session) {
  return getDriveMode() == DriveMode::AI && owner.length() && session == owner;
}

bool acceptAICommand(const String& session, uint32_t sequence, RobotMovement movement, uint8_t percent) {
  updateAIControl(); // Expired sessions cannot be revived by a delayed packet.
  if (!ownsAIControl(session) || sequence <= lastSequence) return false;
  lastSequence = sequence;
  lastCommand = millis();
  requested = movement;
  speed = percent;
  apply();
  return true;
}

void updateAIControl() {
  if (getDriveMode() != DriveMode::AI || !owner.length()) return;
  if ((unsigned long)(millis() - lastCommand) > Config::COMMAND_TIMEOUT_MS) {
    stopCar();
    invalidateAIControl();
    reason = "command_timeout";
    recordRobotEvent("AI command timeout; session revoked");
    return;
  }
  if ((unsigned long)(millis() - centeredAt) >= 300 &&
      (unsigned long)(millis() - lastSensor) >= Config::AI_SENSOR_INTERVAL_MS) {
    lastSensor = millis();
    distance = getDistanceCm();
    const char* nextSensor = distance == 0 ? "no_echo" : distance < 2 || distance > 400 ? "out_of_range" : "ok";
    if (strcmp(nextSensor, sensorState) != 0) {
      recordRobotEvent(distance >= 2 && distance <= 400 ? "AI sonar reading valid" : "AI sonar invalid; forward blocked");
    }
    sensorState = nextSensor;
    if (distance >= 2 && distance <= 400) lastValidSensor = millis();
    if ((unsigned long)(millis() - lastSensorPrint) >= 1000) {
      lastSensorPrint = millis();
      Serial.printf("[AI sonar] %d cm | %s | forward needs valid echo >25 cm\n", distance, sensorState);
    }
    apply(); // Local distance guard works even between laptop commands.
  }
}

bool aiControlActive() { return owner.length() > 0; }
int aiDistanceCm() { return distance; }
const char* aiSafetyReason() { return reason; }
const char* aiSensorState() { return sensorState; }
unsigned long aiSensorAgeMs() { return lastValidSensor ? millis() - lastValidSensor : 0; }
