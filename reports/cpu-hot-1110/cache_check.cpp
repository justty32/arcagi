// Focused interpreter invariants: replay steps, budget fallback and id reuse.
// Link with the hot build's seed_value.o (no existing tests/sources changed).
#include "seed_value.hpp"
#include <cassert>
#include <iostream>

using namespace seed;

PP leaf(const char* s) { return p_leaf(sym(s)); }
PP app(const char* name, std::vector<PP> args) {
    args.insert(args.begin(), p_str(sym(name)));
    return p_tup(std::move(args));
}
V lambda(PP body, int arity = 1) {
    int node = compile(p_tup({p_str(sym("lam")), p_int(arity), body}));
    assert(node >= 0);
    return mk_fn(uint32_t(node));
}
void expect(V f, V input, const V* args, int n, long budget, V result, long remaining) {
    Ctx c{input, budget};
    assert(call(f, args, n, c) == result);
    assert(c.steps == remaining);
}

int main() {
    store().reset(); arena().reset();
    V x[] = {mk_int(3), mk_int(5)};
    V f = lambda(app("add", {leaf("$0"), p_int(1)}));
    expect(f, 0, x, 1, 10, mk_int(4), 9);  // miss
    expect(f, 0, x, 1, 1, mk_int(4), 0);   // hit, exactly enough budget
    expect(f, 0, x, 1, 0, ERR, -1);        // hit must fall back mid-call
    expect(f, 0, x, 1, 10, mk_int(4), 9);  // fallback did not poison cache
    f = lambda(app("add", {leaf("$0"), leaf("$1")}), 2);
    expect(f, 0, x, 2, 10, mk_int(8), 9);
    x[1] = mk_int(6);
    expect(f, 0, x, 2, 10, mk_int(9), 9);
    f = lambda(leaf("$in"));
    expect(f, mk_int(7), x, 1, 10, mk_int(7), 10);
    expect(f, mk_int(8), x, 1, 10, mk_int(8), 10);
    expect(f, mk_int(8), x, 1, -1, mk_int(8), -1);  // zero-step fallback

    auto n0 = arena().nodes.size(), k0 = arena().kids.size();
    f = lambda(app("add", {leaf("$0"), p_int(1)}));
    expect(f, 0, x, 1, 10, mk_int(4), 9);
    arena().nodes.resize(n0); arena().kids.resize(k0);
    V reused = lambda(app("sub", {leaf("$0"), p_int(1)}));
    assert(f == reused);
    expect(reused, 0, x, 1, 10, mk_int(2), 9);

    V elems[] = {mk_int(1), mk_int(2)};
    V list = store().make(elems, 2);
    f = lambda(app("reverse", {leaf("$0")}));
    size_t before = store().off.size();
    Ctx c{0, 10};
    V result = call(f, &list, 1, c);
    assert(store().off.size() == before + 1 && c.steps == 9);
    expect(f, 0, &list, 1, 10, result, 9);  // now eligible to insert
    expect(f, 0, &list, 1, 1, result, 0);   // cached existing list
    assert(store().off.size() == before + 1);

    // Reset only the Store to prove cached list handles are invalidated even
    // when the Arena and lambda node stay alive.
    f = lambda(app("head", {leaf("$0")}));
    expect(f, 0, &list, 1, 10, mk_int(1), 9);
    store().reset();
    elems[0] = mk_int(9);
    V same_id = store().make(elems, 2);
    assert(same_id == list);
    expect(f, 0, &same_id, 1, 10, mk_int(9), 9);
    std::cout << "cache invariants: PASS\n";
}
