#include <Arduino.h>
#include <ESP32Servo.h>
#include "config.h"
#include "servo_scan.h"

namespace {
  Servo scanner;
}
void setupServoScan() {
  // ESP32Servo su dung timer PWM phu hop cho ESP32
  scanner.setPeriodHertz(50);
  scanner.attach(Config::SERVO_PIN, 500, 2400);
  scanner.write(90);
}
void setServoAngle(int angle) {
  scanner.write(constrain(angle, 0, 180));
}
