#include <Arduino.h>
#include "config.h"
#include "ultrasonic.h"

void setupUltrasonic() {
  pinMode(Config::TRIG_PIN, OUTPUT);
  pinMode(Config::ECHO_PIN, INPUT);
  digitalWrite(Config::TRIG_PIN, LOW);
}

int getDistanceCm() {
  digitalWrite(Config::TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(Config::TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(Config::TRIG_PIN, LOW);

  // timeout 25 ms, tranh pulseIn cho doi qua lau khi khong co Echo
  unsigned long duration = pulseIn(Config::ECHO_PIN, HIGH, 25000UL);
  // Fail-safe: neu khong nhan duoc Echo, xem nhu khoang cach khong an toan.
  if (duration == 0) return 0;
  return static_cast<int>(duration * 0.0343f / 2.0f);
}
