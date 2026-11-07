#pragma once
#include <Arduino.h>

enum class LedDirection : uint8_t { Stop, Forward, Backward, Left, Right };

void setupLeds();
void showMovementLeds(LedDirection direction);
