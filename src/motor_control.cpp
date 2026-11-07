#include <Arduino.h>
#include "config.h"
#include "motor_control.h"
#include "led_control.h"
#include "robot_status.h"

namespace {
  bool moving = false;
  // ESP32Servo allocates LEDC channel 0 independently of analogWrite.
  // Reserve separate channels so the scanner cannot share a motor output.
  constexpr uint32_t MOTOR_PWM_HZ = 1000;
  constexpr uint8_t MOTOR_PWM_BITS = 8;
  constexpr uint8_t MOTOR_CHANNELS[4] = {4, 5, 6, 7};
  constexpr uint8_t MOTOR_PINS[4] = {
    Config::MOTOR_IN1, Config::MOTOR_IN2,
    Config::MOTOR_IN3, Config::MOTOR_IN4
  };

  void setMotorPins(uint8_t a, uint8_t b, uint8_t c, uint8_t d) {
    ledcWrite(Config::MOTOR_IN1, a ? Config::MOTOR_SPEED_DUTY : 0);
    ledcWrite(Config::MOTOR_IN2, b ? Config::MOTOR_SPEED_DUTY : 0);
    ledcWrite(Config::MOTOR_IN3, c ? Config::MOTOR_SPEED_DUTY : 0);
    ledcWrite(Config::MOTOR_IN4, d ? Config::MOTOR_SPEED_DUTY : 0);
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
  bool pwmReady = true;
  for (int i = 0; i < 4; ++i) {
    pwmReady &= ledcAttachChannel(MOTOR_PINS[i], MOTOR_PWM_HZ,
                                  MOTOR_PWM_BITS, MOTOR_CHANNELS[i]);
  }
  if (!pwmReady) {
    Serial.println("Motor PWM setup failed; ENA/ENB remain disabled.");
    return;
  }
  stopCar();
  digitalWrite(Config::MOTOR_ENA, HIGH);
  digitalWrite(Config::MOTOR_ENB, HIGH);
}
void stopCar() {
  setMotorPins(LOW, LOW, LOW, LOW);
  moving = false;
  setRobotMovement(RobotMovement::Stopped);
  showMovementLeds(LedDirection::Stop);
}
void moveForward() {
  setMotorPins(HIGH, LOW, HIGH, LOW);
  moving = true;
  setRobotMovement(RobotMovement::Forward);
  showMovementLeds(LedDirection::Forward);
}
void moveBackward() {
  setMotorPins(LOW, HIGH, LOW, HIGH);
  moving = true;
  setRobotMovement(RobotMovement::Backward);
  showMovementLeds(LedDirection::Backward);
}
void turnRight() {
  setMotorPins(LOW, HIGH, HIGH, LOW);
  moving = true;
  setRobotMovement(RobotMovement::Right);
  showMovementLeds(LedDirection::Right);
}
void turnLeft() {
  setMotorPins(HIGH, LOW, LOW, HIGH);
  moving = true;
  setRobotMovement(RobotMovement::Left);
  showMovementLeds(LedDirection::Left);
}
bool isCarMoving() { return moving; }
