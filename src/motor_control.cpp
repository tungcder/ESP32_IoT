
#include <Arduino.h>
#include "config.h"
#include "motor_control.h"
#include "led_control.h"
#include "robot_status.h"

namespace {
  bool moving = false;

  // Dung cac kenh PWM rieng, tranh trung voi ESP32Servo.
  constexpr uint32_t MOTOR_PWM_HZ = 1000;
  constexpr uint8_t MOTOR_PWM_BITS = 8;

  constexpr uint8_t MOTOR_CHANNELS[4] = {4, 5, 6, 7};

  constexpr uint8_t MOTOR_PINS[4] = {
    Config::MOTOR_IN1,
    Config::MOTOR_IN2,
    Config::MOTOR_IN3,
    Config::MOTOR_IN4
  };

  // Dieu khien 2 dong co trai va phai.
  // a,b: dong co trai
  // c,d: dong co phai
  void setMotorPins(
    uint8_t a,
    uint8_t b,
    uint8_t c,
    uint8_t d,
    uint8_t duty
  ) {
    ledcWrite(Config::MOTOR_IN1, a ? duty : 0);
    ledcWrite(Config::MOTOR_IN2, b ? duty : 0);
    ledcWrite(Config::MOTOR_IN3, c ? duty : 0);
    ledcWrite(Config::MOTOR_IN4, d ? duty : 0);
  }
}

// =====================================================
// KHOI TAO DONG CO
// =====================================================

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

  for (int i = 0; i < 4; i++) {
    pwmReady &= ledcAttachChannel(
      MOTOR_PINS[i],
      MOTOR_PWM_HZ,
      MOTOR_PWM_BITS,
      MOTOR_CHANNELS[i]
    );
  }

  if (!pwmReady) {
    Serial.println(
      "Motor PWM setup failed; ENA/ENB remain disabled."
    );
    return;
  }

  stopCar();

  digitalWrite(Config::MOTOR_ENA, HIGH);
  digitalWrite(Config::MOTOR_ENB, HIGH);

  Serial.println("Motor setup completed.");
}

// =====================================================
// DUNG ROBOT
// =====================================================

void stopCar() {
  setMotorPins(LOW, LOW, LOW, LOW, 0);

  moving = false;

  setRobotMovement(RobotMovement::Stopped);
  showMovementLeds(LedDirection::Stop);
}

// =====================================================
// DI CHUYEN THANG
// =====================================================

void moveForward() {
  setMotorPins(
    HIGH, LOW,
    HIGH, LOW,
    Config::MOTOR_SPEED_DUTY
  );

  moving = true;

  setRobotMovement(RobotMovement::Forward);
  showMovementLeds(LedDirection::Forward);
}

// =====================================================
// DI CHUYEN LUI
// =====================================================

void moveBackward() {
  setMotorPins(
    LOW, HIGH,
    LOW, HIGH,
    Config::MOTOR_SPEED_DUTY
  );

  moving = true;

  setRobotMovement(RobotMovement::Backward);
  showMovementLeds(LedDirection::Backward);
}

// =====================================================
// RE PHAI
// =====================================================

void turnRight() {
  // Da dao anh xa theo ket qua thu nghiem thuc te.
  // Ben trai lui, ben phai tien.

  setMotorPins(
    LOW, HIGH,
    HIGH, LOW,
    Config::MOTOR_TURN_SPEED_DUTY
  );

  moving = true;

  setRobotMovement(RobotMovement::Right);
  showMovementLeds(LedDirection::Right);
}

// =====================================================
// RE TRAI
// =====================================================

void turnLeft() {
  // Ben trai tien, ben phai lui.

  setMotorPins(
    HIGH, LOW,
    LOW, HIGH,
    Config::MOTOR_TURN_SPEED_DUTY
  );

  moving = true;

  setRobotMovement(RobotMovement::Left);
  showMovementLeds(LedDirection::Left);
}

// =====================================================
// KIEM TRA TRANG THAI DI CHUYEN
// =====================================================

bool isCarMoving() {
  return moving;
}

// =====================================================
// DIEU KHIEN TOC DO TUNG BEN
// leftPercent: toc do ben trai
// rightPercent: toc do ben phai
// Gia tri: -100 den 100
// =====================================================

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

  // Dong co ben trai
  ledcWrite(
    Config::MOTOR_IN1,
    leftPercent > 0 ? leftDuty : 0
  );

  ledcWrite(
    Config::MOTOR_IN2,
    leftPercent < 0 ? leftDuty : 0
  );

  // Dong co ben phai
  ledcWrite(
    Config::MOTOR_IN3,
    rightPercent > 0 ? rightDuty : 0
  );

  ledcWrite(
    Config::MOTOR_IN4,
    rightPercent < 0 ? rightDuty : 0
  );

  moving = true;

  // Cap nhat trang thai theo chieu quay da hieu chinh.
  if (leftPercent > 0 && rightPercent > 0) {

    setRobotMovement(RobotMovement::Forward);
    showMovementLeds(LedDirection::Forward);

  } else if (leftPercent < 0 && rightPercent < 0) {

    setRobotMovement(RobotMovement::Backward);
    showMovementLeds(LedDirection::Backward);

  } else if (leftPercent > 0 && rightPercent < 0) {

    // Ben trai tien, ben phai lui -> quay trai
    setRobotMovement(RobotMovement::Left);
    showMovementLeds(LedDirection::Left);

  } else if (leftPercent < 0 && rightPercent > 0) {

    // Ben trai lui, ben phai tien -> quay phai
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

void applyAIMovement(RobotMovement movement, uint8_t speedPercent) {
  const bool turning = movement == RobotMovement::Left || movement == RobotMovement::Right;
  const uint8_t limit = turning ? Config::MOTOR_TURN_SPEED_PERCENT : Config::MOTOR_SPEED_PERCENT;
  const uint8_t duty = (255 * min(speedPercent, limit) + 50) / 100;
  if (!duty || movement == RobotMovement::Stopped) { stopCar(); return; }
  LedDirection led = LedDirection::Stop;
  switch (movement) {
    case RobotMovement::Forward: setMotorPins(1, 0, 1, 0, duty); led = LedDirection::Forward; break;
    case RobotMovement::Left: setMotorPins(1, 0, 0, 1, duty); led = LedDirection::Left; break;
    case RobotMovement::Right: setMotorPins(0, 1, 1, 0, duty); led = LedDirection::Right; break;
    default: stopCar(); return;
  }
  moving = true;
  setRobotMovement(movement);
  showMovementLeds(led);
}
