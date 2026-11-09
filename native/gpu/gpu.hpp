// Host API of the CUDA evaluator (kernel.cu).
#pragma once
#include "space.hpp"
#include <cstdint>
#include <vector>

namespace gs {
struct GpuCtx;
GpuCtx* gpu_open(unsigned int cap);
void gpu_close(GpuCtx* c);
void gpu_load(GpuCtx* c, const DTask& task, const std::vector<uint8_t>& inputs,
              const std::vector<uint8_t>& targets, const std::vector<DStep>& alpha);
// Prefix table: rows of plen alphabet indices; plen 0 turns it off.
void gpu_set_prefixes(GpuCtx* c, const std::vector<uint8_t>& table, int plen);
// Evaluates programs [start, start+count) of length depth; appends up to the
// context cap of solution words (idx | kind<<62) and returns the true count.
// With use_prefix, idx = prefix_row * A^(depth-plen) + suffix. With shared,
// [start, start+count) ranges over depth-1 prefixes (idx / A) instead, each
// thread trying all A last steps on its cached pair-0 state.
uint64_t gpu_run(GpuCtx* c, int depth, uint64_t start, uint64_t count, std::vector<uint64_t>& sols,
                 bool use_prefix = false, bool shared = false);
}
