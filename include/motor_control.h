#pragma once
#include <Arduino.h>
#include "robot_status.h"

void setupMotors();
void stopCar();
void moveForward();
void moveBackward();
void turnRight();
void turnLeft();
bool isCarMoving();
void applyAIMovement(RobotMovement movement, uint8_t speedPercent);
void setMotorSpeeds(int leftPercent, int rightPercent);
