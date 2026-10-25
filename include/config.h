#pragma once
#include <Arduino.h>

// ESP32-WROOM-32 DevKit (CH340C chi la chip USB-UART).
// L298N: de jumper ENA/ENB neu muon chay toc do toi da co dinh.
namespace Config {
  // L298N direction pins
  constexpr uint8_t MOTOR_IN1 = 26;
  constexpr uint8_t MOTOR_IN2 = 25;
  constexpr uint8_t MOTOR_IN3 = 33;
  constexpr uint8_t MOTOR_IN4 = 32;

  // HC-SR04
  constexpr uint8_t TRIG_PIN = 16;
  constexpr uint8_t ECHO_PIN = 17;

  // SG90 signal
  constexpr uint8_t SERVO_PIN = 21;

  // LEDs
  constexpr uint8_t LED_FRONT_LEFT  = 18;
  constexpr uint8_t LED_FRONT_RIGHT = 19;
  constexpr uint8_t LED_REAR_LEFT   = 22;
  constexpr uint8_t LED_REAR_RIGHT  = 23;

  constexpr char WIFI_SSID[] = "ESP32_CAR";
  constexpr char WIFI_PASSWORD[] = "12345678";

  constexpr unsigned long COMMAND_TIMEOUT_MS = 500;
  constexpr int SAFE_DISTANCE_CM = 25;
  constexpr int NO_ECHO_DISTANCE_CM = 200;
}
