// Seed values, types, primitives and interpreter (mirrors seed/prims.py,
// seed/types.py, seed/interp.py).
#include "seed_value.hpp"
#include <algorithm>
#include <mutex>
#include <stdexcept>

namespace seed {

// ---- symbols -----------------------------------------------------------------
namespace {
std::mutex sym_mu;
std::vector<std::string>& sym_tab() { static std::vector<std::string> t; return t; }
std::unordered_map<std::string, int>& sym_idx() { static std::unordered_map<std::string, int> m; return m; }
}
int sym(const std::string& s) {
    std::lock_guard<std::mutex> g(sym_mu);
    auto& m = sym_idx();
    auto it = m.find(s);
    if (it != m.end()) return it->second;
    int id = int(sym_tab().size());
    sym_tab().push_back(s);
    m.emplace(s, id);
    return id;
}
const std::string& sym_name(int id) { return sym_tab()[size_t(id)]; }

// ---- program trees ---------------------------------------------------------------
PP p_int(int64_t v) { auto n = std::make_shared<PN>(); n->kind = PN::INT; n->i = v; return n; }
PP p_str(int s) { auto n = std::make_shared<PN>(); n->kind = PN::STR; n->s = s; return n; }
PP p_tup(std::vector<PP> kids) { auto n = std::make_shared<PN>(); n->kind = PN::TUP; n->kids = std::move(kids); return n; }
PP p_leaf(int s) { return p_tup({p_str(s)}); }

PP from_json(const arc::Json& j) {
    if (std::holds_alternative<double>(j.value)) return p_int(int64_t(std::get<double>(j.value)));
    if (std::holds_alternative<std::string>(j.value)) {
        // Python from_json on a bare string makes a tuple of characters.
        std::vector<PP> k;
        for (char ch : j.str()) k.push_back(p_str(sym(std::string(1, ch))));
        return p_tup(std::move(k));
    }
    if (j.array()) {
        std::vector<PP> k;
        for (const auto& x : j.items()) {
            if (std::holds_alternative<std::string>(x.value)) k.push_back(p_str(sym(x.str())));
            else k.push_back(from_json(x));
        }
        return p_tup(std::move(k));
    }
    auto n = std::make_shared<PN>(); n->kind = PN::BAD; return n;  // bool/null/object
}

arc::Json to_json(const PP& p) {
    switch (p->kind) {
    case PN::INT: return arc::Json(double(p->i));
    case PN::STR: return arc::Json(sym_name(p->s));
    case PN::TUP: {
        arc::Json::Array a;
        for (const auto& k : p->kids) a.push_back(to_json(k));
        return arc::Json(std::move(a));
    }
    default: return arc::Json();
    }
}

bool p_eq(const PP& a, const PP& b) {
    if (a == b) return true;
    if (a->kind != b->kind) return false;
    switch (a->kind) {
    case PN::INT: return a->i == b->i;
    case PN::STR: return a->s == b->s;
    case PN::TUP:
        if (a->kids.size() != b->kids.size()) return false;
        for (size_t i = 0; i < a->kids.size(); ++i) if (!p_eq(a->kids[i], b->kids[i])) return false;
        return true;
    default: return false;
    }
}

// ---- value store -------------------------------------------------------------
Store& store() { thread_local Store s; return s; }

void Store::reset() {
    elems.clear(); off.clear(); len.clear(); boolish.clear(); hashes.clear();
    table.assign(1 << 12, -1); used = 0;
    elems.reserve(1 << 20);
}

static inline uint64_t mix(uint64_t h, uint64_t v) { return (h ^ v) * 0x100000001b3ull; }

V Store::make(const V* p, size_t n) {
    if (table.empty()) table.assign(1 << 12, -1);
    uint64_t h = 1469598103934665603ull ^ n;
    for (size_t i = 0; i < n; ++i) h = mix(h, p[i]);
    h ^= h >> 29;
    h *= 0xbf58476d1ce4e5b9ull;
    h ^= h >> 32;
    size_t mask = table.size() - 1, pos = size_t(h) & mask;
    while (true) {
        int32_t id = table[pos];
        if (id < 0) break;
        if (hashes[size_t(id)] == h && len[size_t(id)] == n &&
            std::equal(p, p + n, elems.data() + off[size_t(id)]))
            return (uint64_t(id) << 3) | T_LIST;
        pos = (pos + 1) & mask;
    }
    uint32_t id = uint32_t(off.size());
    off.push_back(uint32_t(elems.size()));
    len.push_back(uint32_t(n));
    hashes.push_back(h);
    uint8_t b = 0;
    for (size_t i = 0; i < n; ++i) {
        elems.push_back(p[i]);
        if (tag(p[i]) == T_BOOL || (tag(p[i]) == T_LIST && boolish[lid(p[i])])) b = 1;
    }
    boolish.push_back(b);
    table[pos] = int32_t(id);
    if (++used * 2 > table.size()) {
        std::vector<int32_t> t2(table.size() * 2, -1);
        size_t m2 = t2.size() - 1;
        for (uint32_t k = 0; k < off.size(); ++k) {
            size_t q = size_t(hashes[k]) & m2;
            while (t2[q] >= 0) q = (q + 1) & m2;
            t2[q] = int32_t(k);
        }
        table.swap(t2);
    }
    return (uint64_t(id) << 3) | T_LIST;
}

bool py_eq(V a, V b) {
    if (a == b) return true;
    unsigned ta = tag(a), tb = tag(b);
    if (ta <= T_BOOL && tb <= T_BOOL) return ival(a) == ival(b);
    if (ta == T_LIST && tb == T_LIST) {
        Store& S = store();
        if (!S.boolish[lid(a)] && !S.boolish[lid(b)]) return false;
        size_t n = S.size(a);
        if (S.size(b) != n) return false;
        for (size_t i = 0; i < n; ++i)
            if (!py_eq(S.data(a)[i], S.data(b)[i])) return false;
        return true;
    }
    return false;
}

int py_lt(V a, V b) {
    unsigned ta = tag(a), tb = tag(b);
    if (ta <= T_BOOL && tb <= T_BOOL) return ival(a) < ival(b);
    if (ta == T_LIST && tb == T_LIST) {
        Store& S = store();
        size_t na = S.size(a), nb = S.size(b);
        for (size_t i = 0; i < na && i < nb; ++i) {
            V x = S.data(a)[i], y = S.data(b)[i];
            if (!py_eq(x, y)) return py_lt(x, y);
        }
        return na < nb;
    }
    return -1;
}

bool truthy(V v) {
    switch (tag(v)) {
    case T_INT: case T_BOOL: return ival(v) != 0;
    case T_LIST: return store().size(v) != 0;
    default: return true;
    }
}

V from_data(const arc::Json& j) {
    if (std::holds_alternative<bool>(j.value)) return mk_bool(std::get<bool>(j.value));
    if (std::holds_alternative<double>(j.value)) return mk_int(int64_t(std::get<double>(j.value)));
    if (j.array()) {
        std::vector<V> v;
        for (const auto& x : j.items()) v.push_back(from_data(x));
        return store().make(v.data(), v.size());
    }
    return ERR;
}

arc::Json to_data(V v) {
    switch (tag(v)) {
    case T_INT: return arc::Json(double(ival(v)));
    case T_BOOL: return arc::Json(bool(ival(v)));
    case T_LIST: {
        Store& S = store();
        arc::Json::Array a;
        size_t n = S.size(v);
        for (size_t i = 0; i < n; ++i) a.push_back(to_data(S.data(v)[i]));
        return arc::Json(std::move(a));
    }
    case T_FN: return arc::Json("<function>");
    default: return arc::Json("ERR");
    }
}

// ---- types ---------------------------------------------------------------------
Types::Types() {
    INT = make(K_INT, -1, {}, -1);
    BOOL = make(K_BOOL, -1, {}, -1);
    INPUT = list(list(INT));
}

int Types::make(TK k, int a, std::vector<int> args, int ret) {
    std::string key(1, char('0' + k));
    key += std::to_string(a) + ":" + std::to_string(ret) + ":";
    for (int x : args) key += std::to_string(x) + ",";
    auto it = index.find(key);
    if (it != index.end()) return it->second;
    TNode n{k, a, std::move(args), ret, true};
    if (k == K_VAR) n.ground = false;
    else if (k == K_LIST) n.ground = nodes[size_t(a)].ground;
    else if (k == K_FN) {
        n.ground = nodes[size_t(ret)].ground;
        for (int x : n.args) n.ground = n.ground && nodes[size_t(x)].ground;
    }
    int id = int(nodes.size());
    nodes.push_back(std::move(n));
    index.emplace(std::move(key), id);
    return id;
}

namespace {
struct TParser {
    Types& T; std::vector<std::string> toks; size_t i = 0;
    void fail() { throw std::runtime_error("bad type"); }
    const std::string& at(size_t k) { if (k >= toks.size()) fail(); return toks[k]; }
    int atom() {
        const std::string& name = at(i);
        if (name == "int") { ++i; return T.INT; }
        if (name == "bool") { ++i; return T.BOOL; }
        if (name == "list") {
            if (at(i + 1) != "[") fail();
            i += 2;
            int e = parse();
            if (at(i) != "]") fail();
            ++i;
            return T.list(e);
        }
        ++i;
        return T.var(sym(name));
    }
    int parse() {
        if (i < toks.size() && toks[i] == "(") {
            std::vector<int> args;
            ++i;
            while (at(i) != ")") {
                args.push_back(parse());
                if (at(i) == ",") ++i;
            }
            ++i;
            if (i < toks.size() && toks[i] == "->") {
                ++i;
                int r = parse();
                return T.make(K_FN, -1, args, r);
            }
            if (args.size() != 1) fail();
            return args[0];
        }
        int head = atom();
        if (i < toks.size() && toks[i] == "->") {
            ++i;
            int r = parse();
            return T.make(K_FN, -1, {head}, r);
        }
        return head;
    }
};
}

int Types::parse(const std::string& text) {
    TParser p{*this, {}, 0};
    for (size_t i = 0; i < text.size();) {
        char c = text[i];
        if (isspace((unsigned char)c)) { ++i; continue; }
        if (text.compare(i, 2, "->") == 0) { p.toks.push_back("->"); i += 2; continue; }
        if (std::strchr("[](),", c)) { p.toks.push_back(std::string(1, c)); ++i; continue; }
        size_t j = i;
        while (j < text.size() && (isalnum((unsigned char)text[j]) || text[j] == '_')) ++j;
        if (j == i) throw std::runtime_error("bad type");
        p.toks.push_back(text.substr(i, j - i));
        i = j;
    }
    int t = p.parse();
    if (p.i != p.toks.size()) throw std::runtime_error("bad type");
    return t;
}

static const int* lookup(const Subst& s, int var) {
    for (const auto& kv : s) if (kv.first == var) return &kv.second;
    return nullptr;
}

int resolve(Types& T, int t, const Subst& s) {
    const TNode& n = T[t];
    if (n.ground) return t;
    if (n.k == K_VAR) {
        const int* b = lookup(s, t);
        return b ? resolve(T, *b, s) : t;
    }
    if (n.k == K_LIST) { int e = n.a; return T.list(resolve(T, e, s)); }
    std::vector<int> args;
    std::vector<int> src = n.args;
    int ret = n.ret;
    for (int a : src) args.push_back(resolve(T, a, s));
    int r = resolve(T, ret, s);
    return T.make(K_FN, -1, std::move(args), r);
}

static int walk(const Types& T, int t, const Subst& s) {
    while (T[t].k == K_VAR) {
        const int* b = lookup(s, t);
        if (!b) break;
        t = *b;
    }
    return t;
}

static bool occurs(Types& T, int var, int t, const Subst& s) {
    t = resolve(T, t, s);
    const TNode& n = T[t];
    if (n.k == K_VAR) return t == var;
    if (n.k == K_LIST) return occurs(T, var, n.a, s);
    if (n.k == K_FN) {
        std::vector<int> args = n.args; int ret = n.ret;
        for (int a : args) if (occurs(T, var, a, s)) return true;
        return occurs(T, var, ret, s);
    }
    return false;
}

bool unify(Types& T, int a, int b, Subst& s) {
    a = walk(T, a, s);
    b = walk(T, b, s);
    if (a == b) return true;
    if (T[a].k == K_VAR) {
        if (occurs(T, a, b, s)) return false;
        s.emplace_back(a, b);
        return true;
    }
    if (T[b].k == K_VAR) return unify(T, b, a, s);
    if (T[a].k == K_LIST && T[b].k == K_LIST) return unify(T, T[a].a, T[b].a, s);
    if (T[a].k == K_FN && T[b].k == K_FN) {
        if (T[a].args.size() != T[b].args.size()) return false;
        std::vector<int> aa = T[a].args, bb = T[b].args;
        int ar = T[a].ret, br = T[b].ret;
        for (size_t i = 0; i < aa.size(); ++i) if (!unify(T, aa[i], bb[i], s)) return false;
        return unify(T, ar, br, s);
    }
    return false;
}

// ---- primitives ------------------------------------------------------------------
const char* PRIM_NAMES[N_PRIMS] = {
    "add", "sub", "mul", "neg", "mod", "eq", "lt", "max", "min", "and", "or", "not", "if",
    "len", "nth", "head", "last", "take", "drop", "reverse", "cons", "append", "concat",
    "range", "repeat", "count", "sort", "map", "filter", "zipwith", "fold", "transpose"};
const char* PRIM_SIGS[N_PRIMS] = {
    "(int, int) -> int", "(int, int) -> int", "(int, int) -> int", "(int) -> int",
    "(int, int) -> int", "(a, a) -> bool", "(int, int) -> bool", "(int, int) -> int",
    "(int, int) -> int", "(bool, bool) -> bool", "(bool, bool) -> bool", "(bool) -> bool",
    "(bool, a, a) -> a", "(list[a]) -> int", "(list[a], int) -> a", "(list[a]) -> a",
    "(list[a]) -> a", "(int, list[a]) -> list[a]", "(int, list[a]) -> list[a]",
    "(list[a]) -> list[a]", "(a, list[a]) -> list[a]", "(list[a], list[a]) -> list[a]",
    "(list[list[a]]) -> list[a]", "(int) -> list[int]", "(int, a) -> list[a]",
    "(a, list[a]) -> int", "(list[a]) -> list[a]", "((a) -> b, list[a]) -> list[b]",
    "((a) -> bool, list[a]) -> list[a]", "((a, b) -> c, list[a], list[b]) -> list[c]",
    "((b, a) -> b, b, list[a]) -> b", "(list[list[a]]) -> list[list[a]]"};
const int PRIM_ARITY[N_PRIMS] = {2, 2, 2, 1, 2, 2, 2, 2, 2, 2, 2, 1, 3, 1, 2, 1, 1, 2, 2, 1,
                                 2, 2, 1, 1, 2, 2, 1, 2, 2, 3, 3, 1};

int prim_of_sym(int s) {
    static std::vector<int> table;
    static std::once_flag once;
    std::call_once(once, [] {
        for (int p = 0; p < N_PRIMS; ++p) {
            int id = sym(PRIM_NAMES[p]);
            if (size_t(id) >= table.size()) table.resize(size_t(id) + 1, -1);
            table[size_t(id)] = p;
        }
    });
    if (s < 0 || size_t(s) >= table.size()) return -1;
    return table[size_t(s)];
}

Engine& engine() {
    thread_local Engine e = [] { Engine x; for (bool& b : x.enabled) b = true; return x; }();
    return e;
}

void set_exclude(const std::vector<std::string>& names) {
    Engine& e = engine();
    for (bool& b : e.enabled) b = true;
    for (const auto& n : names) {
        int p = prim_of_sym(sym(n));
        if (p < 0) throw std::runtime_error("unknown primitive " + n);
        e.enabled[p] = false;
    }
}

constexpr int64_t MAX_INT = 1000000000;
constexpr size_t MAX_LEN = 1024;

static inline V chk_int(int64_t v) { return (v >= -MAX_INT && v <= MAX_INT) ? mk_int(v) : ERR; }

static thread_local std::vector<V> tmpbuf_pool[8];
static thread_local int tmpdepth = 0;
struct Tmp {  // reentrant scratch vectors for building lists
    std::vector<V>* v;
    Tmp() { v = &tmpbuf_pool[std::min(tmpdepth, 7)]; if (tmpdepth >= 7) v = new std::vector<V>(); ++tmpdepth; v->clear(); }
    ~Tmp() { --tmpdepth; if (tmpdepth >= 7) delete v; }
};

V apply_prim(int p, const V* a, Ctx& c) {
    Store& S = store();
    switch (p) {
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
    case TAKE: case DROP: {
        if (!is_num(a[0])) return ERR;  // max(n, 0) with a list n raises
        if (!is_list(a[1])) return ERR;
        int64_t n = std::max<int64_t>(ival(a[0]), 0);
        size_t L = S.size(a[1]);
        size_t k = size_t(std::min<int64_t>(n, int64_t(L)));
        if (p == TAKE) { if (k == L) return a[1]; Tmp t; t.v->assign(S.data(a[1]), S.data(a[1]) + k); return S.make(t.v->data(), k); }
        if (k == 0) return a[1];
        Tmp t; t.v->assign(S.data(a[1]) + k, S.data(a[1]) + L); return S.make(t.v->data(), t.v->size());
    }
    case REVERSE: {
        if (!is_list(a[0])) return ERR;
        Tmp t; const V* d = S.data(a[0]); size_t n = S.size(a[0]);
        t.v->assign(d, d + n); std::reverse(t.v->begin(), t.v->end());
        return S.make(t.v->data(), n);
    }
    case CONS: {
        if (!is_list(a[1])) return ERR;
        size_t n = S.size(a[1]);
        if (n + 1 > MAX_LEN) return ERR;
        Tmp t; t.v->push_back(a[0]); t.v->insert(t.v->end(), S.data(a[1]), S.data(a[1]) + n);
        return S.make(t.v->data(), n + 1);
    }
    case APPEND: {
        if (!is_list(a[0]) || !is_list(a[1])) return ERR;
        size_t n = S.size(a[0]), m = S.size(a[1]);
        if (n + m > MAX_LEN) return ERR;
        Tmp t; t.v->assign(S.data(a[0]), S.data(a[0]) + n); t.v->insert(t.v->end(), S.data(a[1]), S.data(a[1]) + m);
        return S.make(t.v->data(), n + m);
    }
    case CONCAT: {
        if (!is_list(a[0])) return ERR;
        size_t n = S.size(a[0]), tot = 0;
        for (size_t i = 0; i < n; ++i) { V x = S.data(a[0])[i]; if (!is_list(x)) return ERR; tot += S.size(x); }
        if (tot > MAX_LEN) return ERR;
        Tmp t;
        for (size_t i = 0; i < n; ++i) { V x = S.data(a[0])[i]; t.v->insert(t.v->end(), S.data(x), S.data(x) + S.size(x)); }
        return S.make(t.v->data(), tot);
    }
    case RANGE: {
        if (!is_num(a[0])) return ERR;
        int64_t n = ival(a[0]);
        if (n > int64_t(MAX_LEN)) return ERR;
        Tmp t; for (int64_t i = 0; i < n; ++i) t.v->push_back(mk_int(i));
        return S.make(t.v->data(), t.v->size());
    }
    case REPEAT: {
        if (!is_num(a[0])) return ERR;
        int64_t n = ival(a[0]);
        if (n > int64_t(MAX_LEN)) return ERR;
        Tmp t; for (int64_t i = 0; i < n; ++i) t.v->push_back(a[1]);
        return S.make(t.v->data(), t.v->size());
    }
    case COUNT: {
        if (!is_list(a[1])) return ERR;
        int64_t k = 0; size_t n = S.size(a[1]);
        for (size_t i = 0; i < n; ++i) k += py_eq(S.data(a[1])[i], a[0]);
        return mk_int(k);
    }
    case SORT: {
        if (!is_list(a[0])) return ERR;
        Tmp t; size_t n = S.size(a[0]); t.v->assign(S.data(a[0]), S.data(a[0]) + n);
        bool ints = true;
        for (V x : *t.v) if (tag(x) != T_INT) { ints = false; break; }
        if (ints) {  // fast path: plain integers (same order as py_lt)
            std::stable_sort(t.v->begin(), t.v->end(), [](V x, V y) { return ival(x) < ival(y); });
            return S.make(t.v->data(), n);
        }
        bool bad = false;
        std::stable_sort(t.v->begin(), t.v->end(), [&](V x, V y) {
            int r = py_lt(x, y); if (r < 0) { bad = true; return false; } return r == 1; });
        if (bad) return ERR;
        return S.make(t.v->data(), n);
    }
    case MAP: case FILTER: {
        if (!is_list(a[1])) return ERR;
        size_t n = S.size(a[1]);
        Tmp t;
        for (size_t i = 0; i < n; ++i) {
            V x = S.data(a[1])[i];  // stable: store elems may grow, re-read via index
            V r = call(a[0], &x, 1, c);
            if (r == ERR) return ERR;
            if (p == MAP) t.v->push_back(r);
            else if (truthy(r)) t.v->push_back(S.data(a[1])[i]);
        }
        return S.make(t.v->data(), t.v->size());
    }
    case ZIPWITH: {
        if (!is_list(a[1]) || !is_list(a[2])) return ERR;
        size_t n = std::min(S.size(a[1]), S.size(a[2]));
        Tmp t;
        for (size_t i = 0; i < n; ++i) {
            V xy[2] = {S.data(a[1])[i], S.data(a[2])[i]};
            V r = call(a[0], xy, 2, c);
            if (r == ERR) return ERR;
            t.v->push_back(r);
        }
        return S.make(t.v->data(), n);
    }
    case FOLD: {
        if (!is_list(a[2])) return ERR;
        V acc = a[1];
        size_t n = S.size(a[2]);
        for (size_t i = 0; i < n; ++i) {
            V xy[2] = {acc, S.data(a[2])[i]};
            acc = call(a[0], xy, 2, c);
            if (acc == ERR) return ERR;
        }
        return acc;
    }
    case TRANSPOSE: {
        if (!is_list(a[0])) return ERR;
        size_t n = S.size(a[0]), w = 0;
        for (size_t i = 0; i < n; ++i) { V x = S.data(a[0])[i]; if (!is_list(x)) return ERR; w = std::max(w, S.size(x)); }
        Tmp rows;
        for (size_t j = 0; j < w; ++j) {
            Tmp col;
            for (size_t i = 0; i < n; ++i) { V x = S.data(a[0])[i]; if (j < S.size(x)) col.v->push_back(S.data(x)[j]); }
            rows.v->push_back(S.make(col.v->data(), col.v->size()));
        }
        return S.make(rows.v->data(), w);
    }
    }
    return ERR;
}

// ---- interpreter -----------------------------------------------------------------
Arena& arena() { thread_local Arena a; return a; }

V call(V f, const V* args, int n, Ctx& c) {
    if (tag(f) != T_FN) return ERR;
    const CNode& lam = arena().nodes[lid(f)];
    return eval(arena().kids[size_t(lam.k0)], args, n, c);
}

V eval(int ni, const V* env, int envn, Ctx& c) {
    Arena& A = arena();
    const CNode n = A.nodes[size_t(ni)];
    switch (n.kind) {
    case C_CONST: return mk_int(n.c);
    case C_INPUT: return c.input;
    case C_VAR: return int(n.c) < envn ? env[n.c] : ERR;
    case C_LAM: return mk_fn(uint32_t(ni));
    default: break;
    }
    if (--c.steps < 0) return ERR;
    V a[3];
    for (int k = 0; k < n.nk; ++k) {
        a[k] = eval(A.kids[size_t(n.k0 + k)], env, envn, c);
        if (a[k] == ERR) return ERR;
    }
    return apply_prim(n.prim, a, c);
}

namespace {
struct Syms { int in, v0, v1, lam, blk, h0, h1, i; };
const Syms& S_() {
    static Syms s{sym("$in"), sym("$0"), sym("$1"), sym("lam"), sym("blk"), sym("$h0"), sym("$h1"), sym("$i")};
    return s;
}
int compile_rec(const PP& p, bool& err) {
    Arena& A = arena();
    if (err) return -1;
    if (p->kind == PN::INT) {
        A.nodes.push_back({C_CONST, 0, 0, 0, p->i});
        return int(A.nodes.size() - 1);
    }
    if (p->kind != PN::TUP || p->kids.empty()) { err = true; return -1; }
    const PP& h = p->kids[0];
    const Syms& S = S_();
    if (h->kind == PN::STR) {
        if (h->s == S.in) { A.nodes.push_back({C_INPUT, 0, 0, 0, 0}); return int(A.nodes.size() - 1); }
        if (h->s == S.v0 || h->s == S.v1) { A.nodes.push_back({C_VAR, 0, 0, 0, h->s == S.v1 ? 1 : 0}); return int(A.nodes.size() - 1); }
        if (h->s == S.lam) {
            if (p->kids.size() < 3) { err = true; return -1; }
            const PP& n = p->kids[1];
            if (n->kind != PN::INT || (n->i != 1 && n->i != 2)) { err = true; return -1; }
            int body = compile_rec(p->kids[2], err);
            if (err) return -1;
            A.kids.push_back(body);
            A.nodes.push_back({C_LAM, 0, 1, int32_t(A.kids.size() - 1), n->i});
            return int(A.nodes.size() - 1);
        }
    }
    int prim = h->kind == PN::STR ? prim_of_sym(h->s) : -1;
    if (prim < 0 || !engine().enabled[prim]) { err = true; return -1; }
    if (int(p->kids.size()) - 1 != PRIM_ARITY[prim]) { err = true; return -1; }
    int ks[3];
    for (size_t k = 1; k < p->kids.size(); ++k) { ks[k - 1] = compile_rec(p->kids[k], err); if (err) return -1; }
    int32_t k0 = int32_t(A.kids.size());
    for (int k = 0; k < PRIM_ARITY[prim]; ++k) A.kids.push_back(ks[k]);
    A.nodes.push_back({C_APP, uint8_t(prim), uint8_t(PRIM_ARITY[prim]), k0, 0});
    return int(A.nodes.size() - 1);
}
}

int compile(const PP& p) {
    bool err = false;
    int r = compile_rec(p, err);
    return err ? -1 : r;
}

PP substitute(const PP& body, const std::vector<PP>& args, bool& err) {
    if (err) return body;
    if (body->kind == PN::INT) return body;
    if (body->kind != PN::TUP) return body;
    const Syms& S = S_();
    if (body->kids.size() == 1) {
        const PP& h = body->kids[0];
        if (h->kind == PN::STR && (h->s == S.h0 || h->s == S.h1)) {
            size_t k = h->s == S.h1 ? 1 : 0;
            if (k >= args.size()) { err = true; return body; }
            return args[k];
        }
        return body;
    }
    if (body->kids.empty()) { err = true; return body; }
    const PP& h = body->kids[0];
    if (h->kind == PN::STR && h->s == S.lam) {
        if (body->kids.size() < 3) { err = true; return body; }
        return p_tup({body->kids[0], body->kids[1], substitute(body->kids[2], args, err)});
    }
    std::vector<PP> k{h};
    for (size_t i = 1; i < body->kids.size(); ++i) {
        const PP& x = body->kids[i];
        if (x->kind == PN::STR) { err = true; return body; }  // see README: blk names never reach here
        k.push_back(substitute(x, args, err));
    }
    return p_tup(std::move(k));
}
}  // namespace seed
