#pragma once
#include <Arduino.h>

enum class HybridBehavior : uint8_t { Hold, Search, Track };
void resetHybridControl();
void setHybridBehavior(HybridBehavior behavior);
bool hybridSearching();
bool hybridTracking();
const char* hybridStateName();
