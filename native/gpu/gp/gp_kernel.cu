// GP shares N2's primitives, task constants, verdict and brute-force evaluator.
#include "../kernel.cu"
#include "gp.hpp"
#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>
#include <filesystem>

namespace gs {
namespace {
constexpr unsigned HIT_CAP = 4096;
constexpr int BLOCK = 128;

__device__ uint64_t splitmix64(uint64_t x) {
    x += 0x9e3779b97f4a7c15ull;
    x = (x ^ (x >> 30)) * 0xbf58476d1ce4e5b9ull;
    x = (x ^ (x >> 27)) * 0x94d049bb133111ebull;
    return x ^ (x >> 31);
}
struct Rng {
    uint64_t key, counter = 0;
    __device__ Rng(uint64_t seed, uint32_t gen, uint32_t i)
        : key(seed ^ uint64_t(gen) * 0x9e3779b97f4a7c15ull ^ uint64_t(i) * 0xd1b54a32d192ed03ull) {}
    __device__ uint64_t next() { return splitmix64(key ^ counter++); }
    __device__ int pick(int n) { return int(next() % uint64_t(n)); }
    __device__ bool chance(float p) { return float(next() >> 40) * (1.0f / 16777216.0f) < p; }
};

__device__ void random_genome(uint8_t* dst, uint8_t& len, GpCfg cfg, int A, Rng& rng) {
    len = uint8_t(1 + rng.pick(cfg.linit));
    for (int k = 0; k < len; ++k) dst[k] = uint8_t(rng.pick(A));
}

__global__ void k_init(uint8_t* lens, uint8_t* genes, GpCfg cfg, int A) {
    uint32_t i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i >= uint32_t(cfg.pop)) return;
    Rng rng(cfg.seed, 0, i);
    random_genome(genes + size_t(i) * GP_LMAX, lens[i], cfg, A, rng);
}

__global__ void k_eval(const uint8_t* lens, const uint8_t* genes, float* fit, GpCfg cfg,
                       const uint8_t* inputs, const uint8_t* targets,
                       unsigned long long* sols, unsigned int* nsol) {
    uint32_t i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i >= uint32_t(cfg.pop)) return;
    int len = lens[i];
    DStep prog[GP_LMAX];
    for (int k = 0; k < len; ++k) prog[k] = c_alpha[genes[size_t(i) * GP_LMAX + k]];
    uint8_t ba[CELLS], bb[CELLS], bt[CELLS];
    uint16_t st[CELLS], cnt[11][10] = {};
    float cell = 0, shape = 0;
    int total = 0;
    bool ok = true;
    Verdict v;
    int nfit = 0;
    for (int p = 0; p < c_task.ntrain; ++p) {
        if (p == cfg.holdout) continue;  // hidden pair: checked on host only
        ++nfit;
        int th = c_task.th[p], tw = c_task.tw[p], h, w;
        total += th * tw;
        const uint8_t* cur = run_steps(prog, len, inputs, p, ba, bb, bt, st, h, w);
        if (!cur) { ok = false; continue; }
        shape += 0.5f * (h == th) + 0.5f * (w == tw);
        const uint8_t* tg = targets + c_task.toff[p];
        int same = 0;
        for (int y = 0; y < h && y < th; ++y)
            for (int x = 0; x < w && x < tw; ++x) same += cur[y * w + x] == tg[y * tw + x];
        cell += float(same) / (th * tw);
        if (h == th && w == tw)
            for (int k = 0; k < h * w; ++k) ++cnt[cur[k]][tg[k]];
        if (!v.fold(p, cur, h, w, targets)) ok = false;
    }
    int mapped = 0;
    for (int s = 0; s < 11; ++s) {
        int best = 0;
        for (int g = 0; g < 10; ++g) best = max(best, int(cnt[s][g]));
        mapped += best;
    }
    fit[i] = 0.5f * cell / nfit + 0.35f * mapped / total
           + 0.15f * shape / nfit - cfg.len_pen * len;
    if (!ok) return;
    for (int p = c_task.ntrain; p < c_task.nall; ++p) {
        int h, w;
        const uint8_t* cur = run_steps(prog, len, inputs, p, ba, bb, bt, st, h, w);
        if (!cur || !v.fold(p, cur, h, w, targets)) return;
    }
    if (auto kind = v.kind()) emit(i, kind, sols, HIT_CAP, nsol);
}

__device__ bool better(uint32_t a, uint32_t b, const float* fit) {
    return fit[a] > fit[b] || (fit[a] == fit[b] && a < b);
}
__global__ void k_island_best(const float* fit, uint32_t* ibest, int island) {
    __shared__ uint32_t best[BLOCK];
    int tid = threadIdx.x;
    uint32_t base = blockIdx.x * island, winner = base;
    for (int j = tid; j < island; j += BLOCK)
        if (better(base + j, winner, fit)) winner = base + j;
    best[tid] = winner;
    __syncthreads();
    for (int stride = BLOCK / 2; stride; stride /= 2) {
        if (tid < stride && better(best[tid + stride], best[tid], fit)) best[tid] = best[tid + stride];
        __syncthreads();
    }
    if (!tid) ibest[blockIdx.x] = best[0];
}

__device__ uint32_t tournament(int base, const float* fit, GpCfg cfg, Rng& rng) {
    uint32_t win = base + rng.pick(cfg.island);
    for (int k = 1; k < cfg.tourn; ++k) {
        uint32_t x = base + rng.pick(cfg.island);
        if (better(x, win, fit)) win = x;
    }
    return win;
}
__global__ void k_breed(const uint8_t* lens, const uint8_t* genes, uint8_t* next_lens,
                        uint8_t* next_genes, const float* fit, const uint32_t* ibest,
                        GpCfg cfg, int A, uint32_t gen) {
    uint32_t i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i >= uint32_t(cfg.pop)) return;
    int isl = i / cfg.island, j = i % cfg.island;
    uint8_t* dst = next_genes + size_t(i) * GP_LMAX;
    Rng rng(cfg.seed, gen, i);
    uint32_t parent;
    if (j == 0) parent = ibest[isl];
    else if (cfg.random) {
        random_genome(dst, next_lens[i], cfg, A, rng); return;
    } else if (j == 1 && gen % cfg.migrate == 0)
        parent = ibest[(isl + cfg.pop / cfg.island - 1) % (cfg.pop / cfg.island)];
    else if (j >= 2 && j < 2 + cfg.immigrants) {
        random_genome(dst, next_lens[i], cfg, A, rng); return;
    } else parent = tournament(isl * cfg.island, fit, cfg, rng);
    int len = lens[parent];
    const uint8_t* src = genes + size_t(parent) * GP_LMAX;
    for (int k = 0; k < len; ++k) dst[k] = src[k];
    // Elites and migrants are copied without crossover or mutation.
    if (j == 0 || (j == 1 && gen % cfg.migrate == 0)) { next_lens[i] = uint8_t(len); return; }
    if (rng.chance(cfg.pcx)) {
        uint32_t pb = tournament(isl * cfg.island, fit, cfg, rng);
        int lb = lens[pb], a = rng.pick(len + 1), b = rng.pick(lb + 1);
        int size = min(cfg.lmax, a + lb - b);
        if (size) {
            for (int k = a; k < size; ++k) dst[k] = genes[size_t(pb) * GP_LMAX + b + k - a];
            len = size;
        }
    }
    if (rng.chance(cfg.pmut)) {
        switch (rng.pick(4)) {
        case 0: dst[rng.pick(len)] = uint8_t(rng.pick(A)); break;
        case 1:
            if (len < cfg.lmax) {
                int at = rng.pick(len + 1);
                for (int k = len; k > at; --k) dst[k] = dst[k - 1];
                dst[at] = uint8_t(rng.pick(A)); ++len;
            }
            break;
        case 2:
            if (len > 1) {
                int at = rng.pick(len);
                for (int k = at; k + 1 < len; ++k) dst[k] = dst[k + 1];
                --len;
            }
            break;
        case 3:
            if (len > 1) {
                int at = rng.pick(len - 1);
                uint8_t tmp = dst[at]; dst[at] = dst[at + 1]; dst[at + 1] = tmp;
            }
            break;
        }
    }
    next_lens[i] = uint8_t(len);
}

void check_stop() {
    const char* home = std::getenv("HOME");
    if (home && std::filesystem::exists(std::filesystem::path(home) / "arcagi-STOP"))
        throw std::runtime_error("arcagi-STOP exists; stopped");
}
}

struct GpCtx {
    GpCfg cfg;
    GpuCtx* gpu = nullptr;
    uint8_t *lens[2]{}, *genes[2]{};
    float* fit = nullptr;
    uint32_t* ibest = nullptr;
    unsigned long long* sols = nullptr;
    unsigned int* nsol = nullptr;
    int current = 0;
    int ntrain = 0;
};

GpCtx* gp_open(const GpCfg& cfg) {
    check_stop();
    if (cfg.pop < 2 || cfg.island < 2 || cfg.pop % cfg.island || cfg.lmax < 1 || cfg.lmax > GP_LMAX
        || cfg.linit < 1 || cfg.linit > cfg.lmax || cfg.tourn < 1 || cfg.migrate < 1 || cfg.immigrants < 0
        || !std::isfinite(cfg.pcx) || cfg.pcx < 0 || cfg.pcx > 1
        || !std::isfinite(cfg.pmut) || cfg.pmut < 0 || cfg.pmut > 1
        || !std::isfinite(cfg.len_pen) || cfg.len_pen < 0)
        throw std::runtime_error("invalid GP configuration (pop must be divisible by island; 1 <= linit <= lmax <= 10)");
    // Bound population buffers to 256 MiB, leaving ample room for CUDA scratch.
    if (uint64_t(cfg.pop) * (2 * (GP_LMAX + 1) + sizeof(float) + sizeof(uint32_t)) > (1ull << 28))
        throw std::runtime_error("population exceeds GPU memory limit");
    auto* c = new GpCtx;
    c->cfg = cfg;
    c->gpu = gpu_open(1u << 16);
    for (int k = 0; k < 2; ++k) {
        CK(cudaMalloc(&c->lens[k], cfg.pop));
        CK(cudaMalloc(&c->genes[k], size_t(cfg.pop) * GP_LMAX));
    }
    CK(cudaMalloc(&c->fit, size_t(cfg.pop) * sizeof(float)));
    CK(cudaMalloc(&c->ibest, size_t(cfg.pop / cfg.island) * sizeof(uint32_t)));
    CK(cudaMalloc(&c->sols, HIT_CAP * sizeof(unsigned long long)));
    CK(cudaMalloc(&c->nsol, sizeof(unsigned int)));
    return c;
}
void gp_tune(GpCtx* c, int holdout, float len_pen) {
    if (holdout >= c->ntrain || c->ntrain < 2) holdout = -1;
    if (!std::isfinite(len_pen) || len_pen < 0) throw std::runtime_error("invalid length penalty");
    c->cfg.holdout = holdout;
    c->cfg.len_pen = len_pen;
}
void gp_close(GpCtx* c) {
    if (!c) return;
    for (int k = 0; k < 2; ++k) { cudaFree(c->lens[k]); cudaFree(c->genes[k]); }
    cudaFree(c->fit); cudaFree(c->ibest); cudaFree(c->sols); cudaFree(c->nsol);
    gpu_close(c->gpu);
    delete c;
}
void gp_load(GpCtx* c, const DTask& task, const std::vector<uint8_t>& inputs,
             const std::vector<uint8_t>& targets, const std::vector<DStep>& alpha) {
    check_stop();
    if (task.ntrain < 1 || task.nall < task.ntrain || task.nall > MAX_PAIRS || alpha.empty() || alpha.size() > 256)
        throw std::runtime_error("invalid GP task");
    gpu_load(c->gpu, task, inputs, targets, alpha);
    c->current = 0;
    c->ntrain = task.ntrain;
    c->cfg.holdout = -1;  // gp_tune re-enables per task
    k_init<<<(c->cfg.pop + BLOCK - 1) / BLOCK, BLOCK>>>(c->lens[0], c->genes[0], c->cfg, c->gpu->A);
    CK(cudaGetLastError());
    CK(cudaDeviceSynchronize());
}
float gp_eval(GpCtx* c, std::vector<std::pair<uint32_t,uint8_t>>& hits, uint32_t& best_idx) {
    check_stop();
    CK(cudaMemset(c->nsol, 0, sizeof(unsigned int)));
    k_eval<<<(c->cfg.pop + BLOCK - 1) / BLOCK, BLOCK>>>(c->lens[c->current], c->genes[c->current], c->fit,
        c->cfg, c->gpu->inputs, c->gpu->targets, c->sols, c->nsol);
    CK(cudaGetLastError());
    k_island_best<<<c->cfg.pop / c->cfg.island, BLOCK>>>(c->fit, c->ibest, c->cfg.island);
    CK(cudaGetLastError());
    unsigned int n;
    CK(cudaMemcpy(&n, c->nsol, sizeof(n), cudaMemcpyDeviceToHost));
    std::vector<unsigned long long> words(std::min(n, HIT_CAP));
    if (!words.empty()) CK(cudaMemcpy(words.data(), c->sols, words.size() * sizeof(words[0]), cudaMemcpyDeviceToHost));
    hits.clear();
    for (auto w : words) hits.emplace_back(uint32_t(w & ((1ull << 62) - 1)), uint8_t(w >> 62));
    std::vector<uint32_t> islands(c->cfg.pop / c->cfg.island);
    std::vector<float> fitness(c->cfg.pop);
    CK(cudaMemcpy(islands.data(), c->ibest, islands.size() * sizeof(uint32_t), cudaMemcpyDeviceToHost));
    CK(cudaMemcpy(fitness.data(), c->fit, fitness.size() * sizeof(float), cudaMemcpyDeviceToHost));
    best_idx = islands[0];
    for (auto idx : islands)
        if (fitness[idx] > fitness[best_idx] || (fitness[idx] == fitness[best_idx] && idx < best_idx)) best_idx = idx;
    return fitness[best_idx];
}
void gp_breed(GpCtx* c, uint32_t gen) {
    check_stop();
    k_breed<<<(c->cfg.pop + BLOCK - 1) / BLOCK, BLOCK>>>(c->lens[c->current], c->genes[c->current],
        c->lens[c->current ^ 1], c->genes[c->current ^ 1], c->fit, c->ibest, c->cfg, c->gpu->A, gen);
    CK(cudaGetLastError());
    c->current ^= 1;
}
void gp_genome(GpCtx* c, uint32_t idx, std::vector<uint8_t>& genes) {
    if (idx >= uint32_t(c->cfg.pop)) throw std::runtime_error("genome index out of bounds");
    uint8_t len;
    CK(cudaMemcpy(&len, c->lens[c->current] + idx, sizeof(len), cudaMemcpyDeviceToHost));
    genes.resize(len);
    CK(cudaMemcpy(genes.data(), c->genes[c->current] + size_t(idx) * GP_LMAX, len, cudaMemcpyDeviceToHost));
}
uint64_t gp_brute(GpCtx* c, int depth) {
    if (depth < 1 || depth > 8) throw std::runtime_error("N2 brute depth must be 1..8");
    uint64_t total = 1;
    for (int k = 0; k < depth; ++k) {
        if (total > std::numeric_limits<uint64_t>::max() / c->gpu->A)
            throw std::runtime_error("brute space overflow");
        total *= c->gpu->A;
    }
    // N2 shared mode counts prefixes, each evaluating A programs.
    uint64_t prefixes = total / c->gpu->A, chunk = std::max<uint64_t>(1, (1ull << 24) / c->gpu->A), solutions = 0;
    for (uint64_t start = 0; start < prefixes; start += chunk) {
        check_stop();
        std::vector<uint64_t> words;
        solutions += gpu_run(c->gpu, depth, start, std::min(chunk, prefixes - start), words, false, true);
    }
    return solutions;
}
}
