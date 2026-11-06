#include <Arduino.h>
#include "config.h"
#include "motor_control.h"
#include "led_control.h"

namespace {
  bool moving = false;

  void setMotorPins(uint8_t a, uint8_t b, uint8_t c, uint8_t d) {
    analogWrite(Config::MOTOR_IN1, a ? Config::MOTOR_SPEED_DUTY : 0);
    analogWrite(Config::MOTOR_IN2, b ? Config::MOTOR_SPEED_DUTY : 0);
    analogWrite(Config::MOTOR_IN3, c ? Config::MOTOR_SPEED_DUTY : 0);
    analogWrite(Config::MOTOR_IN4, d ? Config::MOTOR_SPEED_DUTY : 0);
  }
}

void setupMotors() {
  digitalWrite(Config::MOTOR_ENA, LOW);
  digitalWrite(Config::MOTOR_ENB, LOW);
  pinMode(Config::MOTOR_ENA, OUTPUT);
  pinMode(Config::MOTOR_ENB, OUTPUT);
  pinMode(Config::MOTOR_IN1, OUTPUT);
  pinMode(Config::MOTOR_IN2, OUTPUT);
  pinMode(Config::MOTOR_IN3, OUTPUT);
  pinMode(Config::MOTOR_IN4, OUTPUT);
  stopCar();
  digitalWrite(Config::MOTOR_ENA, HIGH);
  digitalWrite(Config::MOTOR_ENB, HIGH);
}
void stopCar() {
  setMotorPins(LOW, LOW, LOW, LOW);
  moving = false;
  showMovementLeds(LedDirection::Stop);
}
void moveForward() {
  setMotorPins(HIGH, LOW, HIGH, LOW);
  moving = true;
  showMovementLeds(LedDirection::Forward);
}
void moveBackward() {
  setMotorPins(LOW, HIGH, LOW, HIGH);
  moving = true;
  showMovementLeds(LedDirection::Backward);
}
void turnRight() {
  setMotorPins(LOW, HIGH, HIGH, LOW);
  moving = true;
  showMovementLeds(LedDirection::Right);
}
void turnLeft() {
  setMotorPins(HIGH, LOW, LOW, HIGH);
  moving = true;
  showMovementLeds(LedDirection::Left);
}
bool isCarMoving() { return moving; }
