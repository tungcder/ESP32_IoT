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

  // duty: tien/lui dung MOTOR_SPEED_DUTY, quay tai ccho dung MOTOR_TURN_SPEED_DUTY.
  void setMotorPins(uint8_t a, uint8_t b, uint8_t c, uint8_t d, uint8_t duty) {
    ledcWrite(Config::MOTOR_IN1, a ? duty : 0);
    ledcWrite(Config::MOTOR_IN2, b ? duty : 0);
    ledcWrite(Config::MOTOR_IN3, c ? duty : 0);
    ledcWrite(Config::MOTOR_IN4, d ? duty : 0);
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
  setMotorPins(LOW, LOW, LOW, LOW, 0);
  moving = false;
  setRobotMovement(RobotMovement::Stopped);
  showMovementLeds(LedDirection::Stop);
}
void moveForward() {
  setMotorPins(HIGH, LOW, HIGH, LOW, Config::MOTOR_SPEED_DUTY);
  moving = true;
  setRobotMovement(RobotMovement::Forward);
  showMovementLeds(LedDirection::Forward);
}
void moveBackward() {
  setMotorPins(LOW, HIGH, LOW, HIGH, Config::MOTOR_SPEED_DUTY);
  moving = true;
  setRobotMovement(RobotMovement::Backward);
  showMovementLeds(LedDirection::Backward);
}
void turnRight() {
  setMotorPins(LOW, HIGH, HIGH, LOW, Config::MOTOR_TURN_SPEED_DUTY);
  moving = true;
  setRobotMovement(RobotMovement::Right);
  showMovementLeds(LedDirection::Right);
}
void turnLeft() {
  setMotorPins(HIGH, LOW, LOW, HIGH, Config::MOTOR_TURN_SPEED_DUTY);
  moving = true;
  setRobotMovement(RobotMovement::Left);
  showMovementLeds(LedDirection::Left);
}
bool isCarMoving() { return moving; }
void setMotorSpeeds(int leftPercent, int rightPercent) {
  leftPercent = constrain(leftPercent, -100, 100);
  rightPercent = constrain(rightPercent, -100, 100);

  if (leftPercent == 0 && rightPercent == 0) {
    stopCar();
    return;
  }

  const uint8_t leftDuty =
      (255 * abs(leftPercent) + 50) / 100;
  const uint8_t rightDuty =
      (255 * abs(rightPercent) + 50) / 100;

  // Bên trái: IN1, IN2
  ledcWrite(Config::MOTOR_IN1,
            leftPercent > 0 ? leftDuty : 0);
  ledcWrite(Config::MOTOR_IN2,
            leftPercent < 0 ? leftDuty : 0);

  // Bên phải: IN3, IN4
  ledcWrite(Config::MOTOR_IN3,
            rightPercent > 0 ? rightDuty : 0);
  ledcWrite(Config::MOTOR_IN4,
            rightPercent < 0 ? rightDuty : 0);

  moving = true;

  // Cập nhật trạng thái tổng quát và LED.
  if (leftPercent > 0 && rightPercent > 0) {
    setRobotMovement(RobotMovement::Forward);
    showMovementLeds(LedDirection::Forward);
  } else if (leftPercent < 0 && rightPercent < 0) {
    setRobotMovement(RobotMovement::Backward);
    showMovementLeds(LedDirection::Backward);
  } else if (leftPercent > 0 && rightPercent < 0) {
    setRobotMovement(RobotMovement::Left);
    showMovementLeds(LedDirection::Left);
  } else if (leftPercent < 0 && rightPercent > 0) {
    setRobotMovement(RobotMovement::Right);
    showMovementLeds(LedDirection::Right);
  } else if (leftPercent > 0 || rightPercent > 0) {
    setRobotMovement(RobotMovement::Forward);
    showMovementLeds(LedDirection::Forward);
  } else {
    setRobotMovement(RobotMovement::Backward);
    showMovementLeds(LedDirection::Backward);
  }
}