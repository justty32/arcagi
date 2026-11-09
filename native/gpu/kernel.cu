// CUDA brute-force evaluator: one thread = one program of a fixed length.
// Every primitive mirrors native/src (grid.cpp, prims_base.cpp, prims_more.cpp,
// learners.cpp fit_colormap) line for line; any failure (fail(), out of
// bounds) rejects the program, as arcsearch drops the node.
#include "space.hpp"
#include "gpu.hpp"
#include <cstdio>
#include <cstdlib>
#include <cuda_runtime.h>

namespace gs {
namespace {
#define CK(x) do { cudaError_t e_=(x); if (e_!=cudaSuccess) { std::fprintf(stderr,"cuda %s at %s:%d\n",cudaGetErrorString(e_),__FILE__,__LINE__); std::exit(3); } } while (0)

__device__ int bg_of(const uint8_t* d, int h, int w) {
    int cnt[11];
    for (int c = 0; c < 11; ++c) cnt[c] = 0;
    for (int i = 0; i < h * w; ++i) ++cnt[d[i]];
    int best = -1;
    for (int c = 0; c < 11; ++c) {
        if (!cnt[c]) continue;
        if (best < 0) { best = c; continue; }
        // tuple(n, c==0, -c) > tuple(n_best, best==0, -best)
        int a0 = cnt[c], b0 = cnt[best];
        if (a0 != b0) { if (a0 > b0) best = c; continue; }
        int a1 = c == 0, b1 = best == 0;
        if (a1 != b1) { if (a1 > b1) best = c; continue; }
        if (-c > -best) best = c;
    }
    return best;
}

// transform(): op in 0..6 (D4 order). Writes dst, returns dims.
__device__ void d4(const uint8_t* g, int h, int w, int op, uint8_t* out, int& oh, int& ow) {
    bool tr = op == TRANSPOSE || op == ROT90 || op == ROT270 || op == ANTI_TRANSPOSE;
    oh = tr ? w : h; ow = tr ? h : w;
    for (int y = 0; y < oh; ++y) for (int x = 0; x < ow; ++x) {
        int sy = y, sx = x;
        switch (op) {
            case FLIP_LR: sx = w - 1 - x; break;
            case FLIP_UD: sy = h - 1 - y; break;
            case ROT180: sy = h - 1 - y; sx = w - 1 - x; break;
            case TRANSPOSE: sy = x; sx = y; break;
            case ROT90: sy = h - 1 - x; sx = y; break;
            case ROT270: sy = x; sx = w - 1 - y; break;
            default: sy = h - 1 - x; sx = w - 1 - y; break;  // anti_transpose
        }
        out[y * ow + x] = g[sy * w + sx];
    }
}

__device__ inline bool inb(int h, int w) { return h > 0 && h <= 30 && w > 0 && w <= 30; }

// Apply one step: src (h,w) -> dst (oh,ow). t1 is scratch (900 bytes),
// st a 900-entry stack. Returns false on failure / out of bounds.
__device__ bool apply(DStep s, const uint8_t* src, int h, int w, uint8_t* dst, int& oh, int& ow,
                      uint8_t* t1, uint16_t* st) {
    switch (s.op) {
    case FLIP_LR: case FLIP_UD: case TRANSPOSE: case ROT90: case ROT180: case ROT270: case ANTI_TRANSPOSE:
        d4(src, h, w, s.op, dst, oh, ow); return true;
    case UPSCALE: case TILE: {
        oh = h * s.a; ow = w * s.b;
        if (!inb(oh, ow)) return false;
        for (int y = 0; y < oh; ++y) for (int x = 0; x < ow; ++x)
            dst[y * ow + x] = s.op == TILE ? src[(y % h) * w + x % w] : src[(y / s.a) * w + x / s.b];
        return true;
    }
    case DOWNSCALE: {
        if (h % s.a || w % s.b) return false;
        oh = h / s.a; ow = w / s.b;
        if (!inb(oh, ow)) return false;
        for (int y = 0; y < oh; ++y) for (int x = 0; x < ow; ++x) dst[y * ow + x] = src[(y * s.a) * w + x * s.b];
        return true;
    }
    case MIRROR_TILE: {
        bool hor = s.a != 1, ver = s.a != 0;
        oh = h * (ver ? 2 : 1); ow = w * (hor ? 2 : 1);
        if (!inb(oh, ow)) return false;
        for (int y = 0; y < oh; ++y) for (int x = 0; x < ow; ++x)
            dst[y * ow + x] = src[(y < h ? y : 2 * h - 1 - y) * w + (x < w ? x : 2 * w - 1 - x)];
        return true;
    }
    case CROP_BBOX: {
        int bg = bg_of(src, h, w);
        int top = 99, left = 99, bot = -1, right = -1;
        for (int y = 0; y < h; ++y) for (int x = 0; x < w; ++x) if (src[y * w + x] != bg) {
            top = min(top, y); left = min(left, x); bot = max(bot, y); right = max(right, x);
        }
        if (bot < 0) return false;
        oh = bot - top + 1; ow = right - left + 1;
        for (int y = 0; y < oh; ++y) for (int x = 0; x < ow; ++x) dst[y * ow + x] = src[(top + y) * w + left + x];
        return true;
    }
    case GRAVITY: {
        // prims_more.cpp: rot90^turn, settle down, rot270^turn.
        int turn = s.a;  // 0 down, 1 left, 2 up, 3 right
        int bg = bg_of(src, h, w);
        uint8_t* bufs[2] = {dst, t1};
        int cur = 0, ch = h, cw = w;
        const uint8_t* from = src;
        for (int i = 0; i < turn; ++i) {
            int nh, nw; d4(from, ch, cw, ROT90, bufs[cur], nh, nw);
            from = bufs[cur]; cur ^= 1; ch = nh; cw = nw;
        }
        uint8_t* out = bufs[cur];
        for (int i = 0; i < ch * cw; ++i) out[i] = bg;
        for (int x = 0; x < cw; ++x) {
            int d = ch - 1;
            for (int y = ch - 1; y >= 0; --y) { uint8_t v = from[y * cw + x]; if (v != bg) out[(d--) * cw + x] = v; }
        }
        from = out; cur ^= 1;
        for (int i = 0; i < turn; ++i) {
            int nh, nw; d4(from, ch, cw, ROT270, bufs[cur], nh, nw);
            from = bufs[cur]; cur ^= 1; ch = nh; cw = nw;
        }
        if (from != dst) for (int i = 0; i < ch * cw; ++i) dst[i] = from[i];
        oh = ch; ow = cw;
        return true;
    }
    case FILL_ENCLOSED: {
        int bg = bg_of(src, h, w);
        uint8_t* outside = t1;
        int n = h * w, top = 0;
        for (int i = 0; i < n; ++i) outside[i] = 0;
        for (int y = 0; y < h; ++y) for (int x = 0; x < w; ++x)
            if ((y == 0 || y == h - 1 || x == 0 || x == w - 1) && src[y * w + x] == bg) {
                outside[y * w + x] = 1; st[top++] = uint16_t(y * w + x);
            }
        while (top) {
            int i = st[--top], y = i / w, x = i % w;
            const int dy[4] = {-1, 1, 0, 0}, dx[4] = {0, 0, -1, 1};
            for (int k = 0; k < 4; ++k) {
                int ny = y + dy[k], nx = x + dx[k];
                if (ny < 0 || ny >= h || nx < 0 || nx >= w) continue;
                int j = ny * w + nx;
                if (outside[j] || src[j] != bg) continue;
                outside[j] = 1; st[top++] = uint16_t(j);
            }
        }
        oh = h; ow = w;
        for (int i = 0; i < n; ++i) dst[i] = (src[i] == bg && !outside[i]) ? 10 : src[i];
        return true;
    }
    case SPLIT_OVERLAY: {
        bool v = s.a == 1;
        int len = v ? w : h, mid = len / 2, odd = len % 2;
        if (odd) {  // middle row (h) / column (v) must be uniform
            if (v) { for (int y = 1; y < h; ++y) if (src[y * w + mid] != src[mid]) return false; }
            else { for (int x = 1; x < w; ++x) if (src[mid * w + x] != src[mid * w]) return false; }
        }
        oh = v ? h : mid; ow = v ? mid : w;
        if (!inb(oh, ow)) return false;
        int bg = -1;
        for (int i = 0; i < h * w; ++i) if (src[i] == 0) { bg = 0; break; }
        if (bg < 0) bg = bg_of(src, h, w);
        int off = mid + odd;
        for (int y = 0; y < oh; ++y) for (int x = 0; x < ow; ++x) {
            bool p = src[y * w + x] != bg;
            bool q = v ? src[y * w + x + off] != bg : src[(y + off) * w + x] != bg;
            bool hit;
            switch (s.b) {
                case 0: hit = p && q; break;
                case 1: hit = p || q; break;
                case 2: hit = p != q; break;
                case 3: hit = !(p || q); break;
                default: hit = p && !q; break;
            }
            dst[y * ow + x] = hit ? 10 : 0;
        }
        return true;
    }
    case SELF_TILE: {
        oh = h * h; ow = w * w;
        if (!inb(oh, ow)) return false;
        int bg = bg_of(src, h, w);
        for (int y = 0; y < oh; ++y) for (int x = 0; x < ow; ++x) {
            bool hit = src[(y / h) * w + x / w] != bg;
            if (s.a) hit = !hit;
            dst[y * ow + x] = hit ? src[(y % h) * w + x % w] : uint8_t(bg);
        }
        return true;
    }
    case COLORMAP: {
        oh = h; ow = w;
        for (int i = 0; i < h * w; ++i) dst[i] = src[i] == s.a ? s.b : src[i];
        return true;
    }
    }
    return false;
}

__constant__ DStep c_alpha[256];
__constant__ DTask c_task;

struct Verdict {
    signed char map[11];
    bool exact = true, consistent = true, tvalid = true, tmapped = true;
    __device__ Verdict() { for (int c = 0; c < 11; ++c) map[c] = -1; }
    // Fold one finished state of pair p; false rejects the program.
    __device__ bool fold(int p, const uint8_t* cur, int h, int w, const uint8_t* __restrict__ targets) {
        if (p < c_task.ntrain) {
            if (h != c_task.th[p] || w != c_task.tw[p]) return false;
            const uint8_t* tg = targets + c_task.toff[p];
            for (int i = 0; i < h * w; ++i) {
                int s = cur[i], g = tg[i];
                if (s != g) exact = false;
                if (map[s] < 0) map[s] = (signed char)g;
                else if (map[s] != g) consistent = false;
            }
            return exact || consistent;
        }
        for (int i = 0; i < h * w; ++i) {
            int s = cur[i];
            if (s > 9) { tvalid = false; if (map[s] < 0) tmapped = false; }
        }
        return true;
    }
    // Solution kind (EXACT / CMAP) after every pair, 0 for none.
    __device__ unsigned long long kind() const {
        if (exact) return tvalid ? EXACT : 0;
        return tmapped ? CMAP : 0;
    }
};

// Runs steps [0, n) of prog on input p into one of ba/bb; returns the state
// pointer or nullptr on failure.
__device__ const uint8_t* run_steps(const DStep* prog, int n, const uint8_t* __restrict__ inputs, int p,
                                    uint8_t* ba, uint8_t* bb, uint8_t* bt, uint16_t* st, int& h, int& w) {
    const uint8_t* cur = inputs + c_task.ioff[p];
    h = c_task.ih[p]; w = c_task.iw[p];
    uint8_t* bufs[2] = {ba, bb};
    int which = 0;
    for (int k = 0; k < n; ++k) {
        int oh, ow;
        if (!apply(prog[k], cur, h, w, bufs[which], oh, ow, bt, st) || !inb(oh, ow)) return nullptr;
        cur = bufs[which]; which ^= 1; h = oh; w = ow;
    }
    return cur;
}

__device__ void decode(unsigned long long r, int A, int lo, int hi, int plen, const uint8_t* __restrict__ prefixes, DStep* prog) {
    // Digits for steps hi-1 .. plen from r (least significant = latest step),
    // then the prefix-table row for steps [0, plen).
    for (int k = hi - 1; k >= plen; --k) { prog[k] = c_alpha[r % A]; r /= A; }
    for (int k = 0; k < plen; ++k) prog[k] = c_alpha[prefixes[r * plen + k]];
    (void)lo;
}

__device__ inline void emit(unsigned long long idx, unsigned long long kind, unsigned long long* sols,
                            unsigned int cap, unsigned int* nsol) {
    unsigned int slot = atomicAdd(nsol, 1u);
    if (slot < cap) sols[slot] = idx | (kind << 62);
}

// Flat kernel: one thread = one program (idx), every pair from scratch.
// With plen>0, idx = prefix_row * A^(depth-plen) + suffix digits.
__global__ void k_flat(int A, int depth, unsigned long long start, unsigned long long count,
                       const uint8_t* __restrict__ inputs, const uint8_t* __restrict__ targets,
                       const uint8_t* __restrict__ prefixes, int plen,
                       unsigned long long* sols, unsigned int cap, unsigned int* nsol) {
    unsigned long long t = blockIdx.x * (unsigned long long)blockDim.x + threadIdx.x;
    if (t >= count) return;
    unsigned long long idx = start + t;
    DStep prog[8];
    decode(idx, A, 0, depth, plen, prefixes, prog);
    uint8_t ba[CELLS], bb[CELLS], bt[CELLS];
    uint16_t st[CELLS];
    Verdict v;
    for (int p = 0; p < c_task.nall; ++p) {
        int h, w;
        const uint8_t* cur = run_steps(prog, depth, inputs, p, ba, bb, bt, st, h, w);
        if (!cur || !v.fold(p, cur, h, w, targets)) return;
    }
    if (unsigned long long k = v.kind()) emit(idx, k, sols, cap, nsol);
}

// Shared kernel: one thread = one prefix of depth-1 steps (pidx); the pair-0
// prefix state is computed once and all A last steps are tried on it; only
// programs that pass pair 0 are run on the other pairs. Program idx =
// pidx * A + last.
__global__ void k_shared(int A, int depth, unsigned long long start, unsigned long long count,
                         const uint8_t* __restrict__ inputs, const uint8_t* __restrict__ targets,
                         const uint8_t* __restrict__ prefixes, int plen,
                         unsigned long long* sols, unsigned int cap, unsigned int* nsol) {
    unsigned long long t = blockIdx.x * (unsigned long long)blockDim.x + threadIdx.x;
    if (t >= count) return;
    unsigned long long pidx = start + t;
    DStep prog[8];
    decode(pidx, A, 0, depth - 1, plen, prefixes, prog);
    uint8_t ba[CELLS], bb[CELLS], bt[CELLS], bp[CELLS];
    uint16_t st[CELLS];
    int h0, w0;
    const uint8_t* pre = run_steps(prog, depth - 1, inputs, 0, ba, bb, bt, st, h0, w0);
    if (!pre) return;
    for (int i = 0; i < h0 * w0; ++i) bp[i] = pre[i];
    for (int s = 0; s < A; ++s) {
        prog[depth - 1] = c_alpha[s];
        int h, w;
        if (!apply(prog[depth - 1], bp, h0, w0, ba, h, w, bt, st) || !inb(h, w)) continue;
        Verdict v;
        if (!v.fold(0, ba, h, w, targets)) continue;
        bool ok = true;
        for (int p = 1; p < c_task.nall && ok; ++p) {
            const uint8_t* cur = run_steps(prog, depth, inputs, p, ba, bb, bt, st, h, w);
            ok = cur && v.fold(p, cur, h, w, targets);
        }
        if (!ok) continue;
        if (unsigned long long k = v.kind()) emit(pidx * A + s, k, sols, cap, nsol);
    }
}
}

struct GpuCtx {
    uint8_t *inputs = nullptr, *targets = nullptr;
    unsigned long long* sols = nullptr;
    unsigned int* nsol = nullptr;
    unsigned int cap = 0;
    int A = 0;
    uint8_t* prefixes = nullptr;
    int plen = 0;
};

GpuCtx* gpu_open(unsigned int cap) {
    auto* c = new GpuCtx;
    c->cap = cap;
    CK(cudaMalloc(&c->inputs, MAX_PAIRS * CELLS));
    CK(cudaMalloc(&c->targets, MAX_PAIRS * CELLS));
    CK(cudaMalloc(&c->sols, sizeof(unsigned long long) * cap));
    CK(cudaMalloc(&c->nsol, sizeof(unsigned int)));
    // Per-thread scratch lives in local memory (~4.5 KB per thread).
    CK(cudaDeviceSetLimit(cudaLimitStackSize, 8192));
    return c;
}
void gpu_set_prefixes(GpuCtx* c, const std::vector<uint8_t>& table, int plen) {
    if (c->prefixes) { cudaFree(c->prefixes); c->prefixes = nullptr; }
    c->plen = plen;
    if (!plen || table.empty()) { c->plen = 0; return; }
    CK(cudaMalloc(&c->prefixes, table.size()));
    CK(cudaMemcpy(c->prefixes, table.data(), table.size(), cudaMemcpyHostToDevice));
}
void gpu_close(GpuCtx* c) {
    if (c->prefixes) cudaFree(c->prefixes);
    cudaFree(c->inputs); cudaFree(c->targets); cudaFree(c->sols); cudaFree(c->nsol);
    delete c;
}
void gpu_load(GpuCtx* c, const DTask& task, const std::vector<uint8_t>& inputs,
              const std::vector<uint8_t>& targets, const std::vector<DStep>& alpha) {
    if (alpha.size() > 256) { std::fprintf(stderr, "alphabet > 256\n"); std::exit(3); }
    c->A = int(alpha.size());
    CK(cudaMemcpyToSymbol(c_task, &task, sizeof(DTask)));
    CK(cudaMemcpyToSymbol(c_alpha, alpha.data(), sizeof(DStep) * alpha.size()));
    CK(cudaMemcpy(c->inputs, inputs.data(), inputs.size(), cudaMemcpyHostToDevice));
    if (!targets.empty()) CK(cudaMemcpy(c->targets, targets.data(), targets.size(), cudaMemcpyHostToDevice));
}
uint64_t gpu_run(GpuCtx* c, int depth, uint64_t start, uint64_t count, std::vector<uint64_t>& sols, bool use_prefix,
                 bool shared) {
    CK(cudaMemset(c->nsol, 0, sizeof(unsigned int)));
    const int block = 128;
    unsigned long long blocks = (count + block - 1) / block;
    int plen = use_prefix ? c->plen : 0;
    if (shared) k_shared<<<(unsigned int)blocks, block>>>(c->A, depth, start, count, c->inputs, c->targets, c->prefixes, plen, c->sols, c->cap, c->nsol);
    else k_flat<<<(unsigned int)blocks, block>>>(c->A, depth, start, count, c->inputs, c->targets, c->prefixes, plen, c->sols, c->cap, c->nsol);
    CK(cudaGetLastError());
    unsigned int n = 0;
    CK(cudaMemcpy(&n, c->nsol, sizeof(n), cudaMemcpyDeviceToHost));
    unsigned int keep = n < c->cap ? n : c->cap;
    size_t old = sols.size();
    sols.resize(old + keep);
    if (keep) CK(cudaMemcpy(sols.data() + old, c->sols, sizeof(unsigned long long) * keep, cudaMemcpyDeviceToHost));
    return n;
}
}
