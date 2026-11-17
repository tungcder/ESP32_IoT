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
  constexpr uint8_t MOTOR_SPEED_PERCENT = 50;        // tốc độ tiến/lùi
  constexpr uint8_t MOTOR_SPEED_DUTY = (255 * MOTOR_SPEED_PERCENT + 50) / 100;
  constexpr uint8_t MOTOR_TURN_SPEED_PERCENT = 80;   // quay tại chỗ Manual/Obstacle Auto
  constexpr uint8_t MOTOR_TURN_SPEED_DUTY = (255 * MOTOR_TURN_SPEED_PERCENT + 50) / 100;
  constexpr uint8_t AI_TURN_SPEED_PERCENT = 70;      // giới hạn quay riêng cho AI

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
  constexpr char WIFI_SSID[] = "Hung Dong 2006";
  constexpr char WIFI_PASSWORD[] = "44448888";
  constexpr unsigned long WIFI_CONNECT_TIMEOUT_MS = 15000;

  constexpr unsigned long COMMAND_TIMEOUT_MS = 500;
  constexpr int AI_STOP_DISTANCE_CM = 20;
  constexpr int AI_RESUME_DISTANCE_CM = 25;
  constexpr unsigned long AI_SENSOR_INTERVAL_MS = 70;
  constexpr unsigned long HYBRID_SERVO_SETTLE_MS = 300;
  constexpr int SAFE_DISTANCE_CM = 40;
  constexpr int AUTO_REVERSE_CM = 8;
  constexpr int AUTO_RETRY_REVERSE_CM = 12;
  // Timings were estimated at 50% PWM, NOT measured distances/angles.
  // Recalibrate the 90-degree turn timings for the current 80% turn PWM.
  // Changing speed/voltage requires calibration on the real car.
  constexpr unsigned long AUTO_REVERSE_MS_PER_CM = 50;
  constexpr unsigned long AUTO_LEFT_90_MS = 780;
  constexpr unsigned long AUTO_RIGHT_90_MS = 780;
  constexpr int NO_ECHO_DISTANCE_CM = 200;
}
