#include "hybrid_control.h"
#include "drive_mode.h"
#include "ai_control.h"
#include "motor_control.h"
#include "servo_scan.h"
#include "obstacle_avoid.h"
#include "robot_status.h"

namespace {
  HybridBehavior current = HybridBehavior::Hold;
}

void resetHybridControl() { current = HybridBehavior::Hold; }

void setHybridBehavior(HybridBehavior behavior) {
  if (getDriveMode() != DriveMode::Hybrid || current == behavior) return;
  // Cancel the previous motor action before handing over the scanner or motors.
  stopCar();
  setServoAngle(90);
  current = behavior;
  if (behavior == HybridBehavior::Search) setupObstacleAvoidance();
  if (behavior == HybridBehavior::Track) prepareAITracking();
  recordRobotEvent(behavior == HybridBehavior::Search ? "Hybrid: obstacle search"
                   : behavior == HybridBehavior::Track ? "Hybrid: AI tracking"
                   : "Hybrid: stopped; confirming or waiting for target");
}

bool hybridSearching() {
  return getDriveMode() == DriveMode::Hybrid && current == HybridBehavior::Search;
}
bool hybridTracking() {
  return getDriveMode() == DriveMode::Hybrid && current == HybridBehavior::Track;
}
const char* hybridStateName() {
  if (getDriveMode() != DriveMode::Hybrid) return "IDLE";
  return current == HybridBehavior::Search ? "SEARCH"
       : current == HybridBehavior::Track ? "TRACK" : "HOLD";
}
