#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>

#include "config.h"
#include "led_control.h"
#include "motor_control.h"
#include "safety.h"
#include "drive_mode.h"
#include "obstacle_avoid.h"
#include "web_page.h"
#include "wifi_control.h"
#include "robot_status.h"
#include "servo_scan.h"

namespace {
  WebServer server(80);
  bool wifiConnected = false;
  unsigned long lastWiFiStatusMs = 0;
  constexpr unsigned long WIFI_STATUS_INTERVAL_MS = 5000;

  void onWiFiDisconnected(WiFiEvent_t, WiFiEventInfo_t info) {
    const uint8_t reason = info.wifi_sta_disconnected.reason;
    Serial.printf("\n[Wi-Fi] Disconnected | reason: %u\n", reason);
    switch (reason) {
      case WIFI_REASON_NO_AP_FOUND:
        Serial.println("[Wi-Fi] Network not found. Check SSID, hotspot and 2.4 GHz.");
        break;
      case WIFI_REASON_AUTH_FAIL:
      case WIFI_REASON_HANDSHAKE_TIMEOUT:
      case WIFI_REASON_4WAY_HANDSHAKE_TIMEOUT:
        Serial.println("[Wi-Fi] Authentication failed or timed out. Check password, signal and router/hotspot settings.");
        break;
      default:
        break;
    }
    // The Wi-Fi library handles reconnection; do not start another attempt here.
  }

  void printWiFiStatus() {
    const wl_status_t status = WiFi.status();
    Serial.print("[Wi-Fi] ");
    if (status == WL_CONNECTED) {
      Serial.print("CONNECTED | IP: ");
      Serial.print(WiFi.localIP());
      Serial.print(" | Signal: ");
      Serial.print(WiFi.RSSI());
      Serial.println(" dBm");
      return;
    }

    Serial.print("NOT CONNECTED | ");
    switch (status) {
      case WL_NO_SSID_AVAIL:
        Serial.println("Network not found. Check hotspot and SSID.");
        break;
      case WL_CONNECT_FAILED:
        Serial.println("Connection failed. Check password and router/hotspot settings.");
        break;
      default:
        Serial.println("Waiting for Wi-Fi connection...");
        break;
    }
  }

  void printWiFiConnection() {
    Serial.print("Connected to Wi-Fi: ");
    Serial.println(Config::WIFI_SSID);
    Serial.print("Open on laptop: http://");
    Serial.println(WiFi.localIP());
  }

  void handleRoot() {
    server.sendHeader("Cache-Control", "no-cache, no-store, must-revalidate");
    server.sendHeader("Pragma", "no-cache");
    server.sendHeader("Expires", "0");
    server.send(200, "text/html; charset=UTF-8", webpage);
  }

  void handleForward() {
    if (getDriveMode() != DriveMode::Manual) { server.send(409, "text/plain", "AUTO mode active"); return; }
    moveForward();
    resetCommandTimer();
    server.send(200, "text/plain", "FORWARD");
  }

  void handleBackward() {
    if (getDriveMode() != DriveMode::Manual) { server.send(409, "text/plain", "AUTO mode active"); return; }
    moveBackward();
    resetCommandTimer();
    server.send(200, "text/plain", "BACKWARD");
  }

  void handleLeft() {
    if (getDriveMode() != DriveMode::Manual) { server.send(409, "text/plain", "AUTO mode active"); return; }
    turnLeft();
    resetCommandTimer();
    server.send(200, "text/plain", "LEFT");
  }

  void handleRight() {
    if (getDriveMode() != DriveMode::Manual) { server.send(409, "text/plain", "AUTO mode active"); return; }
    turnRight();
    resetCommandTimer();
    server.send(200, "text/plain", "RIGHT");
  }

  void handleStop() {
    if (getDriveMode() != DriveMode::Manual) { server.send(409, "text/plain", "AUTO mode active"); return; }
    stopCar();
    resetCommandTimer();
    server.send(200, "text/plain", "STOP");
  }

  void handleDriveAuto() {
    stopCar();
    setupObstacleAvoidance();
    setDriveMode(DriveMode::Auto);
    recordRobotEvent("Obstacle Auto selected");
    resetCommandTimer();
    server.send(200, "text/plain", "DRIVE AUTO");
  }

  void handleDriveManual() {
    stopCar();
    setDriveMode(DriveMode::Manual);
    setServoAngle(90);
    recordRobotEvent("Wi-Fi Manual selected");
    resetCommandTimer();
    server.send(200, "text/plain", "DRIVE MANUAL");
  }

  void handleStatus() {
    server.sendHeader("Cache-Control", "no-store");
    server.send(200, "application/json; charset=UTF-8", robotStatusJson());
  }
}

void setupWiFiAndServer() {
  WiFi.onEvent(onWiFiDisconnected, ARDUINO_EVENT_WIFI_STA_DISCONNECTED);
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  WiFi.setAutoReconnect(true);

  Serial.println();
  Serial.println("==============================");
  Serial.println("ESP32 WIFI ROBOT");
  Serial.println("==============================");
  Serial.print("Connecting to Wi-Fi: ");
  Serial.println(Config::WIFI_SSID);
  Serial.println("Laptop must connect to the same network. Wi-Fi must support 2.4 GHz.");

  WiFi.begin(Config::WIFI_SSID, Config::WIFI_PASSWORD);
  const unsigned long connectStartedMs = millis();
  while (WiFi.status() != WL_CONNECTED &&
         (unsigned long)(millis() - connectStartedMs) < Config::WIFI_CONNECT_TIMEOUT_MS) {
    delay(250);
    Serial.print('.');
  }
  Serial.println();
  wifiConnected = WiFi.status() == WL_CONNECTED;
  if (wifiConnected) {
    printWiFiConnection();
  } else {
    Serial.println("Wi-Fi not connected yet. Check SSID, password, 2.4 GHz and disconnect reason logs.");
  }
  printWiFiStatus();
  lastWiFiStatusMs = millis();

  server.on("/", HTTP_GET, handleRoot);
  server.on("/forward", HTTP_GET, handleForward);
  server.on("/backward", HTTP_GET, handleBackward);
  server.on("/left", HTTP_GET, handleLeft);
  server.on("/right", HTTP_GET, handleRight);
  server.on("/stop", HTTP_GET, handleStop);
  server.on("/driveauto", HTTP_GET, handleDriveAuto);
  server.on("/drivemanual", HTTP_GET, handleDriveManual);
  server.on("/status", HTTP_GET, handleStatus);

  server.begin();
  Serial.println("Web server started on port 80; accessible when Wi-Fi is connected.");
}

void handleWebServer() {
  // Report periodically without blocking motor control or obstacle avoidance.
  if ((unsigned long)(millis() - lastWiFiStatusMs) >= WIFI_STATUS_INTERVAL_MS) {
    lastWiFiStatusMs = millis();
    printWiFiStatus();
  }

  if (WiFi.status() != WL_CONNECTED) {
    if (wifiConnected) {
      wifiConnected = false;
      Serial.println("Wi-Fi disconnected. Automatic reconnection is enabled.");
    }
    // setAutoReconnect handles retries after failure events. Calling reconnect()
    // on a timer can overlap an active connection and cause 'sta is connecting'.
    return;
  }

  if (!wifiConnected) {
    wifiConnected = true;
    printWiFiConnection();
  }
  server.handleClient();
}
