#include <Arduino.h>
#include "config.h"

// Standalone L298N test: both motors run for 3 seconds, then stay stopped.
// ENA/ENB may be bridged on the module or wired to GPIO13/GPIO14.
// Use a motor supply within the motor's rating.
namespace {
  constexpr unsigned long MOTOR_RUN_MS = 3000;

  void stopTestMotors() {
    analogWrite(Config::MOTOR_IN1, 0);
    analogWrite(Config::MOTOR_IN2, 0);
    analogWrite(Config::MOTOR_IN3, 0);
    analogWrite(Config::MOTOR_IN4, 0);
  }
}

void setup() {
  digitalWrite(Config::MOTOR_ENA, LOW);
  digitalWrite(Config::MOTOR_ENB, LOW);
  pinMode(Config::MOTOR_ENA, OUTPUT);
  pinMode(Config::MOTOR_ENB, OUTPUT);
  pinMode(Config::MOTOR_IN1, OUTPUT);
  pinMode(Config::MOTOR_IN2, OUTPUT);
  pinMode(Config::MOTOR_IN3, OUTPUT);
  pinMode(Config::MOTOR_IN4, OUTPUT);
  stopTestMotors();

  Serial.begin(115200);
  Serial.println("\nL298N test: both motors run for 3 seconds, then stop.");
  Serial.printf("IN1=%u, IN2=%u, IN3=%u, IN4=%u\n",
                Config::MOTOR_IN1, Config::MOTOR_IN2,
                Config::MOTOR_IN3, Config::MOTOR_IN4);
  Serial.println("ENA/ENB: bridged on module or connected to GPIO13/GPIO14");
  Serial.println("Starting in 2 seconds...");
  delay(2000);

  Serial.printf("RUN: IN1/IN3 PWM %u/255; IN2/IN4 LOW\n",
                Config::MOTOR_SPEED_DUTY);
  analogWrite(Config::MOTOR_IN1, Config::MOTOR_SPEED_DUTY);
  analogWrite(Config::MOTOR_IN2, 0);
  analogWrite(Config::MOTOR_IN3, Config::MOTOR_SPEED_DUTY);
  analogWrite(Config::MOTOR_IN4, 0);
  digitalWrite(Config::MOTOR_ENA, HIGH);
  digitalWrite(Config::MOTOR_ENB, HIGH);

  delay(MOTOR_RUN_MS);

  digitalWrite(Config::MOTOR_ENA, LOW);
  digitalWrite(Config::MOTOR_ENB, LOW);
  stopTestMotors();
  Serial.println("STOP: all motor inputs LOW. Press EN/RST to test again.");
}

void loop() {
  // Run once per reset. Motors remain stopped.
  delay(100);
}
