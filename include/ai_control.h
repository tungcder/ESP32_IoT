#pragma once
#include <Arduino.h>
#include "robot_status.h"
#include "hybrid_control.h"

void invalidateAIControl();
String beginAIControl();
void prepareAITracking();
bool ownsAIControl(const String& session);
bool acceptAICommand(const String& session, uint32_t sequence, RobotMovement movement, uint8_t speed);
bool acceptHybridCommand(const String& session, uint32_t sequence, HybridBehavior behavior,
                         RobotMovement movement, uint8_t speed);
void updateAIControl();
bool aiControlActive();
int aiDistanceCm();
const char* aiSafetyReason();
const char* aiSensorState();
unsigned long aiSensorAgeMs();
