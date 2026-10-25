#include <Arduino.h>
#include "config.h"
#include "drive_mode.h"
#include "motor_control.h"
#include "ultrasonic.h"
#include "servo_scan.h"
#include "obstacle_avoid.h"

namespace {
  enum class State : uint8_t {
    CheckFront, Reverse, StopBeforeScan,
    PointRight, CenterAfterRight,
    PointLeft, CenterAfterLeft,
    Turn, FinishTurn
  };

  State state = State::CheckFront;
  unsigned long stateStarted = 0;
  unsigned long lastFrontCheck = 0;
  int rightDistance = 0;
  int leftDistance = 0;
  bool turnToRight = true;

  void enterState(State next) {
    state = next;
    stateStarted = millis();
  }

  bool elapsed(unsigned long ms) {
    return (unsigned long)(millis() - stateStarted) >= ms;
  }
}

void setupObstacleAvoidance() {
  setServoAngle(90);
  state = State::CheckFront;
  stateStarted = millis();
  lastFrontCheck = 0;
}

void updateObstacleAvoidance() {
  if (getDriveMode() != DriveMode::Auto) return;

  switch (state) {
    case State::CheckFront: {
      if ((unsigned long)(millis() - lastFrontCheck) < 70) return;
      lastFrontCheck = millis();
      int frontDistance = getDistanceCm();
      Serial.printf("Front distance: %d cm\n", frontDistance);

      if (frontDistance > Config::SAFE_DISTANCE_CM) {
        moveForward();
      } else {
        stopCar();
        enterState(State::Reverse);
        moveBackward();
      }
      break;
    }

    case State::Reverse:
      if (elapsed(300)) {
        stopCar();
        enterState(State::StopBeforeScan);
      }
      break;

    case State::StopBeforeScan:
      if (elapsed(100)) {
        setServoAngle(10); // goc phia ben phai
        enterState(State::PointRight);
      }
      break;

    case State::PointRight:
      if (elapsed(300)) {
        rightDistance = getDistanceCm();
        Serial.printf("Right: %d cm\n", rightDistance);
        setServoAngle(90);
        enterState(State::CenterAfterRight);
      }
      break;

    case State::CenterAfterRight:
      if (elapsed(200)) {
        setServoAngle(170); // goc phia ben trai
        enterState(State::PointLeft);
      }
      break;

    case State::PointLeft:
      if (elapsed(300)) {
        leftDistance = getDistanceCm();
        Serial.printf("Left: %d cm\n", leftDistance);
        setServoAngle(90);
        enterState(State::CenterAfterLeft);
      }
      break;

    case State::CenterAfterLeft:
      if (elapsed(200)) {
        // Neu ca hai ben deu bi chan gan, dung lai thay vi quay lien tuc.
        if (rightDistance <= Config::SAFE_DISTANCE_CM &&
            leftDistance <= Config::SAFE_DISTANCE_CM) {
          stopCar();
          Serial.println("Both sides blocked; staying stopped.");
          enterState(State::CheckFront);
        } else {
          turnToRight = rightDistance > leftDistance;
          if (turnToRight) {
            Serial.println("Turning right");
            turnRight();
          } else {
            Serial.println("Turning left");
            turnLeft();
          }
          enterState(State::Turn);
        }
      }
      break;

    case State::Turn:
      if (elapsed(400)) {
        stopCar();
        enterState(State::FinishTurn);
      }
      break;

    case State::FinishTurn:
      if (elapsed(100)) {
        enterState(State::CheckFront);
      }
      break;
  }
}
