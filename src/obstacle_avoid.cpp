
#include <Arduino.h>
#include "config.h"
#include "drive_mode.h"
#include "motor_control.h"
#include "ultrasonic.h"
#include "servo_scan.h"
#include "obstacle_avoid.h"
#include "robot_status.h"
#include "hybrid_control.h"

namespace {

enum class State : uint8_t {
    CheckFront, Reverse,
    ScanLeft135, ScanLeft180,
    ScanRight45, ScanRight0, Turn
};

constexpr int MIN_VALID_CM = 2;
constexpr int MAX_VALID_CM = 400;
constexpr int SERVO_CENTER = 90;
constexpr int SERVO_LEFT_NEAR = 135;
constexpr int SERVO_LEFT_FAR = 180;
constexpr int SERVO_RIGHT_NEAR = 45;
constexpr int SERVO_RIGHT_FAR = 0;

constexpr unsigned long FRONT_INTERVAL_MS = 70;
constexpr unsigned long SERVO_SETTLE_MS = 250;
constexpr unsigned long SERVO_CROSS_SETTLE_MS = 350;

State state = State::CheckFront;
unsigned long stateStarted = 0;
unsigned long lastFrontCheck = 0;
unsigned long reverseDurationMs = 0;
unsigned long turnDurationMs = 0;
unsigned long initializedAt = 0;
int lastDistance = 0;

bool leftNearClear = false;
bool rightNearClear = false;

void enterState(State next) {
    state = next;
    stateStarted = millis();
}

bool elapsed(unsigned long duration) {
    return millis() - stateStarted >= duration;
}

int readDistanceCm() {
    int distance = getDistanceCm();
    lastDistance = distance;
    return (distance >= MIN_VALID_CM && distance <= MAX_VALID_CM)
        ? distance : -1;
}

bool isClear(int distance) {
    return distance != -1 && distance > Config::SAFE_DISTANCE_CM;
}

void startReverse(int distanceCm) {
    stopCar();
    setServoAngle(SERVO_CENTER);

    leftNearClear = false;
    rightNearClear = false;

    reverseDurationMs =
        distanceCm * Config::AUTO_REVERSE_MS_PER_CM;

    char message[72];
    snprintf(message, sizeof(message),
             "Obstacle ahead; reverse target %d cm", distanceCm);
    recordRobotEvent(message);

    Serial.printf("Reverse: %d cm (%lu ms)\n",
                  distanceCm, reverseDurationMs);

    moveBackward();
    enterState(State::Reverse);
}

void startTurn(bool right) {
    stopCar();
    setServoAngle(SERVO_CENTER);

    turnDurationMs = right
        ? Config::AUTO_RIGHT_90_MS
        : Config::AUTO_LEFT_90_MS;

    if (right) {
        recordRobotEvent("Right clear; turning right");
        turnRight();
    } else {
        recordRobotEvent("Left clear; turning left");
        turnLeft();
    }

    enterState(State::Turn);
}

void logDistance(const char* direction, int angle, int distance) {
    Serial.printf("%s[%d deg]: %d cm\n",
                  direction, angle, distance);

    char message[72];
    snprintf(message, sizeof(message),
             "%s %d deg: %d cm", direction, angle, distance);
    recordRobotEvent(message);
}

}

void setupObstacleAvoidance() {
    setServoAngle(SERVO_CENTER);

    state = State::CheckFront;
    stateStarted = millis();
    initializedAt = millis();
    lastDistance = 0;
    lastFrontCheck = millis() - FRONT_INTERVAL_MS;

    leftNearClear = false;
    rightNearClear = false;
    reverseDurationMs = 0;
    turnDurationMs = 0;

    Serial.println("Obstacle avoidance initialized.");
}

void updateObstacleAvoidance() {
    if (getDriveMode() != DriveMode::Auto && !hybridSearching()) return;
    if (hybridSearching() && millis() - initializedAt < Config::HYBRID_SERVO_SETTLE_MS) return;

    switch (state) {

        case State::CheckFront: {
            if (millis() - lastFrontCheck < FRONT_INTERVAL_MS)
                return;

            lastFrontCheck = millis();
            setServoAngle(SERVO_CENTER);

            int distance = readDistanceCm();
            if (hybridSearching() && distance == -1) { stopCar(); break; }
            Serial.printf("Front[90 deg]: %d cm\n", distance);

            if (isClear(distance))
                moveForward();
            else
                startReverse(Config::AUTO_REVERSE_CM);

            break;
        }

        case State::Reverse:
            if (elapsed(reverseDurationMs)) {
                stopCar();
                recordRobotEvent("Reversing done; scanning left");

                setServoAngle(SERVO_LEFT_NEAR);
                enterState(State::ScanLeft135);
            }
            break;

        case State::ScanLeft135:
            if (elapsed(SERVO_SETTLE_MS)) {
                int distance = readDistanceCm();
                if (hybridSearching() && distance == -1) { stopCar(); break; }
                leftNearClear = isClear(distance);

                logDistance("Left", 135, distance);
                setServoAngle(SERVO_LEFT_FAR);
                enterState(State::ScanLeft180);
            }
            break;

        case State::ScanLeft180:
            if (elapsed(SERVO_SETTLE_MS)) {
                int distance = readDistanceCm();
                if (hybridSearching() && distance == -1) { stopCar(); break; }
                logDistance("Left", 180, distance);

                if (leftNearClear && isClear(distance)) {
                    startTurn(false);
                } else {
                    setServoAngle(SERVO_RIGHT_NEAR);
                    enterState(State::ScanRight45);
                }
            }
            break;

        case State::ScanRight45:
            if (elapsed(SERVO_CROSS_SETTLE_MS)) {
                int distance = readDistanceCm();
                if (hybridSearching() && distance == -1) { stopCar(); break; }
                rightNearClear = isClear(distance);

                logDistance("Right", 45, distance);
                setServoAngle(SERVO_RIGHT_FAR);
                enterState(State::ScanRight0);
            }
            break;

        case State::ScanRight0:
            if (elapsed(SERVO_SETTLE_MS)) {
                int distance = readDistanceCm();
                if (hybridSearching() && distance == -1) { stopCar(); break; }
                logDistance("Right", 0, distance);

                if (rightNearClear && isClear(distance)) {
                    startTurn(true);
                } else {
                    recordRobotEvent(
                        "Both sides blocked; scanning again");
                    startReverse(Config::AUTO_RETRY_REVERSE_CM);
                }
            }
            break;

        case State::Turn:
            if (elapsed(turnDurationMs)) {
                stopCar();
                recordRobotEvent("Turn complete; checking front");

                setServoAngle(SERVO_CENTER);
                if (!hybridSearching()) moveForward();

                lastFrontCheck = millis() - FRONT_INTERVAL_MS;
                enterState(State::CheckFront);
            }
            break;
    }
}

int obstacleDistanceCm() { return lastDistance; }
