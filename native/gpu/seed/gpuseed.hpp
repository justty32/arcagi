// GPU seed layer (reports/seed-gpu-1110/): shared between host.cpp (g++) and
// kernel.cu (nvcc). One enumeration layer of the seed Enumerator, first-order
// primitives only, values as fixed records (int / bool / list[int] / grid).
#pragma once
#include <cstdint>

#ifdef __CUDACC__
#define HD __host__ __device__ __forceinline__
#else
#define HD inline
#endif

namespace gseed {

// value kinds; L1 = list[int] (cells in int8), L2 = rectangular list[list[int]]
enum Kind : uint8_t { K_I = 0, K_B = 1, K_L1 = 2, K_L2 = 3 };
struct GVal {
    int64_t iv;    // int / bool
    uint32_t off;  // cells offset (L1, L2)
    uint16_t h, w; // L1: h = len; L2: h rows x w cols (h == 0: empty)
    uint8_t kind;
    uint8_t pad[3];
};
struct GItem { uint32_t voff; uint32_t seq; };  // voff: index of example 0 in vals
// GPU-supported primitives (seed Prim numbering, seed_value.hpp)
enum : int { P_ADD = 0, P_SUB, P_MUL, P_NEG, P_MOD, P_EQ, P_LT, P_MAX, P_MIN, P_AND, P_OR, P_NOT,
             P_IF, P_LEN, P_NTH, P_HEAD, P_LAST, P_TAKE, P_DROP, P_REVERSE, P_TRANSPOSE = 31 };
struct GJob {
    uint64_t start;   // first global candidate id (exclusive prefix sum)
    uint32_t aOff, aCnt, bOff, bCnt;  // into the item-id list (bCnt = 1, bOff unused for unary)
    int32_t task, prim, ret, n;
    int32_t comm;     // commutative with equal sizes: skip seq[a] > seq[b] (Enumerator.emit)
    int32_t arity;
};
struct GTask { uint64_t tabOff; uint64_t mask; };  // open-addressing table slice
struct GOut { uint64_t cand; uint64_t fp; int32_t task; int32_t pad; };

constexpr int64_t MAX_INT = 1000000000;  // seed_value.cpp chk_int / mul bound

HD uint64_t mix64(uint64_t z) {
    z += 0x9e3779b97f4a7c15ull;
    z = (z ^ (z >> 30)) * 0xbf58476d1ce4e5b9ull;
    z = (z ^ (z >> 27)) * 0x94d049bb133111ebull;
    return z ^ (z >> 31);
}
// structural value hash (identical on CPU from seed V handles and on GPU)
HD uint64_t h_int(int64_t x) { return mix64(uint64_t(x) ^ 0x1111111111111111ull); }
HD uint64_t h_bool(int64_t b) { return mix64(uint64_t(b) ^ 0x2222222222222222ull); }
HD uint64_t h_list0(uint64_t len) { return mix64(len ^ 0x3333333333333333ull); }
HD uint64_t h_step(uint64_t h, uint64_t e) { return mix64(h * 31 + e); }
HD uint64_t fp_begin(int typ) { return 0x84222325cbf29ce4ull ^ uint64_t(uint32_t(typ)); }
HD uint64_t fp_end(uint64_t f) { return f ? f : 1; }

// host entry (kernel.cu): one layer for all tasks. Returns kernel ms (best of reps).
struct LayerIn {
    const GVal* vals; uint64_t nvals;
    const int8_t* cells; uint64_t ncells;
    const GItem* items; uint64_t nitems;
    const uint32_t* ids; uint64_t nids;
    const GJob* jobs; uint64_t njobs; uint64_t ncand;
    const GTask* tasks; int ntasks;
    const uint64_t* table0; uint64_t tabsize;  // preloaded with fps of earlier entries
    int reps;
};
struct LayerOut {
    std::uint64_t* nodes;  // per task (host, ntasks)
    GOut* outs; uint64_t maxout; uint64_t nout;
    double kernel_ms_best, kernel_ms_mean, reset_ms_mean, upload_ms;
    uint64_t gpu_bytes;
};
int run_layer(const LayerIn& in, LayerOut& out);  // 0 ok
}  // namespace gseed
