#include "robot_status.h"
#include "drive_mode.h"
#include "ai_control.h"
#include <esp_system.h>
#include <string.h>

namespace {
  constexpr size_t EVENT_COUNT = 24;
  constexpr size_t MESSAGE_SIZE = 72;
  struct Event {
    uint32_t id;
    unsigned long ms;
    DriveMode mode;
    char message[MESSAGE_SIZE];
  };
  Event events[EVENT_COUNT] = {};
  size_t nextEvent = 0;
  size_t eventCount = 0;
  uint32_t nextId = 1;
  RobotMovement currentMovement = RobotMovement::Stopped;
  const uint32_t bootId = esp_random();

  const char* movementName(RobotMovement movement) {
    switch (movement) {
      case RobotMovement::Forward: return "FORWARD";
      case RobotMovement::Backward: return "BACKWARD";
      case RobotMovement::Left: return "LEFT";
      case RobotMovement::Right: return "RIGHT";
      default: return "STOPPED";
    }
  }

  void appendEscaped(String& json, const char* value) {
    json += '"';
    for (const char* p = value; *p; ++p) {
      if (*p == '"' || *p == '\\') json += '\\';
      if (static_cast<uint8_t>(*p) >= 0x20) json += *p;
    }
    json += '"';
  }
}

void recordRobotEvent(const char* message) {
  Event& event = events[nextEvent];
  event.id = nextId++;
  event.ms = millis();
  event.mode = getDriveMode();
  strncpy(event.message, message, MESSAGE_SIZE - 1);
  event.message[MESSAGE_SIZE - 1] = '\0';
  nextEvent = (nextEvent + 1) % EVENT_COUNT;
  if (eventCount < EVENT_COUNT) ++eventCount;
}

void setRobotMovement(RobotMovement movement) {
  if (currentMovement == movement) return;
  currentMovement = movement;
  char message[MESSAGE_SIZE];
  snprintf(message, sizeof(message), "Movement: %s", movementName(movement));
  recordRobotEvent(message);
}

RobotMovement getRobotMovement() { return currentMovement; }
const char* robotMovementName() { return movementName(currentMovement); }

String robotStatusJson() {
  String json;
  json.reserve(3300);
  json += F("{\"drive_mode\":\"");
  json += driveModeName(getDriveMode());
  json += F("\",\"movement\":\"");
  json += robotMovementName();
  json += F("\",\"uptime_ms\":");
  json += millis();
  json += F(",\"mode_epoch\":"); json += getModeEpoch();
  json += F(",\"boot_id\":"); json += bootId;
  json += F(",\"ai_active\":"); json += aiControlActive() ? F("true") : F("false");
  json += F(",\"distance_cm\":"); json += aiDistanceCm();
  json += F(",\"ai_safety\":"); appendEscaped(json, aiSafetyReason());
  json += F(",\"ai_sensor_state\":"); appendEscaped(json, aiSensorState());
  json += F(",\"ai_sensor_age_ms\":"); json += aiSensorAgeMs();
  json += F(",\"events\":[");
  const size_t first = (nextEvent + EVENT_COUNT - eventCount) % EVENT_COUNT;
  for (size_t i = 0; i < eventCount; ++i) {
    if (i) json += ',';
    const Event& event = events[(first + i) % EVENT_COUNT];
    json += F("{\"id\":");
    json += event.id;
    json += F(",\"ms\":");
    json += event.ms;
    json += F(",\"mode\":\"");
    json += driveModeName(event.mode);
    json += F("\",\"message\":");
    appendEscaped(json, event.message);
    json += '}';
  }
  json += F("]}");
  return json;
}
