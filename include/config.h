#pragma once
#include <Arduino.h>

// ESP32-WROOM-32 DevKit (CH340C chi la chip USB-UART).
// ENA/ENB can be bridged on the L298N or driven by ESP32 GPIO13/GPIO14.
namespace Config {
  // L298N enable and direction pins
  constexpr uint8_t MOTOR_ENA = 13;
  constexpr uint8_t MOTOR_ENB = 14;
  constexpr uint8_t MOTOR_IN1 = 27;
  constexpr uint8_t MOTOR_IN2 = 26;
  constexpr uint8_t MOTOR_IN3 = 25;
  constexpr uint8_t MOTOR_IN4 = 33;
  // 8-bit PWM duty: 153/255 is about 60% speed command.
  constexpr uint8_t MOTOR_SPEED_DUTY = 153;

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

  // Connect to the same 2.4 GHz Wi-Fi network as the laptop.
  constexpr char WIFI_SSID[] = "hung";
  constexpr char WIFI_PASSWORD[] = "12345678";
  constexpr unsigned long WIFI_CONNECT_TIMEOUT_MS = 15000;

  constexpr unsigned long COMMAND_TIMEOUT_MS = 500;
  constexpr int SAFE_DISTANCE_CM = 25;
  constexpr int NO_ECHO_DISTANCE_CM = 200;
}
