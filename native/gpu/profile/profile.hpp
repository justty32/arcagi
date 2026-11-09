// Host API of the GPU near-miss profiler (profile_kernel.cu): scores every
// program of the gpusearch space by how close it gets to the train outputs.
#pragma once
#include "../space.hpp"
#include <cstdint>
#include <vector>

namespace gs {
// One kept program: idx = prefix_idx * A + last step (gpusearch encoding),
// q / rq = colormapped / raw score quantised to 0..65535.
struct ProfHit { unsigned long long idx; uint32_t q, rq; };
struct ProfCounters { uint64_t valid = 0, fail = 0, perfect = 0; };
constexpr int PROF_BINS = 1024;  // histogram bin = q >> 6

struct ProfCtx;
ProfCtx* prof_open(unsigned int cap);
void prof_close(ProfCtx* c);
void prof_load(ProfCtx* c, const DTask& task, const std::vector<uint8_t>& inputs,
               const std::vector<uint8_t>& targets, const std::vector<DStep>& alpha);
void prof_set_prefixes(ProfCtx* c, const std::vector<uint8_t>& table, int plen);
// Runs `count` depth-1 prefix threads starting at `start` (each tries all A
// last steps). Overwrites hits (up to cap, q >= thr_q), hist[PROF_BINS] and
// counters with this launch only; returns the true number of hits.
uint64_t prof_run(ProfCtx* c, int depth, uint64_t start, uint64_t count, bool use_prefix, uint32_t thr_q,
                  std::vector<ProfHit>& hits, std::vector<uint64_t>& hist, ProfCounters& ctr);
}
