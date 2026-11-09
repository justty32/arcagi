// Host API for GPU genetic program search over the N2 alphabet.
#pragma once
#include "../gpu.hpp"
#include <utility>

namespace gs {
constexpr int GP_LMAX = 10;
struct GpCfg {
    int pop=65536, island=256, lmax=10, linit=6, tourn=4, immigrants=8, migrate=20;
    float pcx=0.5f, pmut=0.9f, len_pen=0.002f;
    uint64_t seed=1;
    bool random=false;
};
struct GpCtx;
GpCtx* gp_open(const GpCfg& cfg);
void gp_close(GpCtx*);
void gp_load(GpCtx*, const DTask&, const std::vector<uint8_t>& inputs,
             const std::vector<uint8_t>& targets, const std::vector<DStep>& alpha);
float gp_eval(GpCtx*, std::vector<std::pair<uint32_t,uint8_t>>& hits, uint32_t& best_idx);
void gp_breed(GpCtx*, uint32_t gen);
void gp_genome(GpCtx*, uint32_t idx, std::vector<uint8_t>& genes);
uint64_t gp_brute(GpCtx*, int depth);
}
