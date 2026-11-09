// Compare complete results, exact step budgets and Store state with/without C.
#include "seed_value.hpp"
#include <cassert>
#include <iostream>

using namespace seed;

PP leaf(const char* name) { return p_leaf(sym(name)); }
PP app(const char* name, std::vector<PP> args) {
    args.insert(args.begin(), p_str(sym(name)));
    return p_tup(std::move(args));
}
PP lam(PP body, int n = 1) { return app("lam", {p_int(n), body}); }
V function(PP body, int n = 1) {
    int node = compile(lam(body, n));
    assert(node >= 0);
    return mk_fn(uint32_t(node));
}
V list(std::initializer_list<V> values) { return store().make(values.begin(), values.size()); }

// Include the intern table, not just the returned values: budget fallback may
// stop after creating some intermediate lists, which must also be identical.
uint64_t snapshot() {
    uint64_t h = 1469598103934665603ull;
    auto add = [&](const auto& xs) {
        h = (h ^ xs.size()) * 1099511628211ull;
        for (auto x : xs) h = (h ^ uint64_t(x)) * 1099511628211ull;
    };
    Store& s = store();
    add(s.elems); add(s.off); add(s.len); add(s.boolish); add(s.hashes); add(s.table);
    return (h ^ s.used) * 1099511628211ull;
}

V run(int p, const V* args, V input, long budget) {
    Ctx ctx{input, budget};
    V result = apply_prim(p, args, ctx);
    std::cout << p << ' ' << input << ' ' << budget << ' ' << result << ' '
              << ctx.steps << ' ' << store().off.size() << ' ' << snapshot() << '\n';
    return result;
}

void exercise(int p, const V* args, V input = 0) {
    V result = run(p, args, input, 100);
    uint64_t state = snapshot();
    assert(run(p, args, input, 100) == result);
    // This assertion also runs against A+B, without the whole-result cache. It
    // checks that repeating even an allocating invocation adds no Store entries.
    assert(snapshot() == state);
    for (long budget : {-1, 0, 1, 2, 3, 4, 8, 100}) run(p, args, input, budget);
}

int main() {
    store().reset(); arena().reset();
    V xs = list({mk_int(1), mk_int(2), mk_int(3), mk_int(4), mk_int(5),
                 mk_int(6), mk_int(7), mk_int(8), mk_int(9), mk_int(10)});
    V ys = list({mk_int(4), mk_int(5), mk_int(6), mk_int(7), mk_int(8),
                 mk_int(9), mk_int(10), mk_int(11)});
    V empty = store().make(nullptr, 0);
    V args[3] = {function(app("add", {leaf("$0"), p_int(1)})), xs, 0};
    exercise(MAP, args);
    args[1] = empty; exercise(MAP, args);
    args[1] = xs;
    args[0] = function(app("lt", {leaf("$0"), p_int(3)}));
    exercise(MAP, args); exercise(FILTER, args);  // primitive is part of the key
    args[0] = function(app("add", {leaf("$0"), leaf("$1")}), 2);
    args[2] = ys; exercise(ZIPWITH, args);
    args[2] = xs; exercise(ZIPWITH, args);       // second list is part of the key
    args[1] = mk_int(7); args[2] = xs; exercise(FOLD, args);
    args[1] = mk_int(8); exercise(FOLD, args);   // initial accumulator is in the key
    args[2] = empty; exercise(FOLD, args);

    args[0] = function(leaf("$0")); args[1] = xs;
    exercise(MAP, args);                        // zero-cost lambda, negative budget
    args[1] = list({mk_bool(true), mk_bool(false)}); exercise(MAP, args);
    args[1] = list({mk_int(1), mk_int(0)}); exercise(MAP, args);
    args[0] = function(leaf("$in")); args[1] = xs;
    exercise(MAP, args, mk_int(7)); exercise(MAP, args, mk_int(8));

    V rows = list({xs, ys});
    args[0] = function(app("cons", {p_int(0), leaf("$0")})); args[1] = rows;
    exercise(MAP, args);                        // intermediate and final allocations
    args[0] = function(app("map", {lam(app("add", {leaf("$0"), p_int(1)})), leaf("$0")}));
    exercise(MAP, args);                        // nested higher-order invocations

    PP body = leaf("$0"); V nested = mk_int(2);
    for (int depth = 0; depth < 10; ++depth) {
        body = app("map", {lam(body), leaf("$0")});
        nested = list({nested});
    }
    args[0] = function(body); args[1] = list({nested});
    exercise(MAP, args);                        // beyond the eight scratch slots
    std::vector<V> large(2048, mk_int(1));
    args[0] = function(leaf("$0")); args[1] = store().make(large.data(), large.size());
    exercise(MAP, args);                        // grow the scratch high-water size
    args[1] = empty; exercise(FILTER, args);     // no stale elements after a shorter result

    args[0] = function(app("cons", {leaf("$1"), leaf("$0")}), 2);
    args[1] = empty; args[2] = xs;
    exercise(FOLD, args);                       // partial allocations on budget failure
    args[0] = function(app("mod", {leaf("$0"), p_int(0)})); args[1] = xs;
    exercise(MAP, args);                        // semantic errors must never be cached
    args[0] = mk_int(0); args[1] = xs; exercise(MAP, args);
    args[1] = empty; exercise(MAP, args);        // empty loop never calls invalid function
    args[1] = mk_int(0); exercise(MAP, args);    // invalid list argument

    size_t n0 = arena().nodes.size(), k0 = arena().kids.size();
    args[0] = function(app("add", {leaf("$0"), p_int(1)})); args[1] = xs;
    exercise(MAP, args);
    V old = args[0];
    arena().nodes.resize(n0); arena().kids.resize(k0);
    args[0] = function(app("sub", {leaf("$0"), p_int(1)}));
    assert(args[0] == old); exercise(MAP, args); // reused Arena node handle
    assert(compile(app("add", {p_int(2), leaf("unknown")})) < 0);
    exercise(MAP, args);                        // failed compilation also changes generation

    store().reset();
    args[0] = function(leaf("$0")); args[1] = list({mk_int(11), mk_int(12)});
    V old_list = args[1]; exercise(MAP, args);
    store().reset();
    args[1] = list({mk_int(21), mk_int(22)});
    assert(args[1] == old_list); exercise(MAP, args); // same value id, different Store
    std::cout << "higher-order invariants: PASS\n";
}
