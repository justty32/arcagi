// Read-only first-order primitives shared by HOT_E's interpreter and batches.
#pragma once
#include "seed_value.hpp"

namespace seed::hot_e {

constexpr int64_t MAX_INT = 1000000000;
static inline V chk_int(int64_t v) { return (v >= -MAX_INT && v <= MAX_INT) ? mk_int(v) : ERR; }

// Keep the case bodies identical to apply_prim's non-HOT_E implementation.
// P is a template argument, so each batch has no per-example dispatch.
template<int P>
inline V scalar_prim(const V* a, Store& S) {
    static_assert((P >= ADD && P <= LAST) || P == COUNT);
    switch (P) {
    case ADD: if (!is_num(a[0]) || !is_num(a[1])) return ERR; return chk_int(ival(a[0]) + ival(a[1]));
    case SUB: if (!is_num(a[0]) || !is_num(a[1])) return ERR; return chk_int(ival(a[0]) - ival(a[1]));
    case MUL: {
        if (!is_num(a[0]) || !is_num(a[1])) return ERR;
        __int128 r = (__int128)ival(a[0]) * ival(a[1]);
        if (r < -MAX_INT || r > MAX_INT) return ERR;
        return mk_int(int64_t(r));
    }
    case NEG: if (!is_num(a[0])) return ERR; return mk_int(-ival(a[0]));
    case MOD: {
        if (!is_num(a[0]) || !is_num(a[1])) return ERR;
        int64_t x = ival(a[0]), y = ival(a[1]);
        if (y == 0) return ERR;
        int64_t r = x % y;
        if (r != 0 && ((r < 0) != (y < 0))) r += y;
        return mk_int(r);
    }
    case EQ: return mk_bool(py_eq(a[0], a[1]));
    case LT: { int r = py_lt(a[0], a[1]); return r < 0 ? ERR : mk_bool(r); }
    case MAX: { int r = py_lt(a[0], a[1]); return r < 0 ? ERR : (r ? a[1] : a[0]); }
    case MIN: { int r = py_lt(a[1], a[0]); return r < 0 ? ERR : (r ? a[1] : a[0]); }
    case AND: return truthy(a[0]) ? a[1] : a[0];
    case OR: return truthy(a[0]) ? a[0] : a[1];
    case NOT: return mk_bool(!truthy(a[0]));
    case IF: return truthy(a[0]) ? a[1] : a[2];
    case LEN: if (!is_list(a[0])) return ERR; return mk_int(int64_t(S.size(a[0])));
    case NTH: {
        int r = py_lt(a[1], mk_int(0));
        if (r < 0) return ERR;
        if (r) return ERR;
        if (!is_list(a[0]) || !is_num(a[1])) return ERR;
        int64_t i = ival(a[1]);
        if (size_t(i) >= S.size(a[0])) return ERR;
        return S.data(a[0])[i];
    }
    case HEAD: if (!is_list(a[0]) || S.size(a[0]) == 0) return ERR; return S.data(a[0])[0];
    case LAST: if (!is_list(a[0]) || S.size(a[0]) == 0) return ERR; return S.data(a[0])[S.size(a[0]) - 1];
    case COUNT: {
        if (!is_list(a[1])) return ERR;
        int64_t k = 0; size_t n = S.size(a[1]);
        for (size_t i = 0; i < n; ++i) k += py_eq(S.data(a[1])[i], a[0]);
        return mk_int(k);
    }
    default: return ERR;
    }
}

template<int P>
inline bool scalar_batch(const V* flat, const uint32_t* offsets, size_t n, V* vals) {
    if (n == 0) return true;
    constexpr int arity = P == NEG || P == NOT || P == LEN || P == HEAD || P == LAST ? 1 : (P == IF ? 3 : 2);
    const V* args[3] = {flat + offsets[0], flat + offsets[1], flat + offsets[2]};
    Store& S = store();
    for (size_t j = 0; j < n; ++j) {
        V a[3];
        a[0] = args[0][j];
        if constexpr (arity >= 2) a[1] = args[1][j];
        if constexpr (arity == 3) a[2] = args[2][j];
        vals[j] = scalar_prim<P>(a, S);
        if (vals[j] == ERR) return false;
    }
    return true;
}

}  // namespace seed::hot_e
