// Seed values, types and interpreter internals (shared by seed_*.cpp).
#pragma once
#include "seed.hpp"
#include <cstring>
#include <stdexcept>
#include <unordered_map>

namespace seed {

// ---- values: 64-bit handles ------------------------------------------------
// tag (low 3 bits): 0 int, 1 bool, 2 list (interned id), 3 closure (node id),
// 4 ERR. Lists are hash-consed per thread, so equal lists of one element type
// have equal handles; py_eq handles Python's True == 1 across element types.
using V = uint64_t;
constexpr V ERR = 4;
enum Tag : unsigned { T_INT = 0, T_BOOL = 1, T_LIST = 2, T_FN = 3, T_ERR = 4 };
inline unsigned tag(V v) { return unsigned(v & 7); }
inline V mk_int(int64_t i) { return (uint64_t(i) << 3) | T_INT; }
inline V mk_bool(bool b) { return (uint64_t(b) << 3) | T_BOOL; }
inline V mk_fn(uint32_t node) { return (uint64_t(node) << 3) | T_FN; }
inline int64_t ival(V v) { return int64_t(v) >> 3; }
inline bool is_num(V v) { return tag(v) <= T_BOOL; }
inline bool is_list(V v) { return tag(v) == T_LIST; }
inline uint32_t lid(V v) { return uint32_t(v >> 3); }

struct Store {
    std::vector<V> elems;
    std::vector<uint32_t> off, len;
    std::vector<uint8_t> boolish;  // contains a bool somewhere (for py_eq)
    std::vector<uint64_t> hashes;
    std::vector<int32_t> table;    // open addressing: list id or -1
    size_t used = 0;
    void reset();
    V make(const V* p, size_t n);
    const V* data(V v) const { return elems.data() + off[lid(v)]; }
    size_t size(V v) const { return len[lid(v)]; }
};
Store& store();  // thread-local

bool py_eq(V a, V b);
int py_lt(V a, V b);  // 1 true, 0 false, -1 TypeError
bool truthy(V v);

// ---- types -----------------------------------------------------------------
enum TK : uint8_t { K_INT, K_BOOL, K_LIST, K_FN, K_VAR };
struct TNode { TK k; int a = -1; std::vector<int> args; int ret = -1; bool ground = true; };
struct Types {  // per solve (thread)
    std::vector<TNode> nodes;
    std::unordered_map<std::string, int> index;
    int INT, BOOL, INPUT;
    Types();
    int make(TK k, int a, std::vector<int> args, int ret);
    std::vector<int> list_of;  // elem id -> list type id (fast path)
    int list(int e) {
        if (size_t(e) < list_of.size() && list_of[size_t(e)] >= 0) return list_of[size_t(e)];
        int t = make(K_LIST, e, {}, -1);
        if (size_t(e) >= list_of.size()) list_of.resize(size_t(e) + 1, -1);
        list_of[size_t(e)] = t;
        return t;
    }
    int var(int symid) { return make(K_VAR, symid, {}, -1); }
    int parse(const std::string& text);
    const TNode& operator[](int t) const { return nodes[t]; }
};
// var type id -> type id, insertion order (a Python dict); small and on the stack
struct Subst {
    uint8_t n = 0;
    std::pair<int, int> kv[12];
    void emplace_back(int a, int b) {
        if (n >= 12) throw std::runtime_error("substitution too large");
        kv[n++] = {a, b};
    }
    const std::pair<int, int>* begin() const { return kv; }
    const std::pair<int, int>* end() const { return kv + n; }
};
int resolve(Types& T, int t, const Subst& s);
bool unify(Types& T, int a, int b, Subst& s);  // extends s in place; false: no unifier

// ---- primitives ------------------------------------------------------------
enum Prim : uint8_t {
    ADD, SUB, MUL, NEG, MOD, EQ, LT, MAX, MIN, AND, OR, NOT, IF, LEN, NTH, HEAD, LAST,
    TAKE, DROP, REVERSE, CONS, APPEND, CONCAT, RANGE, REPEAT, COUNT, SORT, MAP, FILTER,
    ZIPWITH, FOLD, TRANSPOSE, N_PRIMS
};
extern const char* PRIM_NAMES[N_PRIMS];
extern const char* PRIM_SIGS[N_PRIMS];
extern const int PRIM_ARITY[N_PRIMS];
int prim_of_sym(int s);  // -1 if not a primitive name

// ---- interpreter -------------------------------------------------------------
constexpr long MAX_STEPS = 200000;
struct Ctx { V input; long steps; };
struct CNode { uint8_t kind; uint8_t prim; uint8_t nk; int32_t k0; int64_t c; };
enum CK : uint8_t { C_CONST, C_INPUT, C_VAR, C_LAM, C_APP };
struct Arena {
    std::vector<CNode> nodes;
    std::vector<int32_t> kids;
    void reset() { nodes.clear(); kids.clear(); }
};
Arena& arena();  // thread-local

// thread-local engine state: enabled primitives (seed.prims.without)
struct Engine { bool enabled[N_PRIMS]; };
Engine& engine();
void set_exclude(const std::vector<std::string>& names);

V apply_prim(int p, const V* a, Ctx& c);
V call(V f, const V* args, int n, Ctx& c);
V eval(int node, const V* env, int envn, Ctx& c);
int compile(const PP& p);  // -1 on EvalError

struct LibView;  // block lookup for expand
PP expand(const PP& p, const LibView* lib, bool& err);
PP substitute(const PP& body, const std::vector<PP>& args, bool& err);

V from_data(const arc::Json& j);
arc::Json to_data(V v);
}  // namespace seed
