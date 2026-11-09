// GPU seed layer inside the real seed search (N5c, reports/seed-gpu-e2e-1110/).
// Interface between seed_enum_gpu.cpp (g++, the Enumerator copy) and
// e2e_kernel.cu (nvcc). No CUDA types here.
#pragma once
#include "gpuseed.hpp"
#include <atomic>
#include <cstdint>

namespace gseed {

// one GPU job slice of a chunk: rows [aOff, aOff+aCnt) of bucket a x all of bucket b
// Candidates of a slice are stored row-major (status index start + row*bCnt + col);
// their rank (CPU walk order: bucket a, entry a, bucket b, entry b) is
// rank0 + row*rstride + col, since rows of the other b buckets interleave.
struct CJob {
    uint64_t start;            // first candidate index within the chunk
    uint64_t rank0;            // rank of (first row, col 0)
    uint32_t aOff, aCnt;       // into the device id array
    uint32_t bOff, bCnt;       // bCnt = 1 for unary
    uint32_t rstride;          // rank distance between consecutive rows
    int32_t prim, ret, comm, arity;
};
enum : uint8_t { ST_SKIP = 0, ST_NODE = 1, ST_SURV = 2 };

struct E2eCtx;  // device buffers + stream of one Enumerator (e2e_kernel.cu)
E2eCtx* e2e_create();                 // nullptr on failure
void e2e_destroy(E2eCtx*);
// append entries: items (voff refer to the global GVal array), GVals, cells
int e2e_append(E2eCtx*, const GItem* items, uint64_t nitems, const GVal* vals, uint64_t nvals,
               const int8_t* cells, uint64_t ncells);
int e2e_append_ids(E2eCtx*, const uint32_t* ids, uint64_t n, uint32_t* off);  // off: device offset
int e2e_append_fps(E2eCtx*, const uint64_t* fps, uint64_t n);
// new layer: empty table sized for the existing fps + `extra` insertions, existing fps at rank 0
int e2e_begin_layer(E2eCtx*, uint64_t extra);
// evaluate one chunk (a contiguous rank interval); status per candidate (ST_*)
int e2e_run_chunk(E2eCtx*, const CJob* jobs, uint64_t njobs, uint64_t ncand, int n, uint8_t* status);
uint64_t e2e_bytes(const E2eCtx*);

// globals (set by e2e_main.cpp, read by the Enumerator copy)
struct E2eFlags {
    bool gpu = false;
    long gpu_min = 20000;
    bool prof = false;
    bool verify = false;
};
extern E2eFlags g_e2e;
extern std::atomic<uint64_t> g_vram;  // bytes allocated by all contexts
constexpr uint64_t VRAM_CAP = 2400ull << 20;  // ours; the CUDA context itself adds ~0.3-0.5 GB
struct E2eProf {
    std::atomic<uint64_t> run_ns{0}, sup_ns{0}, other_ns{0}, gpu_ns{0}, sync_ns{0};
    std::atomic<uint64_t> enumerators{0}, layers_gpu{0}, chunks{0}, gpu_cands{0}, gpu_surv{0}, gpu_nodes{0},
        nodes_sup{0}, nodes_all{0}, fallbacks{0}, verified{0}, vram_peak{0};
};
extern E2eProf g_prof;
void e2e_print_prof();
}  // namespace gseed
