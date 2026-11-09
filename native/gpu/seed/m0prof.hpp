// M0 (reports/m0-baseline-1110/): exclusive rdtsc time buckets for the CPU seed
// Enumerator. Sw(b) charges the time since the last switch to the current bucket
// and makes b current until it is destroyed. Thread-local; flushed into globals
// whenever the outermost Sw closes (once per run_enum).
#pragma once
#include <cstdint>
#include <cstdio>
#include <mutex>
#include <x86intrin.h>
#include "seed_value.hpp"

namespace m0 {
enum B { CHOOSE, FO, LAM, IF_, LIB, HASH, BANK, POOL, COND, NB };
inline const char* NAMES[NB] = {"choose_unify", "eval_fo", "eval_lambda", "eval_if", "eval_lib",
                                 "dedup_hash", "bank_offer", "lam_pool", "cond"};
constexpr int NH = 48, NS = 64;
struct Acc { uint64_t cyc[NB] = {}, cnt[NB] = {}, hist[NH] = {}, size_nodes[NS] = {}, segs = 0, enums = 0, nodes = 0; };
inline thread_local Acc t_acc;
inline thread_local uint64_t* t_cnt = t_acc.cnt;
inline thread_local int t_cur = -1;
inline thread_local uint64_t t_t0 = 0;
inline Acc g_acc;
inline std::mutex g_mu;

inline void flush() {
    std::lock_guard<std::mutex> lk(g_mu);
    for (int b = 0; b < NB; ++b) { g_acc.cyc[b] += t_acc.cyc[b]; g_acc.cnt[b] += t_acc.cnt[b]; }
    for (int h = 0; h < NH; ++h) g_acc.hist[h] += t_acc.hist[h];
    for (int s = 0; s < NS; ++s) g_acc.size_nodes[s] += t_acc.size_nodes[s];
    g_acc.segs += t_acc.segs; g_acc.enums += t_acc.enums; g_acc.nodes += t_acc.nodes;
    t_acc = Acc{};
}
struct Sw {
    int prev;
    explicit Sw(int b) {
        uint64_t t = __rdtsc();
        if (t_cur >= 0) t_acc.cyc[t_cur] += t - t_t0;
        t_t0 = t; prev = t_cur; t_cur = b;
    }
    ~Sw() {
        uint64_t t = __rdtsc();
        t_acc.cyc[t_cur] += t - t_t0;
        t_t0 = t; t_cur = prev;
        if (prev < 0) flush();
    }
};
// one (op, split) segment of a layer: node count -> log2 histogram, nodes per program size
struct Seg {
    int size; const long& nodes; long nb;
    Seg(int s, const long& n, long b) : size(s), nodes(n), nb(b) {}
    ~Seg() {
        long d = nodes - nb;
        int h = 0; while (h + 1 < NH && (1L << h) <= d) ++h;   // h = bit length of d
        ++t_acc.hist[h]; ++t_acc.segs;
        if (size < NS) t_acc.size_nodes[size] += uint64_t(d);
    }
};
inline void note_enum(long nodes) { ++t_acc.enums; t_acc.nodes += uint64_t(nodes); }
inline int bucket_of(bool block, int prim) {
    if (block) return LIB;
    if (prim == seed::IF) return IF_;
    if (prim == seed::MAP || prim == seed::FILTER || prim == seed::ZIPWITH || prim == seed::FOLD) return LAM;
    return FO;
}
}  // namespace m0
