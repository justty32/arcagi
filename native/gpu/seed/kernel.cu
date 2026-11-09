// GPU seed layer kernel: one thread per candidate (op, child a, child b) of one
// enumeration layer, all tasks in one launch. Generate + evaluate on every
// train example + structural hash + fingerprint dedup in a per-task
// open-addressing table. Results are compared against the CPU Enumerator by host.cpp.
#include "gpuseed.hpp"
#include <cuda_runtime.h>
#include <cstdio>
#include <vector>

namespace gseed {

struct L1V { const int8_t* p; int len; int step; };
struct L2V { const int8_t* p; int H, W, rows, r0, rdir; bool tr; };
struct R { int kind; int64_t iv; L1V l1; L2V l2; };

__device__ __forceinline__ L1V l1_of(const GVal& v, const int8_t* cells) { return L1V{cells + v.off, int(v.h), 1}; }
__device__ __forceinline__ L2V l2_of(const GVal& v, const int8_t* cells) {
    return L2V{cells + v.off, int(v.h), int(v.w), int(v.h), 0, 1, false};
}

__device__ uint64_t hash_r(const R& r) {
    if (r.kind == K_I) return h_int(r.iv);
    if (r.kind == K_B) return h_bool(r.iv);
    if (r.kind == K_L1) {
        uint64_t h = h_list0(uint64_t(r.l1.len));
        for (int k = 0; k < r.l1.len; ++k) h = h_step(h, h_int(r.l1.p[k * r.l1.step]));
        return h;
    }
    const L2V& g = r.l2;
    uint64_t h = h_list0(uint64_t(g.rows));
    for (int i = 0; i < g.rows; ++i) {
        int rl = g.tr ? g.H : g.W;
        uint64_t rh = h_list0(uint64_t(rl));
        if (!g.tr) {
            const int8_t* row = g.p + (g.r0 + i * g.rdir) * g.W;
            for (int c = 0; c < rl; ++c) rh = h_step(rh, h_int(row[c]));
        } else {
            for (int c = 0; c < rl; ++c) rh = h_step(rh, h_int(g.p[c * g.W + i]));
        }
        h = h_step(h, rh);
    }
    return h;
}

__device__ bool val_eq(const GVal& a, const GVal& b, const int8_t* cells) {
    if (a.kind != b.kind) return false;
    if (a.kind <= K_B) return a.iv == b.iv;
    if (a.h != b.h) return false;
    if (a.h == 0) return true;
    int cnt = a.h;
    if (a.kind == K_L2) { if (a.w != b.w) return false; cnt = a.h * a.w; }
    for (int k = 0; k < cnt; ++k) if (cells[a.off + k] != cells[b.off + k]) return false;
    return true;
}

__device__ __forceinline__ bool truthy(const GVal& v) {
    if (v.kind <= K_B) return v.iv != 0;
    return v.h != 0;
}
__device__ __forceinline__ void as_val(R& r, const GVal& v, const int8_t* cells) {
    r.kind = v.kind; r.iv = v.iv;
    if (v.kind == K_L1) r.l1 = l1_of(v, cells);
    if (v.kind == K_L2) r.l2 = l2_of(v, cells);
}

// false = ERR (seed_value.cpp apply_prim semantics for these primitives)
__device__ bool apply(int p, const GVal& a, const GVal& b, const int8_t* cells, R& r) {
    switch (p) {
    case P_ADD: case P_SUB: {
        int64_t x = p == P_ADD ? a.iv + b.iv : a.iv - b.iv;
        if (x < -MAX_INT || x > MAX_INT) return false;
        r.kind = K_I; r.iv = x; return true;
    }
    case P_MUL: {  // |operands| <= 1e9, so the product fits int64
        int64_t x = a.iv * b.iv;
        if (x < -MAX_INT || x > MAX_INT) return false;
        r.kind = K_I; r.iv = x; return true;
    }
    case P_NEG: r.kind = K_I; r.iv = -a.iv; return true;
    case P_MOD: {
        if (b.iv == 0) return false;
        int64_t x = a.iv % b.iv;
        if (x != 0 && ((x < 0) != (b.iv < 0))) x += b.iv;
        r.kind = K_I; r.iv = x; return true;
    }
    case P_EQ: r.kind = K_B; r.iv = val_eq(a, b, cells); return true;
    case P_LT: r.kind = K_B; r.iv = a.iv < b.iv; return true;
    case P_MAX: as_val(r, a.iv < b.iv ? b : a, cells); return true;
    case P_MIN: as_val(r, b.iv < a.iv ? b : a, cells); return true;
    case P_AND: as_val(r, truthy(a) ? b : a, cells); return true;
    case P_OR: as_val(r, truthy(a) ? a : b, cells); return true;
    case P_NOT: r.kind = K_B; r.iv = !truthy(a); return true;
    case P_LEN: r.kind = K_I; r.iv = a.h; return true;
    case P_NTH: case P_HEAD: case P_LAST: {
        int64_t i = p == P_NTH ? b.iv : (p == P_HEAD ? 0 : int64_t(a.h) - 1);
        if (i < 0 || i >= int64_t(a.h)) return false;
        if (a.kind == K_L1) { r.kind = K_I; r.iv = cells[a.off + i]; return true; }
        r.kind = K_L1; r.l1 = L1V{cells + a.off + i * a.w, int(a.w), 1}; return true;
    }
    case P_TAKE: case P_DROP: {  // (int, list)
        int64_t nn = a.iv < 0 ? 0 : a.iv;
        int L = b.h;
        int k = int(nn < L ? nn : L);
        r.kind = b.kind;
        if (b.kind == K_L1) {
            r.l1 = p == P_TAKE ? L1V{cells + b.off, k, 1} : L1V{cells + b.off + k, L - k, 1};
        } else {
            r.l2 = l2_of(b, cells);
            if (p == P_TAKE) r.l2.rows = k; else { r.l2.r0 = k; r.l2.rows = L - k; }
        }
        return true;
    }
    case P_REVERSE:
        r.kind = a.kind;
        if (a.kind == K_L1) r.l1 = L1V{cells + a.off + (a.h ? a.h - 1 : 0), int(a.h), -1};
        else { r.l2 = l2_of(a, cells); r.l2.r0 = int(a.h) - 1; r.l2.rdir = -1; }
        return true;
    case P_TRANSPOSE:
        r.kind = K_L2; r.l2 = l2_of(a, cells); r.l2.tr = true; r.l2.rows = a.h ? a.w : 0;
        return true;
    }
    return false;
}

__global__ void layer_kernel(LayerIn in, uint64_t* tab, unsigned long long* nodes, GOut* outs,
                             unsigned long long* nout, uint64_t maxout) {
    uint64_t c = uint64_t(blockIdx.x) * blockDim.x + threadIdx.x;
    if (c >= in.ncand) return;
    // job: last with start <= c
    uint64_t lo = 0, hi = in.njobs;
    while (hi - lo > 1) { uint64_t m = (lo + hi) / 2; if (in.jobs[m].start <= c) lo = m; else hi = m; }
    const GJob& J = in.jobs[lo];
    uint64_t k = c - J.start;
    uint32_t ia = in.ids[J.aOff + uint32_t(k / J.bCnt)];
    uint32_t ib = J.arity == 2 ? in.ids[J.bOff + uint32_t(k % J.bCnt)] : ia;
    const GItem A = in.items[ia], B = in.items[ib];
    bool live = !(J.comm && A.seq > B.seq);
    // node count: warp-aggregated per task
    unsigned act = __activemask();
    unsigned same = __match_any_sync(act, live ? J.task : -1 - J.task);
    if (live && (__ffs(same) - 1) == int(threadIdx.x & 31)) atomicAdd(&nodes[J.task], (unsigned long long)__popc(same));
    if (!live) return;
    uint64_t f = fp_begin(J.ret);
    for (int j = 0; j < J.n; ++j) {
        R r;
        if (!apply(J.prim, in.vals[A.voff + j], in.vals[B.voff + j], in.cells, r)) return;
        f = h_step(f, hash_r(r));
    }
    f = fp_end(f);
    const GTask T = in.tasks[J.task];
    uint64_t pos = f & T.mask;
    while (true) {
        unsigned long long old = atomicCAS((unsigned long long*)&tab[T.tabOff + pos], 0ull, (unsigned long long)f);
        if (old == 0) break;
        if (old == f) return;
        pos = (pos + 1) & T.mask;
    }
    unsigned long long o = atomicAdd(nout, 1ull);
    if (o < maxout) outs[o] = GOut{c, f, J.task, 0};
}

#define CK(x) do { cudaError_t e_ = (x); if (e_ != cudaSuccess) { fprintf(stderr, "cuda %s: %s\n", #x, cudaGetErrorString(e_)); return 1; } } while (0)

template <class T> static int up(T** d, const T* h, uint64_t n) {
    CK(cudaMalloc((void**)d, (n ? n : 1) * sizeof(T)));
    if (n) CK(cudaMemcpy(*d, h, n * sizeof(T), cudaMemcpyHostToDevice));
    return 0;
}

int run_layer(const LayerIn& in, LayerOut& out) {
    cudaEvent_t e0, e1, e2;
    cudaEventCreate(&e0); cudaEventCreate(&e1); cudaEventCreate(&e2);
    cudaEventRecord(e0);
    LayerIn d = in;
    GVal* dv; int8_t* dc; GItem* di; uint32_t* dids; GJob* dj; GTask* dt; uint64_t *dtab0, *dtab;
    unsigned long long *dnodes, *dnout; GOut* douts;
    if (up(&dv, in.vals, in.nvals) || up(&dc, in.cells, in.ncells) || up(&di, in.items, in.nitems) ||
        up(&dids, in.ids, in.nids) || up(&dj, in.jobs, in.njobs) || up(&dt, in.tasks, uint64_t(in.ntasks)) ||
        up(&dtab0, in.table0, in.tabsize)) return 1;
    CK(cudaMalloc(&dtab, in.tabsize * 8));
    CK(cudaMalloc(&dnodes, uint64_t(in.ntasks) * 8));
    CK(cudaMalloc(&dnout, 8));
    CK(cudaMalloc(&douts, (out.maxout ? out.maxout : 1) * sizeof(GOut)));
    cudaEventRecord(e1); cudaEventSynchronize(e1);
    float ms = 0; cudaEventElapsedTime(&ms, e0, e1);
    out.upload_ms = ms;
    out.gpu_bytes = in.nvals * sizeof(GVal) + in.ncells + in.nitems * sizeof(GItem) + in.nids * 4 +
                    in.njobs * sizeof(GJob) + in.tabsize * 16 + out.maxout * sizeof(GOut);
    d.vals = dv; d.cells = dc; d.items = di; d.ids = dids; d.jobs = dj; d.tasks = dt;
    double best = 1e30, sum = 0, rsum = 0;
    int reps = in.reps < 1 ? 1 : in.reps;
    for (int rep = 0; rep < reps; ++rep) {
        cudaEventRecord(e0);
        CK(cudaMemcpyAsync(dtab, dtab0, in.tabsize * 8, cudaMemcpyDeviceToDevice));
        CK(cudaMemsetAsync(dnodes, 0, uint64_t(in.ntasks) * 8));
        CK(cudaMemsetAsync(dnout, 0, 8));
        cudaEventRecord(e1);
        if (in.ncand) {
            uint64_t blocks = (in.ncand + 255) / 256;
            layer_kernel<<<unsigned(blocks), 256>>>(d, dtab, dnodes, douts, dnout, out.maxout);
        }
        cudaEventRecord(e2);
        CK(cudaEventSynchronize(e2));
        CK(cudaGetLastError());
        float rm = 0, km = 0;
        cudaEventElapsedTime(&rm, e0, e1); cudaEventElapsedTime(&km, e1, e2);
        rsum += rm; sum += km; if (km < best) best = km;
    }
    out.kernel_ms_best = best; out.kernel_ms_mean = sum / reps; out.reset_ms_mean = rsum / reps;
    unsigned long long nout = 0;
    CK(cudaMemcpy(&nout, dnout, 8, cudaMemcpyDeviceToHost));
    out.nout = nout;
    std::vector<unsigned long long> nodes(size_t(in.ntasks));
    CK(cudaMemcpy(nodes.data(), dnodes, uint64_t(in.ntasks) * 8, cudaMemcpyDeviceToHost));
    for (int t = 0; t < in.ntasks; ++t) out.nodes[t] = nodes[size_t(t)];
    uint64_t keep = nout < out.maxout ? nout : out.maxout;
    if (keep) CK(cudaMemcpy(out.outs, douts, keep * sizeof(GOut), cudaMemcpyDeviceToHost));
    cudaFree(dv); cudaFree(dc); cudaFree(di); cudaFree(dids); cudaFree(dj); cudaFree(dt);
    cudaFree(dtab0); cudaFree(dtab); cudaFree(dnodes); cudaFree(dnout); cudaFree(douts);
    return 0;
}
}  // namespace gseed
