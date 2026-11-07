#include <Arduino.h>
#include "config.h"
#include "led_control.h"

namespace {
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
  writeAll(false);
}

void showMovementLeds(LedDirection direction) {
  writeAll(false);
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
