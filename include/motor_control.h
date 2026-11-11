#pragma once
#include <Arduino.h>

void setupMotors();
void stopCar();
void moveForward();
void moveBackward();
void turnRight();
void turnLeft();
bool isCarMoving();
void setMotorSpeeds(int leftPercent, int rightPercent);
