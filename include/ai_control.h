#pragma once
#include <Arduino.h>
#include "robot_status.h"

void invalidateAIControl();
String beginAIControl();
bool ownsAIControl(const String& session);
bool acceptAICommand(const String& session, uint32_t sequence, RobotMovement movement, uint8_t speed);
void updateAIControl();
bool aiControlActive();
int aiDistanceCm();
const char* aiSafetyReason();
const char* aiSensorState();
unsigned long aiSensorAgeMs();
