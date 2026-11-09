// Near-miss profiler kernel. Shares N2's primitives, task constants and
// decode by including kernel.cu (same pattern as gp/gp_kernel.cu).
#include "../kernel.cu"
#include "profile.hpp"

namespace gs {
namespace {
// Score of one program over the train pairs: denom += max(out area, target
// area); over the overlap, same += exact cell matches and cnt[out][target]
// counts colour pairs (shared across pairs) for the best single colormap.
struct Score {
    uint16_t cnt[11][10];
    unsigned int denom = 0, same = 0;
    __device__ Score() { for (int s = 0; s < 11; ++s) for (int g = 0; g < 10; ++g) cnt[s][g] = 0; }
    __device__ void fold(int p, const uint8_t* cur, int h, int w, const uint8_t* __restrict__ targets) {
        int th = c_task.th[p], tw = c_task.tw[p];
        const uint8_t* tg = targets + c_task.toff[p];
        denom += max(h * w, th * tw);
        int oh = min(h, th), ow = min(w, tw);
        for (int y = 0; y < oh; ++y) for (int x = 0; x < ow; ++x) {
            int s = cur[y * w + x], g = tg[y * tw + x];
            same += s == g;
            ++cnt[s][g];
        }
    }
    __device__ unsigned int mapped() const {
        unsigned int m = 0;
        for (int s = 0; s < 11; ++s) {
            unsigned int b = 0;
            for (int g = 0; g < 10; ++g) b = max(b, (unsigned int)cnt[s][g]);
            m += b;
        }
        return m;
    }
};

__device__ inline unsigned int quant(unsigned int num, unsigned int den) {
    if (num >= den) return 65535u;
    unsigned int q = (unsigned int)((double)num / den * 65535.0 + 0.5);
    return q > 65534u ? 65534u : q;  // 65535 is reserved for exact fits
}

// One thread = one depth-1 prefix; pair-0 prefix state cached, all A last
// steps scored without early exit. Program idx = pidx * A + s.
__global__ void k_profile(int A, int depth, unsigned long long start, unsigned long long count,
                          const uint8_t* __restrict__ inputs, const uint8_t* __restrict__ targets,
                          const uint8_t* __restrict__ prefixes, int plen, unsigned int thr_q,
                          ProfHit* hits, unsigned int cap, unsigned int* nhit, unsigned int* hist,
                          unsigned long long* ctr) {
    __shared__ unsigned int sh[PROF_BINS];
    for (int i = threadIdx.x; i < PROF_BINS; i += blockDim.x) sh[i] = 0;
    __syncthreads();
    unsigned long long t = blockIdx.x * (unsigned long long)blockDim.x + threadIdx.x;
    unsigned long long nvalid = 0, nfail = 0, nperf = 0;
    if (t < count) {
        unsigned long long pidx = start + t;
        DStep prog[8];
        decode(pidx, A, 0, depth - 1, plen, prefixes, prog);
        uint8_t ba[CELLS], bb[CELLS], bt[CELLS], bp[CELLS];
        uint16_t st[CELLS];
        int h0, w0;
        const uint8_t* pre = run_steps(prog, depth - 1, inputs, 0, ba, bb, bt, st, h0, w0);
        if (!pre) nfail = A;
        else {
            for (int i = 0; i < h0 * w0; ++i) bp[i] = pre[i];
            for (int s = 0; s < A; ++s) {
                prog[depth - 1] = c_alpha[s];
                int h, w;
                if (!apply(prog[depth - 1], bp, h0, w0, ba, h, w, bt, st) || !inb(h, w)) { ++nfail; continue; }
                Score sc;
                sc.fold(0, ba, h, w, targets);
                bool ok = true;
                for (int p = 1; p < c_task.ntrain && ok; ++p) {
                    const uint8_t* cur = run_steps(prog, depth, inputs, p, ba, bb, bt, st, h, w);
                    if (!cur) ok = false;
                    else sc.fold(p, cur, h, w, targets);
                }
                if (!ok) { ++nfail; continue; }
                unsigned int m = sc.mapped();
                unsigned int q = quant(m, sc.denom), rq = quant(sc.same, sc.denom);
                ++nvalid;
                if (m == sc.denom) ++nperf;
                atomicAdd(&sh[q >> 6], 1u);
                if (q >= thr_q) {
                    unsigned int slot = atomicAdd(nhit, 1u);
                    if (slot < cap) hits[slot] = ProfHit{pidx * A + s, q, rq};
                }
            }
        }
    }
    if (nvalid) atomicAdd(&ctr[0], nvalid);
    if (nfail) atomicAdd(&ctr[1], nfail);
    if (nperf) atomicAdd(&ctr[2], nperf);
    __syncthreads();
    for (int i = threadIdx.x; i < PROF_BINS; i += blockDim.x) if (sh[i]) atomicAdd(&hist[i], sh[i]);
}
}

struct ProfCtx {
    uint8_t *inputs = nullptr, *targets = nullptr, *prefixes = nullptr;
    ProfHit* hits = nullptr;
    unsigned int *nhit = nullptr, *hist = nullptr;
    unsigned long long* ctr = nullptr;
    unsigned int cap = 0;
    int A = 0, plen = 0;
};

ProfCtx* prof_open(unsigned int cap) {
    auto* c = new ProfCtx;
    c->cap = cap;
    CK(cudaMalloc(&c->inputs, MAX_PAIRS * CELLS));
    CK(cudaMalloc(&c->targets, MAX_PAIRS * CELLS));
    CK(cudaMalloc(&c->hits, sizeof(ProfHit) * cap));
    CK(cudaMalloc(&c->nhit, sizeof(unsigned int)));
    CK(cudaMalloc(&c->hist, sizeof(unsigned int) * PROF_BINS));
    CK(cudaMalloc(&c->ctr, sizeof(unsigned long long) * 3));
    CK(cudaDeviceSetLimit(cudaLimitStackSize, 8192));
    return c;
}
void prof_close(ProfCtx* c) {
    if (c->prefixes) cudaFree(c->prefixes);
    cudaFree(c->inputs); cudaFree(c->targets); cudaFree(c->hits); cudaFree(c->nhit); cudaFree(c->hist); cudaFree(c->ctr);
    delete c;
}
void prof_load(ProfCtx* c, const DTask& task, const std::vector<uint8_t>& inputs,
               const std::vector<uint8_t>& targets, const std::vector<DStep>& alpha) {
    if (alpha.size() > 256) { std::fprintf(stderr, "alphabet > 256\n"); std::exit(3); }
    c->A = int(alpha.size());
    CK(cudaMemcpyToSymbol(c_task, &task, sizeof(DTask)));
    CK(cudaMemcpyToSymbol(c_alpha, alpha.data(), sizeof(DStep) * alpha.size()));
    CK(cudaMemcpy(c->inputs, inputs.data(), inputs.size(), cudaMemcpyHostToDevice));
    if (!targets.empty()) CK(cudaMemcpy(c->targets, targets.data(), targets.size(), cudaMemcpyHostToDevice));
}
void prof_set_prefixes(ProfCtx* c, const std::vector<uint8_t>& table, int plen) {
    if (c->prefixes) { cudaFree(c->prefixes); c->prefixes = nullptr; }
    c->plen = plen;
    if (!plen || table.empty()) { c->plen = 0; return; }
    CK(cudaMalloc(&c->prefixes, table.size()));
    CK(cudaMemcpy(c->prefixes, table.data(), table.size(), cudaMemcpyHostToDevice));
}
uint64_t prof_run(ProfCtx* c, int depth, uint64_t start, uint64_t count, bool use_prefix, uint32_t thr_q,
                  std::vector<ProfHit>& hits, std::vector<uint64_t>& hist, ProfCounters& ctr) {
    CK(cudaMemset(c->nhit, 0, sizeof(unsigned int)));
    CK(cudaMemset(c->hist, 0, sizeof(unsigned int) * PROF_BINS));
    CK(cudaMemset(c->ctr, 0, sizeof(unsigned long long) * 3));
    const int block = 128;
    unsigned long long blocks = (count + block - 1) / block;
    int plen = use_prefix ? c->plen : 0;
    k_profile<<<(unsigned int)blocks, block>>>(c->A, depth, start, count, c->inputs, c->targets, c->prefixes, plen,
                                               thr_q, c->hits, c->cap, c->nhit, c->hist, c->ctr);
    CK(cudaGetLastError());
    unsigned int n = 0;
    CK(cudaMemcpy(&n, c->nhit, sizeof(n), cudaMemcpyDeviceToHost));
    unsigned int keep = n < c->cap ? n : c->cap;
    hits.resize(keep);
    if (keep) CK(cudaMemcpy(hits.data(), c->hits, sizeof(ProfHit) * keep, cudaMemcpyDeviceToHost));
    std::vector<unsigned int> h(PROF_BINS);
    CK(cudaMemcpy(h.data(), c->hist, sizeof(unsigned int) * PROF_BINS, cudaMemcpyDeviceToHost));
    hist.assign(h.begin(), h.end());
    unsigned long long k[3];
    CK(cudaMemcpy(k, c->ctr, sizeof(k), cudaMemcpyDeviceToHost));
    ctr.valid = k[0]; ctr.fail = k[1]; ctr.perfect = k[2];
    return n;
}
}
