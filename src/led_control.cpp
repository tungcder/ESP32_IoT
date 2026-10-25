#include <Arduino.h>
#include "config.h"
#include "led_control.h"

namespace {
  LedMode currentLedMode = LedMode::Auto;
  bool allLedsOnState = false;

  void writeAll(bool state) {
    digitalWrite(Config::LED_FRONT_LEFT, state ? HIGH : LOW);
    digitalWrite(Config::LED_FRONT_RIGHT, state ? HIGH : LOW);
    digitalWrite(Config::LED_REAR_LEFT, state ? HIGH : LOW);
    digitalWrite(Config::LED_REAR_RIGHT, state ? HIGH : LOW);
  }
}

void setupLeds() {
  pinMode(Config::LED_FRONT_LEFT, OUTPUT);
  pinMode(Config::LED_FRONT_RIGHT, OUTPUT);
  pinMode(Config::LED_REAR_LEFT, OUTPUT);
  pinMode(Config::LED_REAR_RIGHT, OUTPUT);
  allLedsOff();
}

void allLedsOff() {
  writeAll(false);
}

void allLedsOn() {
  writeAll(true);
}

void updateManualLeds() {
  if (currentLedMode == LedMode::Manual) {
    if (allLedsOnState) allLedsOn();
    else allLedsOff();
  }
}

void setLedMode(LedMode mode) {
  currentLedMode = mode;
  if (mode == LedMode::Auto) {
    allLedsOff();
  } else {
    updateManualLeds();
  }
}

LedMode getLedMode() {
  return currentLedMode;
}

void setAllLeds(bool on) {
  currentLedMode = LedMode::Manual;
  allLedsOnState = on;
  if (on) allLedsOn();
  else allLedsOff();
}

void showMovementLeds(LedDirection direction) {
  if (currentLedMode == LedMode::Manual) {
    updateManualLeds();
    return;
  }

  allLedsOff();
  switch (direction) {
    case LedDirection::Forward:
      digitalWrite(Config::LED_FRONT_LEFT, HIGH);
      digitalWrite(Config::LED_FRONT_RIGHT, HIGH);
      break;
    case LedDirection::Backward:
      digitalWrite(Config::LED_REAR_LEFT, HIGH);
      digitalWrite(Config::LED_REAR_RIGHT, HIGH);
      break;
    case LedDirection::Right:
      digitalWrite(Config::LED_FRONT_RIGHT, HIGH);
      digitalWrite(Config::LED_REAR_RIGHT, HIGH);
      break;
    case LedDirection::Left:
      digitalWrite(Config::LED_FRONT_LEFT, HIGH);
      digitalWrite(Config::LED_REAR_LEFT, HIGH);
      break;
    case LedDirection::Stop:
    default:
      break;
  }
}
