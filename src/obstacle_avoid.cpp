#include <Arduino.h>
#include "config.h"
#include "drive_mode.h"
#include "motor_control.h"
#include "ultrasonic.h"
#include "servo_scan.h"
#include "obstacle_avoid.h"
#include "robot_status.h"

namespace {
  enum class State : uint8_t {
    CheckFront, Reverse, ScanLeft45, ScanLeft0,
    ScanRight135, ScanRight180, Turn
  };

  constexpr int MIN_VALID_CM = 2;
  constexpr int MAX_VALID_CM = 400;
  constexpr int NO_ECHO = -1;
  constexpr unsigned long FRONT_INTERVAL_MS = 70;
  constexpr unsigned long SERVO_SETTLE_MS = 250;
  constexpr unsigned long SERVO_CROSS_SETTLE_MS = 350;

  State state = State::CheckFront;
  unsigned long stateStarted = 0;
  unsigned long lastFrontCheck = 0;
  bool left45Clear = false;
  bool right135Clear = false;
  unsigned long reverseDurationMs = 0;
  unsigned long turnDurationMs = 0;

  void enterState(State next) {
    state = next;
    stateStarted = millis();
  }

  bool elapsed(unsigned long ms) {
    return (unsigned long)(millis() - stateStarted) >= ms;
  }

  // One ping per check keeps the WebServer responsive and leaves enough time
  // between HC-SR04 triggers for the previous echo to die away.
  int readDistanceCm() {
    const int distance = getDistanceCm();
    return distance >= MIN_VALID_CM && distance <= MAX_VALID_CM
               ? distance : NO_ECHO;
  }

  bool isClear(int distance) {
    return distance != NO_ECHO && distance > Config::SAFE_DISTANCE_CM;
  }

  void startReverse(int distanceCm) {
    setServoAngle(90);
    left45Clear = false;
    right135Clear = false;
    reverseDurationMs = distanceCm * Config::AUTO_REVERSE_MS_PER_CM;
    Serial.printf("Reverse target: %d cm (timed estimate: %lu ms)\n",
                  distanceCm, reverseDurationMs);
    char message[72];
    snprintf(message, sizeof(message), "Obstacle ahead; reverse target %d cm", distanceCm);
    recordRobotEvent(message);
    moveBackward();
    enterState(State::Reverse);
  }

  void startTurn(bool right) {
    // Center the sensor during the turn, so it is ready when driving resumes.
    setServoAngle(90);
    turnDurationMs = right ? Config::AUTO_RIGHT_90_MS : Config::AUTO_LEFT_90_MS;
    recordRobotEvent(right ? "Right clear; turning right" : "Left clear; turning left");
    if (right) turnRight();
    else turnLeft();
    enterState(State::Turn);
  }
}

void setupObstacleAvoidance() {
  setServoAngle(90);
  state = State::CheckFront;
  stateStarted = millis();
  lastFrontCheck = millis() - FRONT_INTERVAL_MS;
  left45Clear = false;
  right135Clear = false;
}

void updateObstacleAvoidance() {
  if (getDriveMode() != DriveMode::Auto) return;

  switch (state) {
    case State::CheckFront: {
      if ((unsigned long)(millis() - lastFrontCheck) < FRONT_INTERVAL_MS) return;
      lastFrontCheck = millis();
      const int distance = readDistanceCm();
      Serial.printf("Front[90 deg]: %d cm\n", distance);
      if (isClear(distance)) {
        moveForward();
      } else {
        // A missing echo is unknown space, so back away and scan rather than
        // driving forward blindly or remaining stopped forever.
        startReverse(Config::AUTO_REVERSE_CM);
      }
      break;
    }

    case State::Reverse:
      if (elapsed(reverseDurationMs)) {
        stopCar();
        recordRobotEvent("Reversing done; scanning left");
        setServoAngle(45);
        enterState(State::ScanLeft45);
      }
      break;

    case State::ScanLeft45:
      if (elapsed(SERVO_SETTLE_MS)) {
        const int distance = readDistanceCm();
        left45Clear = isClear(distance);
        Serial.printf("Left[45 deg]: %d cm\n", distance);
        char message[72];
        snprintf(message, sizeof(message), "Left 45 deg: %d cm", distance);
        recordRobotEvent(message);
        setServoAngle(0);
        enterState(State::ScanLeft0);
      }
      break;

    case State::ScanLeft0:
      if (elapsed(SERVO_SETTLE_MS)) {
        const int distance = readDistanceCm();
        Serial.printf("Left[0 deg]: %d cm\n", distance);
        char message[72];
        snprintf(message, sizeof(message), "Left 0 deg: %d cm", distance);
        recordRobotEvent(message);
        if (left45Clear && isClear(distance)) {
          Serial.println("Left clear; turning left.");
          startTurn(false);
        } else {
          setServoAngle(135);
          enterState(State::ScanRight135);
        }
      }
      break;

    case State::ScanRight135:
      if (elapsed(SERVO_CROSS_SETTLE_MS)) {
        const int distance = readDistanceCm();
        right135Clear = isClear(distance);
        Serial.printf("Right[135 deg]: %d cm\n", distance);
        char message[72];
        snprintf(message, sizeof(message), "Right 135 deg: %d cm", distance);
        recordRobotEvent(message);
        setServoAngle(180);
        enterState(State::ScanRight180);
      }
      break;

    case State::ScanRight180:
      if (elapsed(SERVO_SETTLE_MS)) {
        const int distance = readDistanceCm();
        Serial.printf("Right[180 deg]: %d cm\n", distance);
        char message[72];
        snprintf(message, sizeof(message), "Right 180 deg: %d cm", distance);
        recordRobotEvent(message);
        const bool rightClear = right135Clear && isClear(distance);
        if (rightClear) {
          Serial.println("Right clear; turning right 90 degrees (timed estimate).");
          startTurn(true);
        } else {
          Serial.println("Both sides blocked; reverse 30 cm and scan again.");
          recordRobotEvent("Both sides blocked; scanning again");
          startReverse(Config::AUTO_RETRY_REVERSE_CM);
        }
      }
      break;

    case State::Turn:
      if (elapsed(turnDurationMs)) {
        recordRobotEvent("Turn complete; checking front");
        moveForward();
        lastFrontCheck = millis() - FRONT_INTERVAL_MS;
        enterState(State::CheckFront);
      }
      break;
  }
}
 