#include <Arduino.h>
#include "config.h"
#include "drive_mode.h"
#include "motor_control.h"
#include "ultrasonic.h"
#include "servo_scan.h"
#include "obstacle_avoid.h"

namespace {
  enum class State : uint8_t {
    CheckFront, Reverse, StopBeforeScan,
    PointRight, CenterAfterRight,
    PointLeft, CenterAfterLeft,
    Turn, FinishTurn
  };

  // ---- Thong so doc cam bien (chinh lai cho hop voi cam bien cua ban) ----
  constexpr int  MIN_VALID_CM = 2;     // nho hon -> coi la doc loi
  constexpr int  MAX_VALID_CM = 200;   // lon hon (hoac timeout) -> coi la "khong co echo"
  constexpr int  NO_ECHO      = -1;

  // ---- Quet hinh quat phia truoc khi dang chay ----
  // slot 0 = giua (90), slot 1 = lech phai (60), slot 2 = lech trai (120)
  constexpr int  FRONT_ANGLE[3]   = {90, 60, 120};
  constexpr uint8_t FRONT_SEQ[]   = {0, 1, 0, 2};  // kiem tra giua 2 lan moi vong
  constexpr uint8_t FRONT_SEQ_LEN = sizeof(FRONT_SEQ) / sizeof(FRONT_SEQ[0]);
  constexpr unsigned long SERVO_SETTLE_MS = 120;
  constexpr unsigned long NEAR_MEMORY_MS  = 1000;  // nho gia tri "gan" truoc khi mat echo

  // ---- Thong so quay ----
  constexpr unsigned long TURN_BASE_MS = 400;
  constexpr unsigned long TURN_STEP_MS = 150;   // moi lan gap vat can lien tiep quay them
  constexpr unsigned long U_TURN_MS    = 900;   // ca hai ben deu bi chan -> quay dau
  constexpr unsigned long STREAK_WINDOW_MS = 2500;

  State state = State::CheckFront;
  unsigned long stateStarted = 0;
  unsigned long lastFrontCheck = 0;

  int rightDistance = 0;
  int leftDistance = 0;
  bool turnToRight = true;

  uint8_t frontStep = 0;
  bool frontAngleSet = false;
  int lastValid[3] = {NO_ECHO, NO_ECHO, NO_ECHO};
  unsigned long lastValidTime[3] = {0, 0, 0};

  unsigned long turnDurationMs = TURN_BASE_MS;
  uint8_t avoidStreak = 0;
  unsigned long lastAvoidEnd = 0;

  void enterState(State next) {
    state = next;
    stateStarted = millis();
  }

  bool elapsed(unsigned long ms) {
    return (unsigned long)(millis() - stateStarted) >= ms;
  }

  void resetFrontScan() {
    frontStep = 0;
    frontAngleSet = false;
    for (int i = 0; i < 3; i++) {
      lastValid[i] = NO_ECHO;
      lastValidTime[i] = 0;
    }
  }

  // Doc 3 lan, lay trung vi de loai nhieu. Tra NO_ECHO neu khong co echo hop le.
  int readDistanceCm() {
    int s[3];
    for (int i = 0; i < 3; i++) {
      s[i] = getDistanceCm();
      delay(8);
    }
    if (s[0] > s[1]) { int t = s[0]; s[0] = s[1]; s[1] = t; }
    if (s[1] > s[2]) { int t = s[1]; s[1] = s[2]; s[2] = t; }
    if (s[0] > s[1]) { int t = s[0]; s[0] = s[1]; s[1] = t; }
    int median = s[1];
    if (median < MIN_VALID_CM || median > MAX_VALID_CM) return NO_ECHO;
    return median;
  }

  // Phat hien vat can phia truoc tai mot slot goc.
  bool isFrontBlocked(uint8_t slot, int d) {
    // Goc lech: tia chieu xien nen khoang cach do duoc dai hon thuc te -> nang nguong.
    int threshold = (slot == 0) ? Config::SAFE_DISTANCE_CM
                                : (Config::SAFE_DISTANCE_CM * 13) / 10;

    if (d != NO_ECHO) {
      lastValid[slot] = d;
      lastValidTime[slot] = millis();
      return d <= threshold;
    }

    // Mat echo: neu ngay truoc do con o gan thi nhieu kha nang la be mat
    // nghieng da phan xa tia di cho khac -> coi nhu co vat can.
    if (lastValid[slot] != NO_ECHO &&
        lastValid[slot] <= Config::SAFE_DISTANCE_CM * 2 &&
        (unsigned long)(millis() - lastValidTime[slot]) < NEAR_MEMORY_MS) {
      return true;
    }
    return false;
  }
}

void setupObstacleAvoidance() {
  setServoAngle(90);
  state = State::CheckFront;
  stateStarted = millis();
  lastFrontCheck = 0;
  avoidStreak = 0;
  lastAvoidEnd = 0;
  resetFrontScan();
}

void updateObstacleAvoidance() {
  if (getDriveMode() != DriveMode::Auto) return;

  switch (state) {
    case State::CheckFront: {
      uint8_t slot = FRONT_SEQ[frontStep];

      // Buoc 1: xoay servo toi goc can kiem tra, doi servo on dinh
      if (!frontAngleSet) {
        setServoAngle(FRONT_ANGLE[slot]);
        frontAngleSet = true;
        lastFrontCheck = millis();
        return;
      }
      if ((unsigned long)(millis() - lastFrontCheck) < SERVO_SETTLE_MS) return;

      // Buoc 2: doc cam bien
      int d = readDistanceCm();
      Serial.printf("Front[%d deg]: %d cm\n", FRONT_ANGLE[slot], d);
      if (d == NO_ECHO) {
        stopCar();
        frontAngleSet = false;
        return;
      }
      bool blocked = isFrontBlocked(slot, d);

      frontAngleSet = false;
      frontStep = (frontStep + 1) % FRONT_SEQ_LEN;

      if (!blocked) {
        moveForward();
      } else {
        stopCar();
        resetFrontScan();
        enterState(State::Reverse);
        moveBackward();
      }
      break;
    }

    case State::Reverse:
      if (elapsed(300)) {
        stopCar();
        enterState(State::StopBeforeScan);
      }
      break;

    case State::StopBeforeScan:
      if (elapsed(100)) {
        setServoAngle(10); // goc phia ben phai
        enterState(State::PointRight);
      }
      break;

    case State::PointRight:
      if (elapsed(300)) {
        int d = readDistanceCm();
        // Khong co echo o ben canh: khong chac an toan -> coi nhu bi chan
        rightDistance = (d == NO_ECHO) ? 0 : d;
        Serial.printf("Right: %d cm (raw %d)\n", rightDistance, d);
        setServoAngle(90);
        enterState(State::CenterAfterRight);
      }
      break;

    case State::CenterAfterRight:
      if (elapsed(200)) {
        setServoAngle(170); // goc phia ben trai
        enterState(State::PointLeft);
      }
      break;

    case State::PointLeft:
      if (elapsed(300)) {
        int d = readDistanceCm();
        leftDistance = (d == NO_ECHO) ? 0 : d;
        Serial.printf("Left: %d cm (raw %d)\n", leftDistance, d);
        setServoAngle(90);
        enterState(State::CenterAfterLeft);
      }
      break;

    case State::CenterAfterLeft:
      if (elapsed(200)) {
        bool bothBlocked = rightDistance <= Config::SAFE_DISTANCE_CM &&
                           leftDistance <= Config::SAFE_DISTANCE_CM;

        if (bothBlocked) {
          // Ca hai ben deu bi chan: quay dau thay vi dung yen
          Serial.println("Both sides blocked; U-turn.");
          turnToRight = true;
          turnDurationMs = U_TURN_MS;
          turnRight();
        } else {
          // Gap vat can lien tiep trong thoi gian ngan -> quay nhieu hon
          if ((unsigned long)(millis() - lastAvoidEnd) < STREAK_WINDOW_MS) {
            if (avoidStreak < 3) avoidStreak++;
          } else {
            avoidStreak = 0;
          }
          turnDurationMs = TURN_BASE_MS + avoidStreak * TURN_STEP_MS;

          turnToRight = rightDistance > leftDistance;
          if (turnToRight) {
            Serial.println("Turning right");
            turnRight();
          } else {
            Serial.println("Turning left");
            turnLeft();
          }
        }
        enterState(State::Turn);
      }
      break;

    case State::Turn:
      if (elapsed(turnDurationMs)) {
        stopCar();
        enterState(State::FinishTurn);
      }
      break;

    case State::FinishTurn:
      if (elapsed(100)) {
        lastAvoidEnd = millis();
        resetFrontScan();
        setServoAngle(90);
        enterState(State::CheckFront);
      }
      break;
  }
}
