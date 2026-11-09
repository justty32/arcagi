// Seed enumerator: port of seed/enum.py (Enumerator), seed/lam.py (BodyPool,
// build_ops, leaf_entries, splits) and seed/cond.py (cond_witness).
#include "seed_enum.hpp"
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <map>
#include <set>
#include <stdexcept>
#ifdef HOT_E
#if !defined(HOT_A) || !defined(HOT_B)
#error "HOT_E requires HOT_A and HOT_B"
#endif
#include "scalar_prims.hpp"
#endif

namespace seed {
namespace {
struct Syms { int in, v0, v1, lam, blk, h0, h1, i; };
const Syms& SY() {
    static Syms s{sym("$in"), sym("$0"), sym("$1"), sym("lam"), sym("blk"), sym("$h0"), sym("$h1"), sym("$i")};
    return s;
}
bool is_str(const PP& p, int s) { return p->kind == PN::STR && p->s == s; }
bool leaf_is(const PP& p, int s) { return p->kind == PN::TUP && p->kids.size() == 1 && is_str(p->kids[0], s); }
bool head_is(const PP& p, int s) { return p->kind == PN::TUP && !p->kids.empty() && is_str(p->kids[0], s); }
}

// ---- library helpers (seed/library.py) ------------------------------------------
int hole_count(const PP& p) {
    if (p->kind != PN::TUP) return 0;
    const Syms& S = SY();
    if (p->kids.size() == 1) {
        if (is_str(p->kids[0], S.h0)) return 1;
        if (is_str(p->kids[0], S.h1)) return 2;
        return 0;
    }
    size_t from = (head_is(p, S.lam) || head_is(p, S.blk)) ? 2 : 1;
    int m = 0;
    for (size_t k = from; k < p->kids.size(); ++k) m = std::max(m, hole_count(p->kids[k]));
    return m;
}

bool free_vars(const PP& p, int depth) {
    if (p->kind != PN::TUP) return false;
    const Syms& S = SY();
    if (p->kids.size() == 1) return (is_str(p->kids[0], S.v0) || is_str(p->kids[0], S.v1)) && depth == 0;
    if (head_is(p, S.lam)) return p->kids.size() > 2 && free_vars(p->kids[2], depth + 1);
    size_t from = head_is(p, S.blk) ? 2 : 1;
    for (size_t k = from; k < p->kids.size(); ++k) if (free_vars(p->kids[k], depth)) return true;
    return false;
}

static bool uses_input(const PP& p) {
    if (p->kind != PN::TUP) return false;
    const Syms& S = SY();
    if (p->kids.size() == 1) return is_str(p->kids[0], S.in);
    size_t from = (head_is(p, S.lam) || head_is(p, S.blk)) ? 2 : 1;
    for (size_t k = from; k < p->kids.size(); ++k) if (uses_input(p->kids[k])) return true;
    return false;
}

static bool hole_under_lambda(const PP& p, int depth) {
    if (p->kind != PN::TUP) return false;
    const Syms& S = SY();
    if (p->kids.size() == 1) return depth > 0 && hole_count(p) > 0;
    if (head_is(p, S.lam)) return p->kids.size() > 2 && hole_under_lambda(p->kids[2], depth + 1);
    size_t from = head_is(p, S.blk) ? 2 : 1;
    for (size_t k = from; k < p->kids.size(); ++k) if (hole_under_lambda(p->kids[k], depth)) return true;
    return false;
}

static PP expand_rec(const PP& p, const LibView* lib, bool& err, int depth) {
    if (err) return p;
    if (depth > 200) { err = true; return p; }  // Python: RecursionError
    if (p->kind == PN::STR) { err = true; return p; }  // only reached in ill-formed programs
    if (p->kind != PN::TUP || p->kids.empty()) return p;
    const Syms& S = SY();
    if (head_is(p, S.blk)) {
        if (!lib || p->kids.size() < 2 || p->kids[1]->kind != PN::STR) { err = true; return p; }
        const BlockInfo* b = lib->find(p->kids[1]->s);
        if (!b) { err = true; return p; }
        std::vector<PP> args;
        for (size_t k = 2; k < p->kids.size(); ++k) args.push_back(expand_rec(p->kids[k], lib, err, depth + 1));
        PP body = expand_rec(b->b->body, lib, err, depth + 1);
        if (err) return p;
        return substitute(body, args, err);
    }
    if (head_is(p, S.lam)) {
        if (p->kids.size() < 3) { err = true; return p; }
        return p_tup({p->kids[0], p->kids[1], expand_rec(p->kids[2], lib, err, depth + 1)});
    }
    if (p->kids.size() == 1) return p;
    std::vector<PP> k{p->kids[0]};
    for (size_t i = 1; i < p->kids.size(); ++i) k.push_back(expand_rec(p->kids[i], lib, err, depth + 1));
    return p_tup(std::move(k));
}

PP expand(const PP& p, const LibView* lib, bool& err) { return expand_rec(p, lib, err, 0); }

LibView make_view(const Lib& lib, Types& T) {
    LibView v;
    for (const auto& b : lib.blocks) {
        BlockInfo bi;
        bi.b = &b;
        bi.sig = T.parse(b.sig);
        bi.holes = hole_count(b.body);
        bi.sig_fn = T[bi.sig].k == K_FN;
        if (bi.holes) {
            if (!bi.sig_fn || int(T[bi.sig].args.size()) != bi.holes)
                throw std::runtime_error("block " + b.name + ": sig must take hole arguments");
            bi.hole_types = T[bi.sig].args;
            bi.ret = T[bi.sig].ret;
        } else {
            bi.ret = bi.sig;
        }
        bi.free = free_vars(b.body);
        if (v.by_name.count(b.name_sym)) throw std::runtime_error("duplicate block name " + b.name);
        v.by_name[b.name_sym] = v.blocks.size();
        v.blocks.push_back(bi);
    }
    return v;
}

LibView sub_library(const LibView& lib) {
    LibView v;
    for (const auto& bi : lib.blocks) {
        bool err = false;
        PP body = expand(bi.b->body, &lib, err);
        if (err) continue;
        if (!uses_input(body) && !hole_under_lambda(body, 0) && !free_vars(body)) {
            v.by_name[bi.b->name_sym] = v.blocks.size();
            v.blocks.push_back(bi);
        }
    }
    return v;
}

std::vector<int64_t> task_consts(const std::vector<V>& values) {
    std::set<int64_t> seen{0, 1, -1};
    std::vector<V> stack(values.begin(), values.end());
    Store& S = store();
    while (!stack.empty()) {
        V v = stack.back();
        stack.pop_back();
        if (is_list(v)) {
            seen.insert(int64_t(S.size(v)));
            for (size_t i = 0; i < S.size(v); ++i) stack.push_back(S.data(v)[i]);
        } else if (tag(v) == T_INT) {
            seen.insert(ival(v));
        }
    }
    return {seen.begin(), seen.end()};
}

// ---- ops (lam.build_ops) ----------------------------------------------------------
namespace {
constexpr int MAX_SIZE = 24;
constexpr size_t NEAR_KEEP = 8;
const std::set<int> COMM = {ADD, MUL, MAX, MIN, AND, OR, EQ};

struct Op {
    int name;
    std::vector<int> args;
    int ret;
    int prim;  // -1: block
    const BlockInfo* block;
    std::vector<int> visit;
    std::vector<bool> lam_pos;
    bool comm;
    int arity() const { return int(args.size()); }
};

std::vector<Op> build_ops(Types& T, const LibView& lib, const std::vector<std::pair<int, double>>& order, bool bodies) {
    std::vector<Op> ops;
    auto mk = [&](int name, std::vector<int> args, int ret, int prim, const BlockInfo* b) {
        Op o{name, std::move(args), ret, prim, b, {}, {}, false};
        for (int a : o.args) o.lam_pos.push_back(T[a].k == K_FN);
        for (int i = 0; i < o.arity(); ++i) if (!o.lam_pos[i]) o.visit.push_back(i);
        for (int i = 0; i < o.arity(); ++i) if (o.lam_pos[i]) o.visit.push_back(i);
        o.comm = !b && COMM.count(prim);
        ops.push_back(std::move(o));
    };
    for (int p = 0; p < N_PRIMS; ++p) {
        if (!engine().enabled[p]) continue;
        int sig = T.parse(PRIM_SIGS[p]);
        mk(sym(PRIM_NAMES[p]), T[sig].args, T[sig].ret, p, nullptr);
    }
    for (const auto& b : lib.blocks)
        if (b.holes && !b.free) mk(b.b->name_sym, b.hole_types, b.ret, -1, &b);
    if (bodies) {
        std::vector<Op> keep;
        for (auto& o : ops) if (std::none_of(o.lam_pos.begin(), o.lam_pos.end(), [](bool x) { return x; })) keep.push_back(o);
        ops.swap(keep);
    }
    auto prior = [&](int name) {
        double w = 0;
        for (const auto& kv : order) if (kv.first == name) w = kv.second;
        return -w;
    };
    std::vector<std::pair<double, size_t>> keys;
    for (size_t i = 0; i < ops.size(); ++i) keys.push_back({prior(ops[i].name), i});
    std::stable_sort(keys.begin(), keys.end(), [](const auto& a, const auto& b) { return a.first < b.first; });
    std::vector<Op> out;
    for (const auto& k : keys) out.push_back(ops[k.second]);
    return out;
}

void splits(int total, int k, std::vector<int>& cur, std::vector<std::vector<int>>& out) {
    if (k <= 0) return;
    if (k == 1) {
        if (total >= 1) { cur.push_back(total); out.push_back(cur); cur.pop_back(); }
        return;
    }
    for (int s = 1; s < total - k + 2; ++s) {
        cur.push_back(s);
        splits(total - s, k - 1, cur, out);
        cur.pop_back();
    }
}
const std::vector<std::vector<int>>& splits_cached(int total, int k) {
    thread_local std::map<std::pair<int, int>, std::vector<std::vector<int>>> cache;
    auto key = std::make_pair(total, k);
    auto it = cache.find(key);
    if (it != cache.end()) return it->second;
    std::vector<int> cur;
    std::vector<std::vector<int>> out;
    splits(total, k, cur, out);
    return cache.emplace(key, std::move(out)).first->second;
}

// insertion-ordered type -> list (Python dict[Type, list])
struct Level {
    std::vector<std::pair<int, std::vector<uint32_t>>> by;
    const std::vector<uint32_t>* get(int t) const {
        for (const auto& kv : by) if (kv.first == t) return &kv.second;
        return nullptr;
    }
    std::vector<uint32_t>& at(int t) {
        for (auto& kv : by) if (kv.first == t) return kv.second;
        by.push_back({t, {}});
        return by.back().second;
    }
};

// hash set of (type, vals[n]) over entries stored in a flat array
struct Seen {
    std::vector<int32_t> table;
    size_t used = 0;
    static uint64_t hash(int typ, const V* v, size_t n) {
        uint64_t h = 0x84222325cbf29ce4ull ^ uint64_t(typ);
        for (size_t i = 0; i < n; ++i) { h ^= v[i] + 0x9e3779b97f4a7c15ull + (h << 6) + (h >> 2); h *= 0xff51afd7ed558ccdull; }
        return h;
    }
};

struct LamEntry { PP prog; int node; };

#ifdef HOT_B
using ChooseSubst = Subst;
// unify only appends bindings, including on failure. Restore its insertion count
// at each branch boundary; this also handles early returns and Done exceptions.
struct SubstUndo {
    Subst& subst;
    uint8_t n;
    explicit SubstUndo(Subst& s) : subst(s), n(s.n) {}
    ~SubstUndo() { subst.n = n; }
};
#else
using ChooseSubst = const Subst;
#endif

struct Done {};
struct LamCompileError {};

struct Body { PP prog; int typ; uint32_t voff; int depth; uint32_t seq; };

struct Probe { V x; V a[2]; };

struct BodyPool {
    Types& T;
    std::vector<int> arg_types;
    int n;
    const LibView& lib;
    std::vector<Probe> probes;
    std::vector<int64_t> consts;
    int in_type;  // -1: none
    int lam_depth;
    int body_max;
    std::vector<Op> ops;
    std::vector<Level> bank{Level{}};
    std::vector<Body> bodies;
    std::vector<V> flat;
    std::vector<int32_t> seen_tab;
    size_t seen_n = 0;  // len(self.seen)
    std::map<int, std::vector<std::pair<int, std::vector<LamEntry>>>> lams;
    long* steps_acc;

    BodyPool(Types& T_, std::vector<int> at, const LibView& l, std::vector<Probe> pr, std::vector<int64_t> c,
             int in_t, int ld, int bm, long* acc)
        : T(T_), arg_types(std::move(at)), n(int(arg_types.size())), lib(l), probes(std::move(pr)),
          consts(std::move(c)), in_type(in_t), lam_depth(ld), body_max(bm), steps_acc(acc) {
        static const std::vector<std::pair<int, double>> none;
        ops = build_ops(T, lib, none, true);
        seen_tab.assign(1024, -1);
    }

    size_t np() const { return probes.size(); }

    bool seen_insert(int typ, const V* v, uint32_t idx) {
        size_t N = np();
        uint64_t h = Seen::hash(typ, v, N);
        size_t mask = seen_tab.size() - 1, pos = size_t(h) & mask;
        while (seen_tab[pos] >= 0) {
            const Body& b = bodies[size_t(seen_tab[pos])];
            if (b.typ == typ && std::equal(v, v + N, flat.data() + b.voff)) return false;
            pos = (pos + 1) & mask;
        }
        seen_tab[pos] = int32_t(idx);
        if (++seen_n * 2 > seen_tab.size()) {
            std::vector<int32_t> t2(seen_tab.size() * 2, -1);
            size_t m2 = t2.size() - 1;
            for (size_t k = 0; k < bodies.size(); ++k) {
                const Body& b = bodies[k];
                size_t q = size_t(Seen::hash(b.typ, flat.data() + b.voff, N)) & m2;
                while (t2[q] >= 0) q = (q + 1) & m2;
                t2[q] = int32_t(k);
            }
            {  // the pending entry is not in ``bodies`` yet
                size_t q = size_t(h) & m2;
                while (t2[q] >= 0) q = (q + 1) & m2;
                t2[q] = int32_t(idx);
            }
            seen_tab.swap(t2);
        }
        return true;
    }

    void add(int size, PP prog, int typ, const V* vals, int d) {
        size_t N = np();
        uint32_t idx = uint32_t(bodies.size());
        if (N) {
            bool all_err = true;
            for (size_t j = 0; j < N; ++j) if (vals[j] != ERR) { all_err = false; break; }
            if (all_err) return;
            // stage vals so seen_insert can compare against the flat array
            if (!seen_insert(typ, vals, idx)) return;
        } else {
            ++seen_n;  // programs built here are always distinct (Python key (typ, prog))
        }
        uint32_t voff = uint32_t(flat.size());
        flat.insert(flat.end(), vals, vals + N);
        bodies.push_back({std::move(prog), typ, voff, d, uint32_t(seen_n)});
        bank[size_t(size)].at(typ).push_back(idx);
    }

    const std::vector<std::pair<int, std::vector<LamEntry>>>& lambdas(int body_size) {
        static const std::vector<std::pair<int, std::vector<LamEntry>>> empty;
        if (body_size > body_max) return empty;
        auto it = lams.find(body_size);
        if (it != lams.end()) return it->second;
        while (int(bank.size()) <= body_size) grow(int(bank.size()));
        std::vector<std::pair<int, std::vector<LamEntry>>> got;
        const Syms& S = SY();
        for (const auto& kv : bank[size_t(body_size)].by) {
            std::vector<LamEntry> ls;
            for (uint32_t bi : kv.second) {
                PP prog = p_tup({p_str(S.lam), p_int(n), bodies[bi].prog});
                ls.push_back(make_lam(prog));
            }
            got.push_back({kv.first, std::move(ls)});
        }
        if (body_size == 1) {
            for (const auto& b : lib.blocks) {
                if (b.holes == 0 && b.sig_fn && T[b.sig].args == arg_types)
                    got.push_back({T[b.sig].ret, {make_lam(p_tup({p_str(S.blk), p_str(b.b->name_sym)}))}});
            }
        }
        return lams.emplace(body_size, std::move(got)).first->second;
    }

    LamEntry make_lam(const PP& prog) {
        bool err = false;
        PP e = expand(prog, &lib, err);
        int node = err ? -1 : compile(e);
        if (node < 0) throw LamCompileError{};
        return {prog, node};
    }

    void grow(int size) {
        bank.push_back(Level{});
        size_t N = np();
        std::vector<V> vals(N);
        const Syms& S = SY();
        if (size == 1) {
            for (int k = 0; k < n; ++k) {
                for (size_t j = 0; j < N; ++j) vals[j] = probes[j].a[k];
                add(1, p_leaf(k == 0 ? S.v0 : S.v1), arg_types[size_t(k)], vals.data(), 0);
            }
            if (in_type >= 0) {
                for (size_t j = 0; j < N; ++j) vals[j] = probes[j].x;
                add(1, p_leaf(S.in), in_type, vals.data(), 0);
            }
            for (int64_t c : consts) {
                for (size_t j = 0; j < N; ++j) vals[j] = mk_int(c);
                add(1, p_int(c), T.INT, vals.data(), 0);
            }
            return;
        }
#ifdef HOT_B
        std::vector<uint32_t> chosen;
#endif
        for (const Op& op : ops) {
            for (const auto& comp : splits_cached(size - 1, op.arity())) {
                if (op.comm && comp[0] > comp[1]) continue;
#ifdef HOT_B
                chosen.resize(size_t(op.arity()));
#else
                std::vector<uint32_t> chosen(size_t(op.arity()));
#endif
                Subst s;
                choose(op, comp, 0, s, chosen, size, vals);
            }
        }
    }

    void choose(const Op& op, const std::vector<int>& comp, int i, ChooseSubst& subst,
                std::vector<uint32_t>& chosen, int size, std::vector<V>& vals) {
        if (i == op.arity()) { emit(op, comp, subst, chosen, size, vals); return; }
        int want = resolve(T, op.args[size_t(i)], subst);
        const Level& lv = bank[size_t(comp[size_t(i)])];
        for (size_t t = 0; t < lv.by.size(); ++t) {
#ifdef HOT_B
            SubstUndo undo(subst);
            Subst& s2 = subst;
#else
            Subst s2 = subst;
#endif
            if (!unify(T, want, lv.by[t].first, s2)) continue;
            const auto& list = lv.by[t].second;
            for (size_t q = 0; q < list.size(); ++q) {
                uint32_t bi = list[q];
                if (bodies[bi].depth >= lam_depth) continue;
                chosen[size_t(i)] = bi;
                choose(op, comp, i + 1, s2, chosen, size, vals);
            }
        }
    }

    void emit(const Op& op, const std::vector<int>& comp, const Subst& subst,
              const std::vector<uint32_t>& chosen, int size, std::vector<V>& vals) {
        if (op.comm && comp[0] == comp[1] && bodies[chosen[0]].seq > bodies[chosen[1]].seq) return;
        int d = 0;
        for (uint32_t c : chosen) d = std::max(d, bodies[c].depth);
        d += 1;
        std::vector<PP> kids;
        const Syms& S = SY();
        size_t N = np();
        if (op.block) { kids.push_back(p_str(S.blk)); kids.push_back(p_str(op.name)); }
        else kids.push_back(p_str(op.name));
        for (uint32_t c : chosen) kids.push_back(bodies[c].prog);
        PP prog = p_tup(std::move(kids));
        if (!op.block) {
            Ctx cx{0, MAX_STEPS};
            V a[3];
            for (size_t j = 0; j < N; ++j) {
                bool bad = false;
                for (int k = 0; k < op.arity(); ++k) {
                    a[k] = flat[bodies[chosen[size_t(k)]].voff + j];
                    if (a[k] == ERR) bad = true;
                }
                vals[j] = bad ? ERR : apply_prim(op.prim, a, cx);
            }
        } else {
            eval_block(prog, vals);
        }
        add(size, std::move(prog), resolve(T, op.ret, subst), vals.data(), d);
    }

    void eval_block(const PP& prog, std::vector<V>& vals) {
        size_t N = np();
        bool err = false;
        PP e = expand(prog, &lib, err);
        Arena& A = arena();
        size_t n0 = A.nodes.size(), k0 = A.kids.size();
        int node = err ? -1 : compile(e);
        if (node < 0) {
            for (size_t j = 0; j < N; ++j) vals[j] = ERR;
            A.nodes.resize(n0); A.kids.resize(k0);
            return;
        }
        bool fn = false;
        for (size_t j = 0; j < N; ++j) {
            Ctx cx{probes[j].x, MAX_STEPS};
            vals[j] = eval(node, probes[j].a, n, cx);
            *steps_acc += MAX_STEPS - cx.steps;
            if (tag(vals[j]) == T_FN) fn = true;
        }
        if (!fn) { A.nodes.resize(n0); A.kids.resize(k0); }
    }
};

double elem_score(V got, V want) {
    Store& S = store();
    if (!is_list(got) || !is_list(want) || S.size(got) != S.size(want)) return 0.0;
    long hit = 0, tot = 0;
    size_t n = S.size(got);
    for (size_t i = 0; i < n; ++i) {
        V g = S.data(got)[i], w = S.data(want)[i];
        if (!is_list(g) || !is_list(w) || S.size(g) != S.size(w)) return 0.0;
        tot += long(S.size(w));
        for (size_t k = 0; k < S.size(w); ++k) hit += py_eq(S.data(g)[k], S.data(w)[k]);
    }
    return tot ? double(hit) / double(tot) : 1.0;
}
}  // namespace

// ---- Enumerator (seed/enum.py) ------------------------------------------------------
// ---- forbid (S1): root AST pattern pruning ----------------------------------------
namespace {
thread_local const std::vector<PP>* g_forbid = nullptr;
thread_local long g_forbidden = 0;

// '?'-prefixed STR in a pattern: 0 = not a wildcard, 1 = any subprogram, 2 = int const
int wild_kind(const PN& p) {
    if (p.kind != PN::STR) return 0;
    const std::string& nm = sym_name(p.s);
    if (nm.size() < 2 || nm[0] != '?') return 0;
    return nm[1] == 'c' ? 2 : 1;
}
using Binds = std::vector<std::pair<int, const PN*>>;
bool pn_eq(const PN* a, const PN* b) {
    if (a == b) return true;
    if (a->kind != b->kind) return false;
    switch (a->kind) {
        case PN::INT: return a->i == b->i;
        case PN::STR: return a->s == b->s;
        case PN::TUP:
            if (a->kids.size() != b->kids.size()) return false;
            for (size_t k = 0; k < a->kids.size(); ++k)
                if (!pn_eq(a->kids[k].get(), b->kids[k].get())) return false;
            return true;
        default: return false;
    }
}
bool pmatch(const PN& pat, const PN* prog, Binds& bs) {
    if (int w = wild_kind(pat)) {
        if (w == 2 && prog->kind != PN::INT) return false;
        for (const auto& b : bs)
            if (b.first == pat.s) return pn_eq(b.second, prog);
        bs.push_back({pat.s, prog});
        return true;
    }
    if (pat.kind != prog->kind) return false;
    switch (pat.kind) {
        case PN::INT: return pat.i == prog->i;
        case PN::STR: return pat.s == prog->s;
        case PN::TUP:
            if (pat.kids.size() != prog->kids.size()) return false;
            for (size_t k = 0; k < pat.kids.size(); ++k)
                if (!pmatch(*pat.kids[k], prog->kids[k].get(), bs)) return false;
            return true;
        default: return false;
    }
}
}  // namespace

void set_forbid(const std::vector<PP>* patterns) {
    g_forbid = (patterns && !patterns->empty()) ? patterns : nullptr;
    g_forbidden = 0;
}
long forbid_count() { return g_forbidden; }

struct Enumerator {
    struct Entry { PP prog; int typ; uint32_t voff; uint32_t seq; };
    struct Near { double sc; long nn; PP prog; };  // heap item (sc, -nodes, prog)
    Types& T;
    const LibView& lib;
    const SubProblem& sp;
    size_t n;
    long budget;
    int lam_depth;
    bool keep_near;
    long nodes = 0;
    PP found;
    long nodes_to_first = -1;
    std::vector<Entry> entries;
    std::vector<V> flat;
    std::vector<int32_t> seen_tab;
    size_t seen_n = 0;
    std::vector<Level> bank{Level{}};
    std::vector<Near> near;
    std::vector<Op> ops;
    std::vector<std::vector<const PN*>> op_pats;  // forbid patterns per op (empty unless g_forbid)
    std::map<std::vector<int>, std::unique_ptr<BodyPool>> pools;
    long steps = 0;
    FILE* trace = nullptr;  // ARC_SEED_TRACE=path: every candidate (debugging, one thread)

    Enumerator(Types& T_, const LibView& l, const SubProblem& p, long b, int ld,
               const std::vector<std::pair<int, double>>& order, bool kn)
        : T(T_), lib(l), sp(p), n(p.xs.size()), budget(b), lam_depth(ld), keep_near(kn) {
        ops = build_ops(T, lib, order, false);
        if (g_forbid) {  // patterns whose head and arity fit each op (forbidden_root)
            const int blk = SY().blk;
            op_pats.resize(ops.size());
            for (size_t o = 0; o < ops.size(); ++o) {
                const Op& op = ops[o];
                const size_t k0 = op.block ? 2 : 1;
                for (const PP& pp : *g_forbid) {
                    const PN& p = *pp;
                    if (p.kind != PN::TUP || p.kids.size() != k0 + size_t(op.arity())) continue;
                    auto is = [](const PP& k, int s) { return k->kind == PN::STR && k->s == s; };
                    if (op.block ? !(is(p.kids[0], blk) && is(p.kids[1], op.name)) : !is(p.kids[0], op.name)) continue;
                    op_pats[o].push_back(pp.get());
                }
            }
        }
        seen_tab.assign(1 << 12, -1);
        if (const char* p = std::getenv("ARC_SEED_TRACE")) trace = std::fopen(p, "a");
    }
    ~Enumerator() { if (trace) std::fclose(trace); }

    bool seen_insert(int typ, const V* v, uint32_t idx) {
        uint64_t h = Seen::hash(typ, v, n);
        size_t mask = seen_tab.size() - 1, pos = size_t(h) & mask;
        while (seen_tab[pos] >= 0) {
            const Entry& e = entries[size_t(seen_tab[pos])];
            if (e.typ == typ && std::equal(v, v + n, flat.data() + e.voff)) return false;
            pos = (pos + 1) & mask;
        }
        seen_tab[pos] = int32_t(idx);
        if (++seen_n * 2 > seen_tab.size()) {
            std::vector<int32_t> t2(seen_tab.size() * 2, -1);
            size_t m2 = t2.size() - 1;
            for (size_t k = 0; k < entries.size(); ++k) {
                size_t q = size_t(Seen::hash(entries[k].typ, flat.data() + entries[k].voff, n)) & m2;
                while (t2[q] >= 0) q = (q + 1) & m2;
                t2[q] = int32_t(k);
            }
            {  // the pending entry is not in ``entries`` yet
                size_t q = size_t(h) & m2;
                while (t2[q] >= 0) q = (q + 1) & m2;
                t2[q] = int32_t(idx);
            }
            seen_tab.swap(t2);
        }
        return true;
    }

    template <class F>
    void offer(int size, F&& make_prog, int typ, const V* vals) {
        ++nodes;
        uint32_t idx = uint32_t(entries.size());
        if (seen_insert(typ, vals, idx)) {
            uint32_t voff = uint32_t(flat.size());
            flat.insert(flat.end(), vals, vals + n);
            entries.push_back({make_prog(), typ, voff, uint32_t(seen_n)});
            bank[size_t(size)].at(typ).push_back(idx);
            const Entry& e = entries.back();
            if (typ == sp.out_type && std::equal(vals, vals + n, sp.outs.begin())) {
                found = e.prog;
                nodes_to_first = nodes;
                throw Done{};
            }
            if (typ == T.INPUT && !sp.sub && keep_near) {
                // Python 3.12 sum() of floats: Neumaier compensated summation
                double sc = 0, comp = 0;
                for (size_t j = 0; j < n; ++j) {
                    double x = elem_score(vals[j], sp.outs[j]);
                    double t = sc + x;
                    if (std::fabs(sc) >= std::fabs(x)) comp += (sc - t) + x;
                    else comp += (x - t) + sc;
                    sc = t;
                }
                if (comp != 0 && std::isfinite(comp)) sc += comp;
                sc /= double(n);
                Near item{sc, -nodes, e.prog};
                auto less = [](const Near& a, const Near& b) { return a.sc < b.sc || (a.sc == b.sc && a.nn < b.nn); };
                if (near.size() < NEAR_KEEP) near.push_back(item);
                else {
                    auto mn = std::min_element(near.begin(), near.end(), less);
                    if (less(*mn, item)) *mn = item;
                }
            }
        }
        if (nodes >= budget) throw Done{};
    }

    bool run_expanded(const PP& prog, std::vector<V>& vals) {
        bool err = false;
        PP e = expand(prog, &lib, err);
        if (err) return false;
        Arena& A = arena();
        size_t n0 = A.nodes.size(), k0 = A.kids.size();
        int node = compile(e);
        bool ok = node >= 0, fn = false;
        for (size_t j = 0; ok && j < n; ++j) {
            Ctx cx{sp.xs[j], MAX_STEPS};
            vals[j] = eval(node, nullptr, 0, cx);
            steps += MAX_STEPS - cx.steps;
            if (vals[j] == ERR) ok = false;
            else if (tag(vals[j]) == T_FN) fn = true;
        }
        if (!fn) { A.nodes.resize(n0); A.kids.resize(k0); }
        return ok;
    }

    void run() {
        bank.push_back(Level{});
        const Syms& S = SY();
        std::vector<V> vals(n);
        PP in = p_leaf(S.in);
        offer(1, [&] { return in; }, sp.in_type, sp.xs.data());
        for (int64_t c : sp.consts) {
            for (size_t j = 0; j < n; ++j) vals[j] = mk_int(c);
            offer(1, [&] { return p_int(c); }, T.INT, vals.data());
        }
        for (const auto& b : lib.blocks) {
            if (b.holes == 0 && !b.sig_fn && !b.free) {
                PP prog = p_tup({p_str(S.blk), p_str(b.b->name_sym)});
                if (run_expanded(prog, vals)) offer(1, [&] { return prog; }, b.sig, vals.data());
            }
        }
        for (const auto& ex : sp.extra) offer(1, [&] { return std::get<0>(ex); }, std::get<1>(ex), std::get<2>(ex).data());
        for (int size = 2; size <= MAX_SIZE; ++size) {
            bank.push_back(Level{});
            for (const Op& op : ops) {
                for (const auto& comp : splits_cached(size - 1, op.arity())) {
                    if (op.comm && comp[0] > comp[1]) continue;
                    apply(size, op, comp, vals);
                }
            }
        }
    }

    // chosen[pos]: entry index, or lam pointer
    struct Pick { uint32_t entry; const LamEntry* lam; };

#ifdef HOT_B
    std::vector<Pick> picks;
#endif

    void apply(int size, const Op& op, const std::vector<int>& comp, std::vector<V>& vals) {
#ifdef HOT_B
        // apply is not reentrant on one Enumerator (BodyPools are separate).
        picks.assign(size_t(op.arity()), Pick{0, nullptr});
        Subst subst;
        choose(size, op, comp, 0, subst, picks, vals);
#else
        std::vector<Pick> chosen(size_t(op.arity()), Pick{0, nullptr});
        choose(size, op, comp, 0, Subst{}, chosen, vals);
#endif
    }

    void choose(int size, const Op& op, const std::vector<int>& comp, int i, ChooseSubst& subst,
                std::vector<Pick>& chosen, std::vector<V>& vals) {
        if (i == op.arity()) { emit(size, op, comp, subst, chosen, vals); return; }
        int pos = op.visit[size_t(i)];
        int want = resolve(T, op.args[size_t(pos)], subst);
        int sz = comp[size_t(pos)];
        if (T[want].k == K_FN) {
#ifdef HOT_B
            const std::vector<int>& wargs = T[want].args;
#else
            std::vector<int> wargs = T[want].args;
#endif
            int wret = T[want].ret;
            BodyPool* pool = get_pool(wargs);
            if (!pool) return;
            const auto& ls = pool->lambdas(sz);
            for (const auto& kv : ls) {
#ifdef HOT_B
                SubstUndo undo(subst);
                Subst& s2 = subst;
#else
                Subst s2 = subst;
#endif
                if (!unify(T, wret, kv.first, s2)) continue;
                for (const auto& lam : kv.second) {
                    chosen[size_t(pos)] = Pick{0, &lam};
                    choose(size, op, comp, i + 1, s2, chosen, vals);
                }
            }
            return;
        }
        const Level& lv = bank[size_t(sz)];
        for (size_t t = 0; t < lv.by.size(); ++t) {
#ifdef HOT_B
            SubstUndo undo(subst);
            Subst& s2 = subst;
#else
            Subst s2 = subst;
#endif
            if (!unify(T, want, lv.by[t].first, s2)) continue;
            const auto& list = lv.by[t].second;
            for (size_t q = 0; q < list.size(); ++q) {
                chosen[size_t(pos)] = Pick{list[q], nullptr};
                choose(size, op, comp, i + 1, s2, chosen, vals);
            }
        }
    }

    // Root of build_prog(op, chosen) matches a forbid pattern (without building it).
    bool forbidden_root(const Op& op, const std::vector<Pick>& chosen) const {
        const size_t k0 = op.block ? 2 : 1, ar = chosen.size();
        Binds bs;
        for (const PN* pp : op_pats[size_t(&op - ops.data())]) {
            const PN& p = *pp;
            bs.clear();
            bool ok = true;
            for (size_t k = 0; ok && k < ar; ++k) {
                const PN* kid = chosen[k].lam ? chosen[k].lam->prog.get() : entries[chosen[k].entry].prog.get();
                ok = pmatch(*p.kids[k0 + k], kid, bs);
            }
            if (ok) return true;
        }
        return false;
    }

    PP build_prog(const Op& op, const std::vector<Pick>& chosen) {
        const Syms& S = SY();
        std::vector<PP> kids;
        if (op.block) { kids.push_back(p_str(S.blk)); kids.push_back(p_str(op.name)); }
        else kids.push_back(p_str(op.name));
        for (const auto& c : chosen) kids.push_back(c.lam ? c.lam->prog : entries[c.entry].prog);
        return p_tup(std::move(kids));
    }

    void emit(int size, const Op& op, const std::vector<int>& comp, const Subst& subst,
              const std::vector<Pick>& chosen, std::vector<V>& vals) {
        if (op.comm && comp[0] == comp[1] && entries[chosen[0].entry].seq > entries[chosen[1].entry].seq) return;
        if (g_forbid && !op_pats[size_t(&op - ops.data())].empty() && forbidden_root(op, chosen)) {
            ++g_forbidden;
            return;
        }
        int ret = resolve(T, op.ret, subst);
        bool ok;
        if (!op.block) ok = eval_prim(op, chosen, vals);
        else ok = run_expanded(build_prog(op, chosen), vals);
        if (trace) fprintf(trace, "%ld %c %s\n", nodes + 1, ok ? 'o' : 'f', to_json(build_prog(op, chosen)).dump().c_str());
        if (ok) {
            offer(size, [&] { return build_prog(op, chosen); }, ret, vals.data());
        } else {
            ++nodes;
            if (nodes >= budget) throw Done{};
        }
    }

    bool eval_prim(const Op& op, const std::vector<Pick>& chosen, std::vector<V>& vals) {
        V a[3];
#ifdef HOT_B
        // Resolve invariant entry metadata once per candidate, before examples.
        uint32_t offsets[3]{};
        int lam_nodes[3];
        for (int k = 0; k < op.arity(); ++k) {
            const Pick& pick = chosen[size_t(k)];
            lam_nodes[k] = pick.lam ? pick.lam->node : -1;
            if (!pick.lam) offsets[k] = entries[pick.entry].voff;
        }
#ifdef HOT_E
        bool no_lambda = true;
        for (int k = 0; k < op.arity(); ++k) no_lambda = no_lambda && lam_nodes[k] < 0;
        if (no_lambda) {
            // These cases neither allocate lists nor consume evaluation steps.
            // Failure writes ERR at the same example and leaves the suffix alone.
            switch (op.prim) {
#define HOT_E_BATCH(P) case P: return hot_e::scalar_batch<P>(flat.data(), offsets, n, vals.data())
            HOT_E_BATCH(ADD); HOT_E_BATCH(SUB); HOT_E_BATCH(MUL); HOT_E_BATCH(NEG);
            HOT_E_BATCH(MOD); HOT_E_BATCH(EQ); HOT_E_BATCH(LT); HOT_E_BATCH(MAX);
            HOT_E_BATCH(MIN); HOT_E_BATCH(AND); HOT_E_BATCH(OR); HOT_E_BATCH(NOT);
            HOT_E_BATCH(IF); HOT_E_BATCH(LEN); HOT_E_BATCH(NTH); HOT_E_BATCH(HEAD);
            HOT_E_BATCH(LAST); HOT_E_BATCH(COUNT);
#undef HOT_E_BATCH
            default: break;
            }
        }
#endif
#endif
        for (size_t j = 0; j < n; ++j) {
            Ctx cx{sp.xs[j], MAX_STEPS};
            for (int k = 0; k < op.arity(); ++k) {
#ifdef HOT_B
                if (lam_nodes[k] < 0) a[k] = flat[offsets[k] + j];
                else {
                    a[k] = eval(lam_nodes[k], nullptr, 0, cx);
#else
                const Pick& c = chosen[size_t(k)];
                if (!c.lam) a[k] = flat[entries[c.entry].voff + j];
                else {
                    a[k] = eval(c.lam->node, nullptr, 0, cx);  // LamEntry.bind(x)
#endif
                    if (a[k] == ERR) return false;
                }
            }
            vals[j] = apply_prim(op.prim, a, cx);
            steps += MAX_STEPS - cx.steps;
            if (vals[j] == ERR) return false;
        }
        return true;
    }

    BodyPool* get_pool(const std::vector<int>& arg_types) {
        for (int t : arg_types) if (!T[t].ground) return nullptr;
        auto it = pools.find(arg_types);
        if (it != pools.end()) return it->second.get();
#ifdef HOT_B
        // A reference to T[want].args can be invalidated by probes() growing T.
        // Copy only on a pool miss, before probes() or BodyPool construction.
        const std::vector<int> owned_args = arg_types;
        auto pool = std::make_unique<BodyPool>(T, owned_args, lib, probes(owned_args), sp.consts,
#else
        auto pool = std::make_unique<BodyPool>(T, arg_types, lib, probes(arg_types), sp.consts,
#endif
                                               sp.sub ? -1 : sp.in_type, lam_depth, sp.lam_body_max, &steps);
        BodyPool* p = pool.get();
#ifdef HOT_B
        pools.emplace(owned_args, std::move(pool));
#else
        pools.emplace(arg_types, std::move(pool));
#endif
        return p;
    }

    std::vector<Probe> probes(const std::vector<int>& arg_types) {
        std::vector<std::vector<std::pair<V, V>>> per;
        for (int t : arg_types) per.push_back(probe_values(t));
        for (const auto& p : per) if (p.empty()) return {};
        std::vector<Probe> out;
        if (per.size() == 1) {
            for (const auto& vx : per[0]) out.push_back(Probe{vx.second, {vx.first, 0}});
            return out;
        }
        const auto& a = per[0];
        const auto& b = per[1];
        size_t m = std::max(a.size(), b.size());
        for (size_t i = 0; i < m; ++i)
            out.push_back(Probe{a[i % a.size()].second, {a[i % a.size()].first, b[i % b.size()].first}});
        for (size_t i = 0; i < std::min<size_t>(3, a.size()); ++i)
            for (size_t k = 0; k < std::min<size_t>(3, b.size()); ++k)
                out.push_back(Probe{a[i].second, {a[i].first, b[k].first}});
        return out;
    }

    std::vector<std::pair<V, V>> probe_values(int t, size_t cap = 10) {
        std::vector<std::pair<V, V>> out;
        std::set<V> seen;  // (type(v), v): the tag is part of the handle
        auto add = [&](V v, V x) {
            if (!seen.count(v) && out.size() < cap) { seen.insert(v); out.push_back({v, x}); }
        };
        Store& S = store();
        int lt = T.list(t);
        for (size_t size = 1; size < std::min<size_t>(4, bank.size()); ++size) {
            if (const auto* es = bank[size].get(t))
                for (uint32_t ei : *es)
                    for (size_t j = 0; j < n; ++j) add(flat[entries[ei].voff + j], sp.xs[j]);
            if (const auto* es = bank[size].get(lt))
                for (uint32_t ei : *es)
                    for (size_t j = 0; j < n; ++j) {
                        V vs = flat[entries[ei].voff + j];
                        size_t L = std::min<size_t>(6, S.size(vs));
                        for (size_t k = 0; k < L; ++k) add(S.data(vs)[k], sp.xs[j]);
                    }
        }
        if (t == T.INT) for (int64_t c : {0, 1, -1}) add(mk_int(c), sp.xs[0]);
        if (t == T.BOOL) { add(mk_bool(true), sp.xs[0]); add(mk_bool(false), sp.xs[0]); }
        return out;
    }

    std::vector<std::pair<PP, double>> near_sorted() const {
        std::vector<Near> v = near;
        std::sort(v.begin(), v.end(), [](const Near& a, const Near& b) { return a.sc > b.sc || (a.sc == b.sc && a.nn > b.nn); });
        std::vector<std::pair<PP, double>> out;
        for (const auto& x : v) out.push_back({x.prog, x.sc});
        return out;
    }

    // seed/cond.py cond_witness
    PP cond_witness(long limit, long& used) {
        constexpr size_t MAX_ELSE = 12;
        size_t W = (n + 63) / 64;
        using Mask = std::vector<uint64_t>;
        Mask full(W, 0);
        for (size_t j = 0; j < n; ++j) full[j / 64] |= 1ull << (j % 64);
        std::vector<std::pair<Mask, uint32_t>> outs, bools;
        for (const auto& level : bank) {
            if (const auto* es = level.get(sp.out_type))
                for (uint32_t ei : *es) {
                    Mask m(W, 0); bool any = false;
                    for (size_t j = 0; j < n; ++j)
                        if (py_eq(flat[entries[ei].voff + j], sp.outs[j])) { m[j / 64] |= 1ull << (j % 64); any = true; }
                    if (any) outs.push_back({m, ei});
                }
            if (const auto* es = level.get(T.BOOL))
                for (uint32_t ei : *es) {
                    Mask m(W, 0); bool any = false; bool all = true;
                    for (size_t j = 0; j < n; ++j) {
                        V v = flat[entries[ei].voff + j];
                        if (tag(v) == T_BOOL && ival(v) == 1) { m[j / 64] |= 1ull << (j % 64); any = true; }
                        else all = false;
                    }
                    if (any && !all) bools.push_back({m, ei});
                }
        }
        auto pop = [](const Mask& m) { long c = 0; for (auto w : m) c += __builtin_popcountll(w); return c; };
        std::vector<size_t> elses(outs.size());
        for (size_t i = 0; i < elses.size(); ++i) elses[i] = i;
        std::stable_sort(elses.begin(), elses.end(), [&](size_t a, size_t b) { return pop(outs[a].first) > pop(outs[b].first); });
        used = 0;
        const Syms& S = SY();
        (void)S;
        for (size_t ii = 0; ii < std::min(MAX_ELSE, elses.size()); ++ii) {
            const auto& me = outs[elses[ii]];
            Mask need(W);
            for (size_t w = 0; w < W; ++w) need[w] = full[w] & ~me.first[w];
            for (const auto& mt : outs) {
                bool covers = true;
                for (size_t w = 0; w < W; ++w) if ((mt.first[w] & need[w]) != need[w]) { covers = false; break; }
                if (!covers || p_eq(entries[mt.second].prog, entries[me.second].prog)) continue;
                Mask wrong(W);
                for (size_t w = 0; w < W; ++w) wrong[w] = full[w] & ~mt.first[w];
                ++used;
                if (used > limit) { used = limit; return nullptr; }
                for (const auto& bm : bools) {
                    bool ok = true;
                    for (size_t w = 0; w < W && ok; ++w)
                        if ((bm.first[w] & need[w]) != need[w] || (bm.first[w] & wrong[w]) != 0) ok = false;
                    if (ok)
                        return p_tup({p_str(sym("if")), entries[bm.second].prog, entries[mt.second].prog,
                                      entries[me.second].prog});
                }
            }
        }
        return nullptr;
    }
};

DirectOut run_enum(Types& T, const LibView& lib, const SubProblem& sp, long budget, int lam_depth,
                   const std::vector<std::pair<int, double>>& order, bool use_cond, long cond_budget,
                   bool keep_near, bool cond_absolute) {
    Enumerator en(T, lib, sp, budget, lam_depth, order, keep_near);
    try { en.run(); } catch (const Done&) {}
    DirectOut out;
    out.prog = en.found;
    out.nodes = en.nodes;
    out.first = en.nodes_to_first;
    if (!en.found && use_cond) {
        long used = 0;
        PP p = en.cond_witness(cond_absolute ? cond_budget : cond_budget - en.nodes, used);
        out.cond_used = used;
        if (p) { out.prog = p; out.cond_hit = true; }
    }
    if (keep_near) out.near = en.near_sorted();
    out.eval_steps = en.steps;
    return out;
}
}  // namespace seed
