// N5d / B1 (reports/seed-gpu-b1-1110/): e2e_kernel.cu with a resident, pooled device context.
//  - e2e_destroy() returns the context to a per-thread pool; the next Enumerator on that thread
//    (every decomposition sub-problem of the task) reuses its stream, device buffers, hash
//    table and pinned staging: no stream create, no cudaMallocAsync/free or grow copies.
//  - every H2D goes through a pinned staging area (truly async), D2H of the status into pinned.
//  - fewer stream ops per GPU layer: table clear = one kernel (was two memsets), the insertion
//    of existing fingerprints is fused into the first eval launch of the layer (both use
//    atomicMin; existing fps have rank 0, so order does not matter), table shrink never reallocs.
// Interface (e2e.hpp) unchanged, so seed_enum_gpu.o is linked as is.
// Original N5c header follows.
// N5c: device side of the GPU seed layer inside the real search.
// Reuses kernel.cu's per-primitive evaluation (apply) and structural hash (hash_r).
// One context per Enumerator: its own stream, stream-ordered allocations,
// incrementally appended entries (GVal / cells / items), bucket id lists and
// existing-entry fingerprints; per layer an open-addressing table of
// (fp, min rank). Candidate status: SKIP (comm), NODE (eval failure or a
// lower-rank / existing twin), SURV (first of its fingerprint).
#include "kernel.cu"
#include "e2e.hpp"
#include <chrono>
#include <cstring>
#include <vector>

namespace gseed {

namespace {
struct DBuf {
    void* p = nullptr;
    uint64_t n = 0;    // used bytes
    uint64_t cap = 0;  // bytes
};
}  // namespace

struct E2eCtx {
    cudaStream_t s = nullptr;
    DBuf items, vals, cells, ids, fps;
    DBuf tfp, trank;  // table
    uint64_t tcap = 0, tused = 0;  // slots (logical, <= physical), upper bound of filled slots
    DBuf jobs, status, slot;
    uint64_t bytes = 0;
    char* stg = nullptr; uint64_t stg_cap = 0, stg_used = 0;  // pinned H2D staging
    uint8_t* hst = nullptr; uint64_t hst_cap = 0;             // pinned status
    uint64_t pend_fp = 0;  // existing fps not inserted yet (fused into the next eval launch)
};

// B1 counters (printed at exit with --seed-prof)
namespace {
struct B1Prof {
    std::atomic<uint64_t> creates{0}, reuses{0}, ops{0}, launches{0}, h2d_calls{0}, h2d_bytes{0}, h2d_ns{0},
        mallocs{0};
    ~B1Prof() {
        if (!g_e2e.prof) return;
        fprintf(stderr,
                "{\"b1_prof\": true, \"ctx_creates\": %llu, \"ctx_reuses\": %llu, \"stream_ops\": %llu, "
                "\"kernel_launches\": %llu, \"h2d_calls\": %llu, \"h2d_mb\": %.1f, \"h2d_enqueue_s\": %.3f, "
                "\"device_mallocs\": %llu}\n",
                (unsigned long long)creates.load(), (unsigned long long)reuses.load(), (unsigned long long)ops.load(),
                (unsigned long long)launches.load(), (unsigned long long)h2d_calls.load(), h2d_bytes.load() / 1048576.0,
                h2d_ns.load() * 1e-9, (unsigned long long)mallocs.load());
    }
} g_b1;
uint64_t b1_now() {
    return uint64_t(std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch()).count());
}
}  // namespace

#define CKR(x) do { cudaError_t e_ = (x); if (e_ != cudaSuccess) { fprintf(stderr, "gpuseed-e2e: %s: %s\n", #x, cudaGetErrorString(e_)); return 1; } } while (0)

static int dalloc(E2eCtx* c, DBuf& b, uint64_t bytes, bool keep) {
    if (bytes <= b.cap) return 0;
    uint64_t nc = b.cap ? b.cap : 4096;
    while (nc < bytes) nc *= 2;
    if (g_vram.load() + nc - b.cap > VRAM_CAP) { fprintf(stderr, "gpuseed-e2e: vram cap\n"); return 1; }
    void* np = nullptr;
    CKR(cudaMallocAsync(&np, nc, c->s));
    ++g_b1.mallocs; ++g_b1.ops;
    if (keep && b.n) { CKR(cudaMemcpyAsync(np, b.p, b.n, cudaMemcpyDeviceToDevice, c->s)); ++g_b1.ops; }
    if (b.p) CKR(cudaFreeAsync(b.p, c->s));
    uint64_t now = (g_vram += nc - b.cap);
    for (uint64_t pk = g_prof.vram_peak.load(); now > pk && !g_prof.vram_peak.compare_exchange_weak(pk, now);) {}
    c->bytes += nc - b.cap;
    b.p = np; b.cap = nc;
    if (!keep) b.n = 0;
    return 0;
}
constexpr uint64_t STG_MAX = 64ull << 20;  // larger single copies go pageable
static int dappend(E2eCtx* c, DBuf& b, const void* h, uint64_t bytes) {
    if (!bytes) return 0;
    const uint64_t t0 = b1_now();
    if (dalloc(c, b, b.n + bytes, true)) return 1;
    const void* src = h;
    if (bytes <= STG_MAX) {
        if (c->stg_used + bytes > c->stg_cap) {
            // staging is reused only after the stream drained the earlier copies
            if (c->stg_used) { CKR(cudaStreamSynchronize(c->s)); c->stg_used = 0; }
            if (bytes > c->stg_cap) {
                uint64_t nc = c->stg_cap ? c->stg_cap : (1ull << 20);
                while (nc < bytes) nc *= 2;
                if (c->stg) CKR(cudaFreeHost(c->stg));
                c->stg = nullptr; c->stg_cap = 0;
                CKR(cudaHostAlloc((void**)&c->stg, nc, cudaHostAllocDefault));
                c->stg_cap = nc;
            }
        }
        std::memcpy(c->stg + c->stg_used, h, bytes);
        src = c->stg + c->stg_used;
        c->stg_used += (bytes + 255) & ~uint64_t(255);
        if (c->stg_used > c->stg_cap) c->stg_used = c->stg_cap;
    }
    CKR(cudaMemcpyAsync((char*)b.p + b.n, src, bytes, cudaMemcpyHostToDevice, c->s));
    b.n += bytes;
    ++g_b1.ops; ++g_b1.h2d_calls; g_b1.h2d_bytes += bytes; g_b1.h2d_ns += b1_now() - t0;
    return 0;
}

static void ctx_free(E2eCtx* c) {
    for (DBuf* b : {&c->items, &c->vals, &c->cells, &c->ids, &c->fps, &c->tfp, &c->trank, &c->jobs, &c->status, &c->slot})
        if (b->p) cudaFreeAsync(b->p, c->s);
    cudaStreamSynchronize(c->s);
    if (c->stg) cudaFreeHost(c->stg);
    if (c->hst) cudaFreeHost(c->hst);
    cudaStreamDestroy(c->s);
    cudaGetLastError();
    g_vram -= c->bytes;
    delete c;
}
namespace {
struct Pool {  // per thread: contexts released by finished Enumerators
    std::vector<E2eCtx*> free;
    ~Pool() { for (E2eCtx* c : free) ctx_free(c); }
};
thread_local Pool t_pool;
}  // namespace

E2eCtx* e2e_create() {
    if (!t_pool.free.empty()) {
        E2eCtx* c = t_pool.free.back();
        t_pool.free.pop_back();
        ++g_b1.reuses;
        return c;
    }
    E2eCtx* c = new E2eCtx;
    if (cudaStreamCreateWithFlags(&c->s, cudaStreamNonBlocking) != cudaSuccess) { cudaGetLastError(); delete c; return nullptr; }
    ++g_b1.creates;
    return c;
}
void e2e_destroy(E2eCtx* c) {
    if (!c) return;
    // keep stream, buffers (capacity), table and staging; forget the contents
    if (cudaStreamSynchronize(c->s) != cudaSuccess) { cudaGetLastError(); ctx_free(c); return; }
    for (DBuf* b : {&c->items, &c->vals, &c->cells, &c->ids, &c->fps, &c->jobs, &c->status, &c->slot}) b->n = 0;
    c->tused = 0; c->pend_fp = 0; c->stg_used = 0;
    t_pool.free.push_back(c);
}
uint64_t e2e_bytes(const E2eCtx* c) { return c ? c->bytes : 0; }

int e2e_append(E2eCtx* c, const GItem* items, uint64_t nitems, const GVal* vals, uint64_t nvals, const int8_t* cells,
               uint64_t ncells) {
    if (dappend(c, c->items, items, nitems * sizeof(GItem)) || dappend(c, c->vals, vals, nvals * sizeof(GVal)) ||
        dappend(c, c->cells, cells, ncells))
        return 1;
    // no sync: async H2D from pageable memory stages the host data before returning
    return 0;
}
int e2e_append_ids(E2eCtx* c, const uint32_t* ids, uint64_t n, uint32_t* off) {
    *off = uint32_t(c->ids.n / 4);
    return dappend(c, c->ids, ids, n * 4);
}
int e2e_append_fps(E2eCtx* c, const uint64_t* fps, uint64_t n) {
    return dappend(c, c->fps, fps, n * 8);
}

__device__ __forceinline__ uint64_t tab_insert(uint64_t* tfp, uint64_t mask, uint64_t f) {
    uint64_t pos = f & mask;
    while (true) {
        unsigned long long old = atomicCAS((unsigned long long*)&tfp[pos], 0ull, (unsigned long long)f);
        if (old == 0 || old == f) return pos;
        pos = (pos + 1) & mask;
    }
}

__global__ void k_insert_fps(const uint64_t* fps, uint64_t n, uint64_t* tfp, unsigned long long* trank, uint64_t mask) {
    uint64_t i = uint64_t(blockIdx.x) * blockDim.x + threadIdx.x;
    if (i >= n) return;
    uint64_t pos = tab_insert(tfp, mask, fps[i]);
    atomicMin(&trank[pos], 0ull);
}

__global__ void k_rehash(const uint64_t* ofp, const unsigned long long* orank, uint64_t ocap, uint64_t* tfp,
                         unsigned long long* trank, uint64_t mask) {
    uint64_t i = uint64_t(blockIdx.x) * blockDim.x + threadIdx.x;
    if (i >= ocap || !ofp[i]) return;
    uint64_t pos = tab_insert(tfp, mask, ofp[i]);
    atomicMin(&trank[pos], orank[i]);
}

__device__ __forceinline__ const CJob& find_job(const CJob* jobs, uint64_t njobs, uint64_t c) {
    uint64_t lo = 0, hi = njobs;
    while (hi - lo > 1) { uint64_t m = (lo + hi) / 2; if (jobs[m].start <= c) lo = m; else hi = m; }
    return jobs[lo];
}
__device__ __forceinline__ uint64_t rank_of(const CJob& J, uint64_t k) {
    return J.rank0 + (k / J.bCnt) * J.rstride + k % J.bCnt;
}

__global__ void k_eval(const CJob* jobs, uint64_t njobs, uint64_t ncand, int n, const GVal* vals,
                       const int8_t* cells, const GItem* items, const uint32_t* ids, uint64_t* tfp,
                       unsigned long long* trank, uint64_t mask, uint8_t* status, uint32_t* slot,
                       const uint64_t* fps, uint64_t nfp) {
    uint64_t c = uint64_t(blockIdx.x) * blockDim.x + threadIdx.x;
    if (c >= ncand) {  // fused k_insert_fps (rank 0 is the minimum: order-independent)
        uint64_t i = c - ncand;
        if (i < nfp) atomicMin(&trank[tab_insert(tfp, mask, fps[i])], 0ull);
        return;
    }
    const CJob J = find_job(jobs, njobs, c);
    uint64_t k = c - J.start;
    uint32_t ia = ids[J.aOff + uint32_t(k / J.bCnt)];
    uint32_t ib = J.arity == 2 ? ids[J.bOff + uint32_t(k % J.bCnt)] : ia;
    const GItem A = items[ia], B = items[ib];
    if (J.comm && A.seq > B.seq) { status[c] = ST_SKIP; return; }
    uint64_t f = fp_begin(J.ret);
    for (int j = 0; j < n; ++j) {
        R r;
        if (!apply(J.prim, vals[A.voff + j], vals[B.voff + j], cells, r)) { status[c] = ST_NODE; return; }
        f = h_step(f, hash_r(r));
    }
    f = fp_end(f);
    uint64_t pos = tab_insert(tfp, mask, f);
    atomicMin(&trank[pos], (unsigned long long)rank_of(J, k));
    slot[c] = uint32_t(pos);
    status[c] = ST_SURV;
}

__global__ void k_resolve(const CJob* jobs, uint64_t njobs, uint64_t ncand, const unsigned long long* trank,
                          uint8_t* status, const uint32_t* slot) {
    uint64_t c = uint64_t(blockIdx.x) * blockDim.x + threadIdx.x;
    if (c >= ncand || status[c] != ST_SURV) return;
    const CJob& J = find_job(jobs, njobs, c);
    if (trank[slot[c]] != rank_of(J, c - J.start)) status[c] = ST_NODE;
}

static unsigned nblk(uint64_t n) { return unsigned((n + 255) / 256); }

__global__ void k_clear(uint64_t* tfp, unsigned long long* trank, uint64_t n) {
    uint64_t i = uint64_t(blockIdx.x) * blockDim.x + threadIdx.x;
    if (i >= n) return;
    tfp[i] = 0;
    trank[i] = ~0ull;
}
static int clear_table(E2eCtx* c, void* tfp, void* trank, uint64_t slots) {
    k_clear<<<nblk(slots), 256, 0, c->s>>>((uint64_t*)tfp, (unsigned long long*)trank, slots);
    ++g_b1.ops; ++g_b1.launches;
    CKR(cudaGetLastError());
    return 0;
}

static int table_alloc(E2eCtx* c, uint64_t slots) {
    // fresh table arrays (no copy); old ones freed
    DBuf nf, nr;
    nf.cap = nr.cap = 0;
    if (dalloc(c, nf, slots * 8, false) || dalloc(c, nr, slots * 8, false)) {
        if (nf.p) { cudaFreeAsync(nf.p, c->s); g_vram -= nf.cap; c->bytes -= nf.cap; }
        return 1;
    }
    if (clear_table(c, nf.p, nr.p, slots)) return 1;
    if (c->tcap && c->tfp.p) {
        ++g_b1.ops; ++g_b1.launches;
        k_rehash<<<nblk(c->tcap), 256, 0, c->s>>>((const uint64_t*)c->tfp.p, (const unsigned long long*)c->trank.p,
                                                   c->tcap, (uint64_t*)nf.p, (unsigned long long*)nr.p, slots - 1);
        CKR(cudaGetLastError());
    }
    for (DBuf* b : {&c->tfp, &c->trank})
        if (b->p) { CKR(cudaFreeAsync(b->p, c->s)); g_vram -= b->cap; c->bytes -= b->cap; }
    c->tfp = nf; c->trank = nr; c->tcap = slots;
    return 0;
}

int e2e_begin_layer(E2eCtx* c, uint64_t extra) {
    uint64_t nf = c->fps.n / 8, need = 2 * (nf + extra) + 1024, slots = 1024;
    while (slots < need) slots *= 2;
    if (slots * 8 > c->tfp.cap) {
        c->tcap = 0;  // no rehash: the table is rebuilt from the fps
        if (table_alloc(c, slots)) return 1;
    } else {  // resident table: use a prefix of the physical arrays
        c->tcap = slots;
        if (clear_table(c, c->tfp.p, c->trank.p, slots)) return 1;
    }
    c->pend_fp = nf;  // inserted by the first eval launch of the layer
    c->tused = nf;
    return 0;
}

int e2e_run_chunk(E2eCtx* c, const CJob* jobs, uint64_t njobs, uint64_t ncand, int n, uint8_t* status) {
    if (!ncand) return 0;
    if (c->pend_fp && 2 * (c->tused + ncand) > c->tcap) {  // rehash needs the fps in the table
        k_insert_fps<<<nblk(c->pend_fp), 256, 0, c->s>>>((const uint64_t*)c->fps.p, c->pend_fp, (uint64_t*)c->tfp.p,
                                                         (unsigned long long*)c->trank.p, c->tcap - 1);
        ++g_b1.ops; ++g_b1.launches;
        CKR(cudaGetLastError());
        c->pend_fp = 0;
    }
    if (2 * (c->tused + ncand) > c->tcap) {
        uint64_t slots = c->tcap;
        while (slots < 2 * (c->tused + ncand)) slots *= 2;
        if (table_alloc(c, slots)) return 1;
    }
    c->jobs.n = 0;
    if (dappend(c, c->jobs, jobs, njobs * sizeof(CJob))) return 1;
    if (dalloc(c, c->status, ncand, false) || dalloc(c, c->slot, ncand * 4, false)) return 1;
    const uint64_t nfp = c->pend_fp;
    c->pend_fp = 0;
    k_eval<<<nblk(ncand + nfp), 256, 0, c->s>>>((const CJob*)c->jobs.p, njobs, ncand, n, (const GVal*)c->vals.p,
                                          (const int8_t*)c->cells.p, (const GItem*)c->items.p,
                                          (const uint32_t*)c->ids.p, (uint64_t*)c->tfp.p,
                                          (unsigned long long*)c->trank.p, c->tcap - 1, (uint8_t*)c->status.p,
                                          (uint32_t*)c->slot.p, (const uint64_t*)c->fps.p, nfp);
    ++g_b1.ops; ++g_b1.launches;
    CKR(cudaGetLastError());
    k_resolve<<<nblk(ncand), 256, 0, c->s>>>((const CJob*)c->jobs.p, njobs, ncand, (const unsigned long long*)c->trank.p,
                                             (uint8_t*)c->status.p, (const uint32_t*)c->slot.p);
    ++g_b1.ops; ++g_b1.launches;
    CKR(cudaGetLastError());
    if (ncand > c->hst_cap) {
        uint64_t nc = c->hst_cap ? c->hst_cap : (1ull << 20);
        while (nc < ncand) nc *= 2;
        if (c->hst) CKR(cudaFreeHost(c->hst));
        c->hst = nullptr; c->hst_cap = 0;
        CKR(cudaHostAlloc((void**)&c->hst, nc, cudaHostAllocDefault));
        c->hst_cap = nc;
    }
    CKR(cudaMemcpyAsync(c->hst, c->status.p, ncand, cudaMemcpyDeviceToHost, c->s));
    ++g_b1.ops;
    CKR(cudaStreamSynchronize(c->s));
    c->stg_used = 0;
    std::memcpy(status, c->hst, ncand);
    c->tused += ncand;
    return 0;
}
}  // namespace gseed
