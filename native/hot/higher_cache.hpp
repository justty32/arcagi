// Included inside namespace seed after mix(), hot_generation and Tmp are defined.
// HOT_C only: memoize a complete successful higher-order primitive invocation.
#pragma once
namespace {
struct HigherEntry {
    uint64_t generation = 0;
    V input = 0, fn = 0, arg1 = 0, arg2 = 0, result = ERR;
    long steps = 0;
    int prim = -1;
};
struct HigherCache {
    static constexpr size_t SIZE = 65536;
    HigherEntry entries[SIZE];  // 4 MiB per worker; exact direct-mapped keys
    const bool profile = [] { const char* p = std::getenv("ARC_HOT_STATS"); return p && *p && *p != '0'; }();
    uint64_t calls = 0, hits = 0, inserts = 0, budget_fallbacks = 0, growing_inserts = 0;
    uint64_t length_calls[8]{}, length_hits[8]{};
    ~HigherCache() {
        if (profile) {
            std::fprintf(stderr, "{\"hot_higher_cache\":true,\"calls\":%llu,\"hits\":%llu,\"inserts\":%llu,\"budget_fallbacks\":%llu,\"growing_inserts\":%llu}\n",
                         (unsigned long long)calls, (unsigned long long)hits,
                         (unsigned long long)inserts, (unsigned long long)budget_fallbacks,
                         (unsigned long long)growing_inserts);
            std::fprintf(stderr, "{\"hot_higher_lengths\":true,\"calls\":[");
            for (int i = 0; i < 8; ++i) std::fprintf(stderr, "%s%llu", i ? "," : "", (unsigned long long)length_calls[i]);
            std::fprintf(stderr, "],\"hits\":[");
            for (int i = 0; i < 8; ++i) std::fprintf(stderr, "%s%llu", i ? "," : "", (unsigned long long)length_hits[i]);
            std::fprintf(stderr, "]}\n");
        }
    }
};

HigherCache& higher_cache() { thread_local HigherCache cache; return cache; }

template <class F>
V higher_cached(int prim, const V* args, Ctx& ctx, F&& evaluate) {
    // About half the measured invocations have fewer than eight elements:
    // their loop is cheaper than hashing a full key. Keep that path unchanged.
    const V source = args[prim == FOLD ? 2 : 1];
    if (!is_list(source) || store().size(source) < 8 ||
        (prim == ZIPWITH && (!is_list(args[2]) || store().size(args[2]) < 8)))
        return evaluate();
    HigherCache& cache = higher_cache();
    const V fn = args[0], a1 = args[1], a2 = PRIM_ARITY[prim] == 3 ? args[2] : 0;
    const V input = ctx.input;
    uint64_t hash = mix(mix(mix(mix(uint64_t(prim), fn), input), a1), a2);
    hash ^= hash >> 29; hash *= 0xbf58476d1ce4e5b9ull; hash ^= hash >> 32;
    HigherEntry& entry = cache.entries[hash & (HigherCache::SIZE - 1)];
    int length_bin = 0;
    if (cache.profile) {
        V list = args[prim == FOLD ? 2 : 1];
        size_t length = is_list(list) ? store().size(list) : 0;
        if (prim == ZIPWITH && is_list(args[2])) length = std::min(length, store().size(args[2]));
        while (length && length_bin < 7) { ++length_bin; length >>= 1; }
        ++cache.calls;
        ++cache.length_calls[length_bin];
    }
    if (entry.generation == hot_generation && entry.prim == prim && entry.input == input &&
        entry.fn == fn && entry.arg1 == a1 && entry.arg2 == a2) {
        // With a smaller budget, real evaluation must stop at the same node and
        // retain its partial Store effects. Never replay that path.
        if (ctx.steps >= entry.steps) {
            ctx.steps -= entry.steps;
            if (cache.profile) { ++cache.hits; ++cache.length_hits[length_bin]; }
            return entry.result;
        }
        if (cache.profile) ++cache.budget_fallbacks;
    }
    const long before = ctx.steps;
    const size_t lists_before = cache.profile ? store().off.size() : 0;
    V result = evaluate();
    if (result != ERR && ctx.steps >= 0) {
        // A completed deterministic invocation has interned every intermediate
        // list it needs. Repeating it in the same generation creates no entries,
        // even if this first invocation grew the Store. Reset/compile invalidates
        // the generation, including temporary Arena id reuse. Nested calls may
        // replace our slot, so write the entire key after evaluation returns.
        entry = {hot_generation, input, fn, a1, a2, result, before - ctx.steps, prim};
        if (cache.profile) {
            ++cache.inserts;
            cache.growing_inserts += store().off.size() != lists_before;
        }
    }
    return result;
}
}  // namespace
