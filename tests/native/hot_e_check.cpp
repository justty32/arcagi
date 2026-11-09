// Compare every read-only batch against apply_prim, including partial writes.
// Pytest links this against both the unchanged A+B and the HOT_E evaluator.
#include "scalar_prims.hpp"
#include <array>
#include <cassert>
#include <iostream>
#include <random>

using namespace seed;
using Args = std::array<V, 3>;
uint64_t digest = 1469598103934665603ull;
size_t checks = 0;

V list(std::initializer_list<V> values) { return store().make(values.begin(), values.size()); }

template<int P>
void check(const std::vector<Args>& rows) {
    const size_t n = rows.size();
    const uint32_t offsets[3] = {uint32_t(2 * n + 5), 3, uint32_t(n + 4)};
    std::vector<V> flat(3 * n + 5, mk_fn(123));
    for (size_t j = 0; j < n; ++j)
        for (int k = 0; k < PRIM_ARITY[P]; ++k) flat[offsets[k] + j] = rows[j][k];
    const V sentinel = mk_fn(999);
    std::vector<V> actual(n, sentinel);
    const bool ok = hot_e::scalar_batch<P>(flat.data(), offsets, n, actual.data());
    for (long budget : {-7L, 0L, MAX_STEPS}) {
        std::vector<V> expected(n, sentinel);
        bool expected_ok = true;
        long steps = 0;
        for (size_t j = 0; j < n; ++j) {
            Ctx cx{mk_int(int64_t(j)), budget};
            expected[j] = apply_prim(P, rows[j].data(), cx);
            steps += budget - cx.steps;
            assert(cx.steps == budget);
            if (expected[j] == ERR) { expected_ok = false; break; }
        }
        assert(steps == 0);
        assert(ok == expected_ok);
        assert(actual == expected);
    }
    digest = (digest ^ uint64_t(ok)) * 1099511628211ull;
    for (V v : actual) digest = (digest ^ v) * 1099511628211ull;
    ++checks;
}

template<int P>
void exercise(const std::vector<V>& values, V xs) {
    const Store before = store();
    auto unchanged = [&] {
        const Store& s = store();
        assert(s.elems == before.elems && s.off == before.off && s.len == before.len);
        assert(s.boolish == before.boolish && s.hashes == before.hashes);
        assert(s.table == before.table && s.used == before.used);
    };
    Args failure{};
    bool can_fail = false;
    for (size_t i = 0; i < values.size(); ++i) {
        for (size_t j = 0; j < values.size(); ++j) {
            Args a{values[i], values[j], values[(17 * i + j) % values.size()]};
            check<P>({a});
            Ctx cx{0, MAX_STEPS};
            if (apply_prim(P, a.data(), cx) == ERR) { failure = a; can_fail = true; }
        }
    }
    unchanged();

    // Successful prefixes followed by ERR at every possible example position.
    Args good{mk_int(1), mk_int(2), mk_bool(false)};
    if constexpr (P == LEN || P == HEAD || P == LAST) good[0] = xs;
    if constexpr (P == NTH) { good[0] = xs; good[1] = mk_int(0); }
    if constexpr (P == COUNT) good[1] = xs;
    for (size_t n : {size_t(0), size_t(1), size_t(8), size_t(31)}) {
        std::vector<Args> rows(n, good);
        check<P>(rows);
        for (size_t j = 0; can_fail && j < n; ++j) {
            rows[j] = failure;
            check<P>(rows);
            rows[j] = good;
        }
    }
    unchanged();

    std::mt19937_64 rng(0x8c1234 + P);
    for (int trial = 0; trial < 300; ++trial) {
        std::vector<Args> rows(1 + rng() % 31);
        for (auto& a : rows)
            for (V& v : a) {
                v = values[rng() % values.size()];
                if (rng() % 2) v = mk_int(int64_t(rng() % 4000000001ull) - 2000000000);
            }
        check<P>(rows);
    }
    unchanged();
}

int main() {
    store().reset();
    std::vector<V> values;
    for (int64_t x : {-(1ll << 60), -1000000001ll, -1000000000ll, -999999999ll,
                      -31623ll, -31622ll, -2ll, -1ll, 0ll, 1ll, 2ll,
                      31622ll, 31623ll, 999999999ll, 1000000000ll, 1000000001ll,
                      (1ll << 60) - 1}) values.push_back(mk_int(x));
    V empty = list({});
    V ints = list({mk_int(0), mk_int(1)});
    V bools = list({mk_bool(false), mk_bool(true)});
    V nested_ints = list({ints, list({mk_int(1)})});
    V nested_bools = list({bools, list({mk_bool(true)})});
    V mixed = list({mk_int(0), empty, mk_fn(1), ERR});
    values.insert(values.end(), {mk_bool(false), mk_bool(true), ERR, mk_fn(1), mk_fn(2),
                                empty, ints, bools, nested_ints, nested_bools, mixed});
    std::vector<V> repeated(1024, mk_bool(true));
    values.push_back(store().make(repeated.data(), repeated.size()));
#define CHECK(P) exercise<P>(values, ints)
    CHECK(ADD); CHECK(SUB); CHECK(MUL); CHECK(NEG); CHECK(MOD); CHECK(EQ);
    CHECK(LT); CHECK(MAX); CHECK(MIN); CHECK(AND); CHECK(OR); CHECK(NOT);
    CHECK(IF); CHECK(LEN); CHECK(NTH); CHECK(HEAD); CHECK(LAST); CHECK(COUNT);
#undef CHECK
    std::cout << "checks=" << checks << " digest=" << digest << '\n';
    std::cout << "scalar batch invariants: PASS\n";
}
