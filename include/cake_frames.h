// Aggregates the cake animation frames (assets/cake-1..4.png)
#pragma once

#include "cake_frame_1.h"
#include "cake_frame_2.h"
#include "cake_frame_3.h"
#include "cake_frame_4.h"

constexpr int16_t CAKE_W = CAKE_FRAME_1_W;
constexpr int16_t CAKE_H = CAKE_FRAME_1_H;
constexpr uint8_t CAKE_FRAME_COUNT = 4;

const uint16_t *const CAKE_FRAMES[CAKE_FRAME_COUNT] = {
    cake_frame_1,
    cake_frame_2,
    cake_frame_3,
    cake_frame_4,
};
