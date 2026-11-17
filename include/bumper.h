#pragma once

#include <Arduino.h>

// Khoi tao 2 cong tac hanh trinh
void setupBumpers();

// Doc va chong doi tin hieu
void updateBumpers();

// Bit 0: bumper trai
// Bit 1: bumper phai
// 0 = khong va cham
// 1 = trai
// 2 = phai
// 3 = ca hai
uint8_t bumperMask();

// Kiem tra tung cong tac
bool bumperLeftPressed();
bool bumperRightPressed();

// True neu co it nhat 1 cong tac bi nhan
bool bumperBlocksForward();

// Xu ly va cham:
// Dung -> Lui -> Re -> Cho nha cong tac
// Tra ve true khi dang xu ly va cham
bool handleBumperCollision();

// Kiem tra robot dang xu ly va cham
bool bumperIsRecovering();
