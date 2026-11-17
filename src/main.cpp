#include <Arduino.h>
#include "motor_control.h"
#include "led_control.h"
#include "wifi_control.h"
#include "safety.h"
#include "ultrasonic.h"
#include "servo_scan.h"
#include "obstacle_avoid.h"
#include "drive_mode.h"
#include "ai_control.h"
#include "bumper.h"

void setup() {
  Serial.begin(115200);
  delay(200);
   
  setupLeds();
  setupMotors();
  setupUltrasonic();
  setupServoScan();
  setupObstacleAvoidance();
  setDriveMode(DriveMode::Manual);
  resetCommandTimer();

  setupBumpers();

  Serial.println();
  Serial.println("ESP32 robot: Wi-Fi manual control ready");
  setupWiFiAndServer();
}

void loop() {
  handleWebServer();
 
  bool bumperBusy = handleBumperCollision();

  if (bumperBusy) {
      return;
  }

  checkCommandTimeout();
  updateAIControl();
  updateObstacleAvoidance();
}