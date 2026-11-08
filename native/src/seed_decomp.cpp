// Port of seed/decomp.py + seed/witness.py (r07 DEFAULT_SPLITS) and the
// whole-task entry seed.enum.solve / seed._check.
#include "seed_enum.hpp"
#include <chrono>
#include <cmath>
#include <functional>
#include <stdexcept>
#include <unordered_map>
#include <set>

namespace seed {
namespace {
constexpr double PROBE = 0.05, SPLIT = 0.6, COND = 0.05;
constexpr int MAX_DEPTH = 2, MIN_COND = 3, MIN_EXAMPLES = 2;

int S(const char* s) { return sym(s); }

// witness.subst_leaves: replace leaves outside lambdas; null if one is inside
PP subst_leaves_rec(const PP& p, const std::vector<std::pair<int, PP>>& repl, int depth, bool& bad) {
    if (bad || p->kind != PN::TUP) return p;
    if (p->kids.size() == 1) {
        const PP& h = p->kids[0];
        if (h->kind == PN::STR)
            for (const auto& kv : repl)
                if (kv.first == h->s) {
                    if (depth) { bad = true; return p; }
                    return kv.second;
                }
        return p;
    }
    const PP& h = p->kids[0];
    if (h->kind == PN::STR && h->s == S("lam")) {
        if (p->kids.size() < 3) return p;
        return p_tup({p->kids[0], p->kids[1], subst_leaves_rec(p->kids[2], repl, depth + 1, bad)});
    }
    std::vector<PP> k{h};
    size_t from = 1;
    if (h->kind == PN::STR && h->s == S("blk")) { if (p->kids.size() > 1) k.push_back(p->kids[1]); from = 2; }
    for (size_t i = from; i < p->kids.size(); ++i) k.push_back(subst_leaves_rec(p->kids[i], repl, depth, bad));
    return p_tup(std::move(k));
}
PP subst_leaves(const PP& p, const std::vector<std::pair<int, PP>>& repl) {
    bool bad = false;
    PP r = subst_leaves_rec(p, repl, 0, bad);
    return bad ? nullptr : r;
}

PP leaf(const char* s) { return p_leaf(S(s)); }
PP app(const char* op, std::vector<PP> args) {
    std::vector<PP> k{p_str(S(op))};
    for (auto& a : args) k.push_back(std::move(a));
    return p_tup(std::move(k));
}

struct Split {
    std::string name;
    std::vector<V> xs, outs;
    int in_t, out_t;
    std::vector<std::tuple<PP, int, std::vector<V>>> extra;
    std::function<PP(const PP&)> build;
};

bool has(std::initializer_list<int> ps) {
    for (int p : ps) if (!engine().enabled[p]) return false;
    return true;
}

// _table: first-seen order; nullopt on conflict or too few keys
template <class K, class H>
bool table(const std::vector<std::pair<K, V>>& pairs, std::vector<std::pair<K, V>>& out) {
    std::unordered_map<K, size_t, H> idx;
    for (const auto& kv : pairs) {
        auto it = idx.find(kv.first);
        if (it == idx.end()) { idx.emplace(kv.first, out.size()); out.push_back(kv); }
        else if (!py_eq(out[it->second].second, kv.second)) return false;
    }
    return out.size() >= size_t(MIN_EXAMPLES);
}
struct PairHash { size_t operator()(const std::pair<V, int64_t>& p) const { return std::hash<uint64_t>()(p.first * 31 + uint64_t(p.second)); } };

std::vector<Split> witness_splits(Types& T, const std::vector<V>& xs, const std::vector<V>& outs, int in_t, int out_t) {
    std::vector<Split> out;
    Store& St = store();
    for (size_t j = 0; j < xs.size(); ++j) if (!is_list(xs[j]) || !is_list(outs[j])) return out;
    if (T[in_t].k != K_LIST || T[out_t].k != K_LIST) return out;
    int in_e = T[in_t].a, out_e = T[out_t].a;
    bool same_len = true;
    for (size_t j = 0; j < xs.size(); ++j) if (St.size(xs[j]) != St.size(outs[j])) same_len = false;
    if (same_len && has({MAP})) {
        std::vector<std::pair<V, V>> pairs, ex;
        for (size_t j = 0; j < xs.size(); ++j)
            for (size_t k = 0; k < St.size(xs[j]); ++k) pairs.push_back({St.data(xs[j])[k], St.data(outs[j])[k]});
        if (table<V, std::hash<uint64_t>>(pairs, ex)) {
            Split s{"map", {}, {}, in_e, out_e, {}, nullptr};
            for (auto& kv : ex) { s.xs.push_back(kv.first); s.outs.push_back(kv.second); }
            s.build = [](const PP& f) -> PP {
                PP body = subst_leaves(f, {{S("$in"), leaf("$0")}});
                if (!body) return nullptr;
                return app("map", {p_tup({p_str(S("lam")), p_int(1), body}), leaf("$in")});
            };
            out.push_back(std::move(s));
        }
        std::vector<std::pair<std::pair<V, int64_t>, V>> pz, ez;
        for (size_t j = 0; j < xs.size(); ++j)
            for (size_t k = 0; k < St.size(xs[j]); ++k) pz.push_back({{St.data(xs[j])[k], int64_t(k)}, St.data(outs[j])[k]});
        if (table<std::pair<V, int64_t>, PairHash>(pz, ez) && has({ZIPWITH, RANGE, LEN})) {
            Split s{"zip_pos", {}, {}, in_e, out_e, {}, nullptr};
            std::vector<V> pos;
            for (auto& kv : ez) { s.xs.push_back(kv.first.first); s.outs.push_back(kv.second); pos.push_back(mk_int(kv.first.second)); }
            s.extra.push_back({leaf("$i"), T.INT, pos});
            s.build = [](const PP& g) -> PP {
                PP body = subst_leaves(g, {{S("$in"), leaf("$0")}, {S("$i"), leaf("$1")}});
                if (!body) return nullptr;
                return app("zipwith", {p_tup({p_str(S("lam")), p_int(2), body}), leaf("$in"),
                                       app("range", {app("len", {leaf("$in")})})});
            };
            out.push_back(std::move(s));
        }
    }
    {
        bool one = true;
        size_t k = St.size(outs[0]);
        for (auto y : outs) if (St.size(y) != k) one = false;
        if (one && has({TAKE})) {
            bool all_ge = true, any_gt = false;
            for (auto x : xs) { if (St.size(x) < k) all_ge = false; if (St.size(x) > k) any_gt = true; }
            if (all_ge && any_gt) {
                Split s{"take", {}, outs, in_t, out_t, {}, nullptr};
                for (auto x : xs) s.xs.push_back(St.make(St.data(x), k));
                int64_t kk = int64_t(k);
                s.build = [kk](const PP& f) -> PP {
                    return subst_leaves(f, {{S("$in"), app("take", {p_int(kk), leaf("$in")})}});
                };
                out.push_back(std::move(s));
            }
        }
    }
    if (in_t == out_t && has({APPEND})) {
        bool pre = true, suf = true, any_pre = false, any_suf = false;
        std::vector<V> rp, rs;
        for (size_t j = 0; j < xs.size(); ++j) {
            size_t lx = St.size(xs[j]), ly = St.size(outs[j]);
            const V* x = St.data(xs[j]);
            const V* y = St.data(outs[j]);
            // y[:len(x)] == x
            if (!(ly >= lx && std::equal(x, x + lx, y, [](V a, V b) { return py_eq(a, b); }))) pre = false;
            else { rp.push_back(St.make(y + lx, ly - lx)); if (ly > lx) any_pre = true; }
            if (!(ly >= lx && std::equal(x, x + lx, y + (ly - lx), [](V a, V b) { return py_eq(a, b); }))) suf = false;
            else { rs.push_back(St.make(y, ly - lx)); if (ly > lx) any_suf = true; }
        }
        if (pre && any_pre) {
            Split s{"append_pre", xs, rp, in_t, out_t, {}, nullptr};
            s.build = [](const PP& r) -> PP { return app("append", {leaf("$in"), r}); };
            out.push_back(std::move(s));
        }
        if (suf && any_suf) {
            Split s{"append_suf", xs, rs, in_t, out_t, {}, nullptr};
            s.build = [](const PP& r) -> PP { return app("append", {r, leaf("$in")}); };
            out.push_back(std::move(s));
        }
    }
    for (int op : {TRANSPOSE, REVERSE}) {
        if (!engine().enabled[op]) continue;
        if (op == TRANSPOSE && !(T[in_e].k == K_LIST && T[out_e].k == K_LIST)) continue;
        std::vector<V> sx, sy;
        bool bad = false, diff = false;
        Ctx cx{0, MAX_STEPS};
        for (size_t j = 0; j < xs.size() && !bad; ++j) {
            V a = apply_prim(op, &xs[j], cx);
            if (a == ERR) bad = true;
            sx.push_back(a);
        }
        for (size_t j = 0; j < outs.size() && !bad; ++j) {
            V a = apply_prim(op, &outs[j], cx);
            if (a == ERR) bad = true;
            sy.push_back(a);
        }
        if (bad) continue;
        for (size_t j = 0; j < xs.size(); ++j) if (!py_eq(sx[j], xs[j]) || !py_eq(sy[j], outs[j])) diff = true;
        if (!diff) continue;
        const char* name = op == TRANSPOSE ? "transpose" : "reverse";
        Split s{std::string("conj_") + name, sx, sy, in_t, out_t, {}, nullptr};
        s.build = [name](const PP& f) -> PP {
            PP inner = subst_leaves(f, {{S("$in"), app(name, {leaf("$in")})}});
            return inner ? app(name, {inner}) : nullptr;
        };
        out.push_back(std::move(s));
    }
    return out;
}

bool check_prog(const PP& prog, const LibView& lib, const std::vector<V>& xs, const std::vector<V>& outs) {
    bool err = false;
    PP e = expand(prog, &lib, err);
    if (err) return false;
    Arena& A = arena();
    size_t n0 = A.nodes.size(), k0 = A.kids.size();
    int node = compile(e);
    bool ok = node >= 0;
    for (size_t j = 0; ok && j < xs.size(); ++j) {
        Ctx cx{xs[j], MAX_STEPS};
        V v = eval(node, nullptr, 0, cx);
        if (v == ERR || !py_eq(v, outs[j])) ok = false;
    }
    A.nodes.resize(n0); A.kids.resize(k0);
    return ok;
}

struct Solver {
    Types& T;
    const LibView& lib;
    LibView sublib;
    const std::vector<std::pair<int, double>>& order;
    long budget;
    int lam_depth;
    std::vector<int64_t> consts;
    long spent = 0;
    long first = -1;
    std::vector<std::pair<PP, double>> near;
    long steps = 0;
    std::set<std::string> allowed;  // empty: every split

    PP direct(const std::vector<V>& xs, const std::vector<V>& outs, int in_t, int out_t, long b, bool free,
              bool top, const std::vector<std::tuple<PP, int, std::vector<V>>>& extra = {}) {
        b = std::min(b, budget - spent);
        if (b <= 0) return nullptr;
        bool sub = !free;
        bool use_cond = long(xs.size()) >= MIN_COND && (allowed.empty() || allowed.count("if"));
        SubProblem sp{xs, outs, in_t, out_t, extra, sub, consts};
        long eb = use_cond ? long(double(b) * (1 - COND)) : b;
        DirectOut d = run_enum(T, sub ? sublib : lib, sp, eb, lam_depth, order, use_cond, b, top);
        steps += d.eval_steps;
        if (d.prog && !d.cond_hit) first = spent + (d.first > 0 ? d.first : d.nodes);
        spent += d.nodes;
        if (!d.prog || d.cond_hit) {
            spent += d.cond_used;
            if (d.cond_hit) { first = spent; return d.prog; }
        }
        if (top && d.near.size() >= near.size()) near = d.near;
        return d.prog;
    }

    PP solve(const std::vector<V>& xs, const std::vector<V>& outs, int in_t, int out_t, int depth, long b,
             bool free, bool top) {
        long start = spent;
        if (depth <= 0) return direct(xs, outs, in_t, out_t, b, free, top);
        PP prog = direct(xs, outs, in_t, out_t, long(double(b) * PROBE), free, top);
        if (prog) return prog;
        std::vector<Split> sp;
        for (auto& s : witness_splits(T, xs, outs, in_t, out_t))
            if (allowed.empty() || allowed.count(s.name.rfind("append", 0) == 0 ? "append" : s.name))
                sp.push_back(std::move(s));
        for (const Split& s : sp) {
            long share = long(double(b) * SPLIT / double(sp.size()));
            PP sub;
            if (s.name == "zip_pos") sub = direct(s.xs, s.outs, s.in_t, s.out_t, share, false, false, s.extra);
            else {
                bool keep = free && s.name.rfind("append", 0) == 0;
                sub = solve(s.xs, s.outs, s.in_t, s.out_t, depth - 1, share, keep, false);
            }
            if (!sub) continue;
            PP whole = s.build(sub);
            if (whole && check_prog(whole, lib, xs, outs)) return whole;
            first = -1;
        }
        long rest = b - (spent - start);
        return direct(xs, outs, in_t, out_t, rest, free, top);
    }
};
}  // namespace

SolveOut solve_task(const std::vector<Example>& train, const std::vector<Example>& test, const Lib& lib_in,
                    const Settings& st) {
    auto t0 = std::chrono::steady_clock::now();
    store().reset();
    arena().reset();
    Types T;
    SolveOut out;
    LibView lib = make_view(lib_in, T);
    std::vector<std::pair<int, double>> order;
    for (const auto& kv : st.order) order.push_back({sym(kv.first), kv.second});
    std::vector<V> xs, outs;
    for (const auto& e : train) { xs.push_back(from_data(e.input)); outs.push_back(from_data(e.output)); }
    std::vector<V> all = xs;
    all.insert(all.end(), outs.begin(), outs.end());
    set_exclude(st.exclude);
    try {
        if (st.decompose) {
            Solver sv{T, lib, sub_library(lib), order, st.budget, st.lam_depth, task_consts(all)};
            for (const auto& n : st.splits) {
                static const std::set<std::string> known{"map", "zip_pos", "if", "take", "conj_transpose",
                                                         "conj_reverse", "append"};
                if (!known.count(n)) throw std::runtime_error("split " + n + " is not ported (C++ has the r07 DEFAULT_SPLITS); use seed-sub");
                sv.allowed.insert(n);
            }
            PP prog = sv.solve(xs, outs, T.INPUT, T.INPUT, MAX_DEPTH, st.budget, true, true);
            out.program = prog;
            out.nodes = sv.spent;
            out.nodes_to_first = prog ? sv.first : -1;
            out.near = sv.near;
            out.eval_steps = sv.steps;
        } else {
            SubProblem sp{xs, outs, T.INPUT, T.INPUT, {}, false, task_consts(all)};
            DirectOut d = run_enum(T, lib, sp, st.budget, st.lam_depth, order, false, 0, true);
            out.program = d.prog;
            out.nodes = d.nodes;
            out.nodes_to_first = d.first;
            out.near = d.near;
            out.eval_steps = d.eval_steps;
        }
    } catch (const std::exception& e) {
        out.error = e.what();
    } catch (...) {
        out.error = "EvalError raised during search (LamEntry compile)";
    }
    set_exclude({});  // the check runs with every primitive, as grow does
    out.seconds = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
    auto check = [&](const std::vector<Example>& exs) {
        if (exs.empty()) return false;
        std::vector<V> a, b;
        for (const auto& e : exs) {
            if (!e.has_output) return false;
            a.push_back(from_data(e.input));
            b.push_back(from_data(e.output));
        }
        return check_prog(out.program, lib, a, b);
    };
    if (out.program) {
        out.train_ok = check(train);
        out.test_ok = out.train_ok && check(test);
    }
    return out;
}

arc::Json run_json(const PP& prog, const arc::Json& input, const Lib& lib_in, const std::vector<std::string>& exclude) {
    store().reset();
    arena().reset();
    Types T;
    LibView lib = make_view(lib_in, T);
    set_exclude(exclude);
    bool err = false;
    PP e = expand(prog, &lib, err);
    int node = err ? -1 : compile(e);
    arc::Json out("ERR");
    if (node >= 0) {
        Ctx cx{from_data(input), MAX_STEPS};
        V v = eval(node, nullptr, 0, cx);
        if (v != ERR) out = to_data(v);
    }
    set_exclude({});
    return out;
}
}  // namespace seed
