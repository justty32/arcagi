// Exclusive per-thread TSC buckets. Only linked by arcbatch-hot-prof.
#pragma once
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <mutex>
#include <x86intrin.h>

namespace hotprof {
enum B { FO, HO_BODY, HO_BUILD, HO_LOOP, POOL, CHOOSE, OFFER, HASH, COND, OTHER, NB };
inline constexpr const char* names[NB] = {
    "first_order_eval", "ho_lambda_body", "ho_result_build", "ho_loop_rest",
    "lambda_body_pool", "choose_unify", "offer", "dedup_seen_insert", "cond_witness", "other"};
inline const char* path = std::getenv("ARC_HOT_PROF");
inline const bool enabled = path && *path && *path != '0';
struct Acc { uint64_t cycles[NB]{}, calls[NB]{}; };
inline Acc total;
inline std::mutex mutex;
inline thread_local Acc local;
inline thread_local int current = -1;
inline thread_local uint64_t since = 0;

inline void flush() {
    std::lock_guard<std::mutex> lock(mutex);
    for (int b = 0; b < NB; ++b) {
        total.cycles[b] += local.cycles[b];
        total.calls[b] += local.calls[b];
    }
    local = Acc{};
}
struct Sw {
    int previous = -1;
    bool switched = false;
    explicit Sw(int bucket, bool count = true) {
        if (!enabled || bucket < 0) return;
        if (count) ++local.calls[bucket];
        if (bucket == current) return;
        const uint64_t now = __rdtsc();
        previous = current;
        if (current >= 0) local.cycles[current] += now - since;
        current = bucket;
        since = now;
        switched = true;
    }
    ~Sw() {
        if (!switched) return;
        const uint64_t now = __rdtsc();
        local.cycles[current] += now - since;
        current = previous;
        since = now;
        if (previous < 0) flush();
    }
};
inline void report(double wall, double hz) {
    if (!enabled) return;
    FILE* out = std::strcmp(path, "-") == 0 ? stderr : std::fopen(path, "w");
    if (!out) { std::perror("ARC_HOT_PROF"); return; }
    uint64_t sum = 0;
    for (auto c : total.cycles) sum += c;
    std::fprintf(out, "# arcbatch-hot-prof: exclusive rdtsc; wall %.6f s; TSC %.6f GHz\n", wall, hz / 1e9);
    std::fprintf(out, "# TSC elapsed worker time, includes scheduling delays and instrumentation; not hardware CPU cycles.\n");
    std::fprintf(out, "bucket\tseconds\tpercent\tcalls\n");
    for (int b = 0; b < NB; ++b)
        std::fprintf(out, "%s\t%.6f\t%.3f\t%llu\n", names[b], total.cycles[b] / hz,
                     sum ? 100.0 * total.cycles[b] / sum : 0.0,
                     (unsigned long long)total.calls[b]);
    std::fprintf(out, "total\t%.6f\t100.000\t-\n", sum / hz);
    if (out != stderr) std::fclose(out);
}
}  // namespace hotprof
