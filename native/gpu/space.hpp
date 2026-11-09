// Brute-force program space shared by the CUDA prototype and its CPU twin.
// A program is any sequence (length 1..depth) over a per-task alphabet of
// fully parameterised steps; after the last step a program is a solution if
// the train outputs match exactly, or (same shapes) a terminal colormap
// learner fits, exactly as arcsearch's evaluate() decides.
#pragma once
#include <cstdint>

namespace gs {
enum Op : uint8_t {
    FLIP_LR, FLIP_UD, TRANSPOSE, ROT90, ROT180, ROT270, ANTI_TRANSPOSE,  // D4 order of prims.hpp
    UPSCALE, TILE, DOWNSCALE,  // a=fy b=fx
    MIRROR_TILE,               // a: 0 lr, 1 ud, 2 quad
    CROP_BBOX,
    GRAVITY,                   // a: 0 down, 1 left, 2 up, 3 right
    FILL_ENCLOSED,
    SPLIT_OVERLAY,             // a: 0 h, 1 v; b: 0 and, 1 or, 2 xor, 3 nor, 4 left
    SELF_TILE,                 // a: 0 pos, 1 neg
    COLORMAP,                  // [[a,b]]
};
struct DStep { uint8_t op, a, b, pad; };

constexpr int MAX_PAIRS = 16;  // train + test inputs
constexpr int CELLS = 900;

// Device-side task image: inputs (train then test) and train targets.
struct DTask {
    int ntrain, nall;
    int ih[MAX_PAIRS], iw[MAX_PAIRS], ioff[MAX_PAIRS];
    int th[MAX_PAIRS], tw[MAX_PAIRS], toff[MAX_PAIRS];
};
enum Kind : uint8_t { EXACT = 1, CMAP = 2 };
}
