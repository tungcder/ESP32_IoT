#pragma once
#include <Arduino.h>

enum class LedMode : uint8_t { Auto = 0, Manual = 1 };
enum class LedDirection : uint8_t { Stop, Forward, Backward, Left, Right };

void setupLeds();
void allLedsOff();
void allLedsOn();
void updateManualLeds();
void setLedMode(LedMode mode);
LedMode getLedMode();
void setAllLeds(bool on);
void showMovementLeds(LedDirection direction);
