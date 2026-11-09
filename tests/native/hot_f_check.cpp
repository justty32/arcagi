// Pytest compares exact handles, remaining steps and every Store field for E/F.
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
int node(PP body) { int n = compile(body); assert(n >= 0); return n; }
V list(std::initializer_list<V> xs) { return store().make(xs.begin(), xs.size()); }

template<class T>
void dump(const std::vector<T>& xs) {
    std::cout << xs.size() << ':';
    for (auto x : xs) std::cout << +x << ',';
    std::cout << '\n';
}

void observe(const char* name, int entry, long budget, V result, const Ctx& c) {
    std::cout << name << ' ' << entry << ' ' << budget << ' ' << result << ' ' << c.steps << '\n';
    const Store& s = store();
    // Exact contents, including intern layout and partial allocations on ERR.
    dump(s.elems); dump(s.off); dump(s.len); dump(s.boolish); dump(s.hashes); dump(s.table);
    std::cout << s.used << '\n';
}

void exercise(const char* name, PP body, std::vector<V> env, V input) {
    const int root = node(body);
    const V fn = mk_fn(uint32_t(node(lam(body, env.size() == 2 ? 2 : 1))));
    // Warm the A cache, then cross its exact-budget and insufficient-budget paths.
    for (long budget : {32L, -1L, 0L, 1L, 2L, 3L, 4L, 5L, 8L, 32L}) {
        for (int entry = 0; entry < 3; ++entry) {
            Ctx c{input, budget};
            V result = entry == 0 ? eval(root, env.data(), int(env.size()), c)
                                 : call(fn, env.data(), int(env.size()), c);
            observe(name, entry, budget, result, c);
        }
    }
}

int main() {
    store().reset(); arena().reset();
    const V x = mk_int(7), env[] = {x};
    const int add = node(app("add", {leaf("$0"), p_int(1)}));
    for (long budget : {-2L, -1L, 0L, 1L, 2L}) {
        Ctx c{x, budget};
        assert(eval(add, env, 1, c) == (budget >= 1 ? mk_int(8) : ERR));
        assert(c.steps == budget - 1);
    }

    // An invalid first kid must stop before an allocating later application.
    const int early = node(app("add", {leaf("$1"), app("range", {p_int(3)})}));
    Ctx c{x, 1};
    const size_t before = store().off.size();
    assert(eval(early, env, 1, c) == ERR && c.steps == 0);
    assert(store().off.size() == before);
    // Reversing kid order must preserve allocation before an invalid VAR.
    const int partial = node(app("add", {app("len", {app("range", {p_int(3)})}), leaf("$1")}));
    c.steps = 2;
    assert(eval(partial, env, 1, c) == ERR && c.steps == -1);
    assert(store().off.size() == before);
    c.steps = 3;
    assert(eval(partial, env, 1, c) == ERR && c.steps == 0);
    assert(store().off.size() == before + 1);

    // A lambda kid returns its own Arena index without evaluating its body.
    const int choice = node(app("if", {p_int(1), lam(leaf("$1")), lam(p_int(0))}));
    const V chosen = mk_fn(uint32_t(arena().kids[size_t(arena().nodes[size_t(choice)].k0 + 1)]));
    c.steps = 1;
    assert(eval(choice, env, 1, c) == chosen && c.steps == 0);

    V xs = list({mk_int(1), mk_int(2), mk_int(3), mk_int(4)});
    PP mapped = app("map", {lam(app("add", {leaf("$0"), p_int(1)})), leaf("$0")});
    const int map_node = node(mapped);
    c.steps = 4;
    assert(eval(map_node, &xs, 1, c) == ERR && c.steps == -1);
    c.steps = 5;
    const V mapped_result = eval(map_node, &xs, 1, c);
    assert(mapped_result == list({mk_int(2), mk_int(3), mk_int(4), mk_int(5)}) && c.steps == 0);

    exercise("const-root", p_int(-3), {x}, x);
    exercise("input-root", leaf("$in"), {x}, mk_bool(true));
    exercise("var-root", leaf("$0"), {mk_bool(true)}, x);
    exercise("lam-root", lam(app("add", {leaf("$0"), p_int(1)})), {x}, x);
    exercise("const-var-kids", app("add", {leaf("$0"), p_int(1)}), {x}, x);
    exercise("input-kid", app("add", {leaf("$in"), leaf("$0")}), {x}, mk_int(5));
    exercise("binary-vars", app("sub", {leaf("$1"), leaf("$0")}), {x, mk_int(9)}, x);
    exercise("var-oob-first", app("add", {leaf("$1"), app("range", {p_int(5)})}), {x}, x);
    exercise("var-oob-last", app("add", {app("len", {app("range", {p_int(5)})}), leaf("$1")}), {x}, x);
    exercise("no-env", app("add", {leaf("$0"), p_int(1)}), {}, x);
    exercise("err-input", app("add", {leaf("$in"), app("range", {p_int(6)})}), {x}, ERR);
    exercise("err-var", app("add", {leaf("$0"), app("range", {p_int(6)})}), {ERR}, x);
    exercise("lam-kid", app("if", {p_int(1), lam(leaf("$1")), lam(p_int(0))}), {x}, x);
    exercise("map", mapped, {xs}, x);
    exercise("map-empty", mapped, {list({})}, x);
    const V rows = list({xs, list({mk_int(0), mk_bool(true)})});
    exercise("nested-map", app("map", {lam(mapped), leaf("$0")}), {rows}, x);
    exercise("allocating-map", app("map", {lam(app("range", {leaf("$0")})), leaf("$0")}), {xs}, x);
    exercise("filter", app("filter", {lam(app("lt", {leaf("$0"), p_int(3)})), leaf("$0")}), {xs}, x);
    PP sum = lam(app("add", {leaf("$0"), leaf("$1")}), 2);
    exercise("zipwith", app("zipwith", {sum, leaf("$0"), leaf("$in")}), {xs}, xs);
    exercise("fold", app("fold", {sum, p_int(0), leaf("$0")}), {xs}, x);
    std::cout << "leaf budget and store invariants: PASS\n";
}
