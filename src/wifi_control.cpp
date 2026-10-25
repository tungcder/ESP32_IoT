#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>

#include "config.h"
#include "led_control.h"
#include "motor_control.h"
#include "safety.h"
#include "drive_mode.h"
#include "web_page.h"
#include "wifi_control.h"

namespace {
  WebServer server(80);

  void handleRoot() {
    server.sendHeader("Cache-Control", "no-cache, no-store, must-revalidate");
    server.sendHeader("Pragma", "no-cache");
    server.sendHeader("Expires", "0");
    server.send(200, "text/html; charset=UTF-8", webpage);
  }

  void handleForward() {
    setDriveMode(DriveMode::Manual);
    moveForward();
    resetCommandTimer();
    server.send(200, "text/plain", "FORWARD");
  }

  void handleBackward() {
    setDriveMode(DriveMode::Manual);
    moveBackward();
    resetCommandTimer();
    server.send(200, "text/plain", "BACKWARD");
  }

  void handleLeft() {
    setDriveMode(DriveMode::Manual);
    turnLeft();
    resetCommandTimer();
    server.send(200, "text/plain", "LEFT");
  }

  void handleRight() {
    setDriveMode(DriveMode::Manual);
    turnRight();
    resetCommandTimer();
    server.send(200, "text/plain", "RIGHT");
  }

  void handleStop() {
    setDriveMode(DriveMode::Manual);
    stopCar();
    resetCommandTimer();
    server.send(200, "text/plain", "STOP");
  }

  void handleDriveAuto() {
    stopCar();
    setDriveMode(DriveMode::Auto);
    resetCommandTimer();
    server.send(200, "text/plain", "DRIVE AUTO");
  }

  void handleDriveManual() {
    stopCar();
    setDriveMode(DriveMode::Manual);
    resetCommandTimer();
    server.send(200, "text/plain", "DRIVE MANUAL");
  }

  void handleLedAuto() {
    setLedMode(LedMode::Auto);
    server.send(200, "text/plain", "AUTO");
  }

  void handleLedManual() {
    setLedMode(LedMode::Manual);
    server.send(200, "text/plain", "MANUAL");
  }

  void handleLedOn() {
    setAllLeds(true);
    server.send(200, "text/plain", "LED ON");
  }

  void handleLedOff() {
    setAllLeds(false);
    server.send(200, "text/plain", "LED OFF");
  }
}

void setupWiFiAndServer() {
  WiFi.mode(WIFI_AP);
  WiFi.setSleep(false);

  const bool apStarted = WiFi.softAP(Config::WIFI_SSID, Config::WIFI_PASSWORD);
  Serial.println();
  Serial.println("==============================");
  Serial.println("ESP32 WIFI ROBOT");
  Serial.println("==============================");
  Serial.print("WiFi AP started: ");
  Serial.println(apStarted ? "YES" : "NO");
  Serial.print("WiFi Name: ");
  Serial.println(Config::WIFI_SSID);
  Serial.print("IP Address: ");
  Serial.println(WiFi.softAPIP());

  server.on("/", HTTP_GET, handleRoot);
  server.on("/forward", HTTP_GET, handleForward);
  server.on("/backward", HTTP_GET, handleBackward);
  server.on("/left", HTTP_GET, handleLeft);
  server.on("/right", HTTP_GET, handleRight);
  server.on("/stop", HTTP_GET, handleStop);
  server.on("/driveauto", HTTP_GET, handleDriveAuto);
  server.on("/drivemanual", HTTP_GET, handleDriveManual);

  server.on("/ledauto", HTTP_GET, handleLedAuto);
  server.on("/ledmanual", HTTP_GET, handleLedManual);
  server.on("/ledon", HTTP_GET, handleLedOn);
  server.on("/ledoff", HTTP_GET, handleLedOff);

  server.begin();
  Serial.println("Web server started!");
}

void handleWebServer() {
  server.handleClient();
}
