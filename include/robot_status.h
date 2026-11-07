#pragma once
#include <Arduino.h>

enum class RobotMovement : uint8_t { Stopped, Forward, Backward, Left, Right };

void setRobotMovement(RobotMovement movement);
RobotMovement getRobotMovement();
const char* robotMovementName();
void recordRobotEvent(const char* message);
String robotStatusJson();
