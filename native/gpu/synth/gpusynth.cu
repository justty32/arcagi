// E11 (reports/gpusynth-1110/): GPU "reverse synthesis" of training samples, v2.
// Each GPU thread takes an ARC training input grid (stratified: grid = global thread index mod #grids),
// grows a random typed postfix program over 28 first-order seed primitives
// (add sub mul neg mod eq lt max min and or not if len nth head last take drop reverse transpose
//  cons append concat range repeat count sort), evaluating eagerly while it grows, and keeps the
// program if it ends as one non-empty 0..9 grid different from the input.
// Diversity (v2): target length in [mint, maxt] drawn uniformly per thread (depth strata), reverse/transpose/take/drop
// down-weighted, no immediate reverse∘reverse / transpose∘transpose / sort∘sort / neg∘neg / not∘not,
// host dedup by output fingerprint (grid index, output grid) keeping the shortest program.
// Semantics follow native/src/seed_value.cpp; the typed model is stricter (rejects some programs the CPU
// accepts, e.g. ragged grids, mixed-kind if, values outside int8) but accepted samples must match the CPU
// exactly: checked by gpusynth_verify (verify.cpp) against seed::eval.
// usage: gpusynth --grids g.bin --names names.json --seconds S --batch N --write N --out f.jsonl
//                 [--maxt 12] [--mint 4] [--mark 30] [--stratum-cap 0] [--dedup 1]
// Output jsonl rows {"task","ex","prog" (seed s-expr),"out"}; summary json on stdout (with a snapshot at --mark s).
#include <cuda_runtime.h>
#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <map>
#include <string>
#include <unordered_map>
#include <vector>

#define HD __host__ __device__
constexpr int MAXC = 900, MAXT = 20, SD = 5;
enum Kind : uint8_t { KI, KB, KL1, KL2 };
enum Tok : uint8_t { T_IN, T_C, ADD, SUB, MUL, NEG, MOD, EQ, LT, MAX, MIN, AND, OR, NOT, IF, LEN, NTH, HEAD, LAST,
                     TAKE, DROP, REVERSE, TRANSPOSE, CONS, APPEND, CONCAT, RANGE, REPEAT, COUNT, SORT, NTOK };
static const char* TN[NTOK] = {"$in", "", "add", "sub", "mul", "neg", "mod", "eq", "lt", "max", "min", "and", "or",
                               "not", "if", "len", "nth", "head", "last", "take", "drop", "reverse", "transpose",
                               "cons", "append", "concat", "range", "repeat", "count", "sort"};
HD inline int arity(int t) {
    switch (t) {
    case T_IN: case T_C: return 0;
    case NEG: case NOT: case LEN: case HEAD: case LAST: case REVERSE: case TRANSPOSE: case CONCAT: case RANGE: case SORT: return 1;
    case IF: return 3;
    default: return 2;
    }
}
struct Val { uint8_t k; uint16_t h, w; int64_t iv; int8_t c[MAXC]; };   // L1: h=1, w=len; L2: h x w (h=0 => w=0)
struct Grid { uint32_t off; int32_t task; int16_t ex; uint8_t h, w; };
struct Sample { int32_t grid; uint8_t ntok, h, w, pad; uint8_t tok[MAXT]; int8_t cst[MAXT]; int8_t c[MAXC]; };

__device__ __forceinline__ uint64_t rng(uint64_t& s) { s ^= s << 13; s ^= s >> 7; s ^= s << 17; return s; }
__device__ __forceinline__ uint64_t mix(uint64_t z) {
    z += 0x9e3779b97f4a7c15ull; z = (z ^ (z >> 30)) * 0xbf58476d1ce4e5b9ull; z = (z ^ (z >> 27)) * 0x94d049bb133111ebull;
    return z ^ (z >> 31);
}
HD inline bool isL(const Val& v) { return v.k == KL1 || v.k == KL2; }
HD inline int llen(const Val& v) { return v.k == KL1 ? v.w : v.h; }
HD inline int ncell(const Val& v) { return v.k == KL1 ? v.w : v.h * v.w; }
HD inline bool okint(int64_t x) { return x <= 1000000000 && x >= -1000000000; }
HD inline bool ok8(int64_t x) { return x >= -128 && x <= 127; }
// applicable by type? (stack top at st[sp-1])
HD bool can(int t, const Val* st, int sp) {
    const Val *a = sp >= 1 ? &st[sp - 1] : nullptr, *b = sp >= 2 ? &st[sp - 2] : nullptr;
    switch (t) {
    case T_IN: case T_C: return sp < SD;
    case ADD: case SUB: case MUL: case MOD: case EQ: case LT: case MAX: case MIN: return b && a->k == KI && b->k == KI;
    case NEG: case RANGE: return a && a->k == KI;
    case AND: case OR: return b && a->k == KB && b->k == KB;
    case NOT: return a && a->k == KB;
    case IF: return sp >= 3 && st[sp - 3].k == KB && a->k == b->k;
    case LEN: case REVERSE: case SORT: return a && isL(*a);
    case HEAD: case LAST: return a && isL(*a) && llen(*a) > 0;
    case NTH: return b && isL(*b) && a->k == KI;
    case TAKE: case DROP: return b && b->k == KI && isL(*a);
    case TRANSPOSE: return a && a->k == KL2 && a->h > 0;
    case CONS: return b && ((b->k == KI && a->k == KL1) || (b->k == KL1 && a->k == KL2));
    case APPEND: return b && ((b->k == KL1 && a->k == KL1) || (b->k == KL2 && a->k == KL2));
    case CONCAT: return a && a->k == KL2;
    case REPEAT: return b && b->k == KI && (a->k == KI || a->k == KL1);
    case COUNT: return b && b->k == KI && a->k == KL1;
    }
    return false;
}
HD inline void copyc(int8_t* d, const int8_t* s, int n) { for (int i = 0; i < n; ++i) d[i] = s[i]; }
// apply token t to the stack (in place); false = runtime error or outside the typed model
HD bool step(int t, int cst, Val* st, int& sp, const int8_t* in, int ih, int iw) {
    if (t == T_IN) { Val& v = st[sp++]; v.k = KL2; v.h = ih; v.w = iw; copyc(v.c, in, ih * iw); return true; }
    if (t == T_C) { Val& v = st[sp++]; v.k = KI; v.iv = cst; return true; }
    Val& a = st[sp - 1];
    if (arity(t) == 1) {
        switch (t) {
        case NEG: a.iv = -a.iv; return true;
        case NOT: a.iv = !a.iv; return true;
        case LEN: a.iv = llen(a); a.k = KI; return true;
        case HEAD: case LAST: {
            int i = t == HEAD ? 0 : llen(a) - 1;
            if (a.k == KL1) { a.iv = a.c[i]; a.k = KI; }
            else { int w = a.w; for (int j = 0; j < w; ++j) a.c[j] = a.c[i * w + j]; a.k = KL1; a.h = 1; }
            return true; }
        case REVERSE: {
            int n = llen(a), w = a.k == KL1 ? 1 : a.w;
            for (int i = 0; i < n / 2; ++i) for (int j = 0; j < w; ++j) { int8_t x = a.c[i * w + j]; a.c[i * w + j] = a.c[(n - 1 - i) * w + j]; a.c[(n - 1 - i) * w + j] = x; }
            return true; }
        case TRANSPOSE: {
            int8_t tmp[MAXC]; int h = a.h, w = a.w;
            for (int i = 0; i < h; ++i) for (int j = 0; j < w; ++j) tmp[j * h + i] = a.c[i * w + j];
            copyc(a.c, tmp, h * w);
            if (w == 0) { a.h = 0; a.w = 0; } else { a.h = w; a.w = h; }
            return true; }
        case CONCAT: { int n = a.h * a.w; a.k = KL1; a.h = 1; a.w = n; return true; }
        case RANGE: {
            int64_t n = a.iv; if (n > 128) return false; if (n < 0) n = 0;
            for (int i = 0; i < n; ++i) a.c[i] = int8_t(i);
            a.k = KL1; a.h = 1; a.w = int(n); return true; }
        case SORT: {
            if (a.k == KL1) {  // ints: counting sort (same order as stable sort)
                int cnt[256]; for (int i = 0; i < 256; ++i) cnt[i] = 0;
                for (int i = 0; i < a.w; ++i) cnt[a.c[i] + 128]++;
                int p = 0; for (int v = 0; v < 256; ++v) for (int k = 0; k < cnt[v]; ++k) a.c[p++] = int8_t(v - 128);
                return true;
            }
            int h = a.h, w = a.w; if (h > 64) return false;
            uint8_t idx[64]; for (int i = 0; i < h; ++i) idx[i] = uint8_t(i);
            for (int i = 1; i < h; ++i) {  // stable insertion sort, lexicographic rows
                uint8_t x = idx[i]; int j = i - 1;
                while (j >= 0) {
                    int r = 0; for (int q = 0; q < w; ++q) { int8_t u = a.c[idx[j] * w + q], v = a.c[x * w + q]; if (u != v) { r = u > v ? 1 : -1; break; } }
                    if (r <= 0) break;
                    idx[j + 1] = idx[j]; --j;
                }
                idx[j + 1] = x;
            }
            int8_t tmp[MAXC]; for (int i = 0; i < h; ++i) copyc(tmp + i * w, a.c + idx[i] * w, w);
            copyc(a.c, tmp, h * w); return true; }
        }
        return false;
    }
    if (arity(t) == 3) {  // if c x y  (postfix: c x y)
        Val& c = st[sp - 3]; bool cond = c.iv != 0;
        Val& src = cond ? st[sp - 2] : st[sp - 1];
        c.k = src.k; c.h = src.h; c.w = src.w; c.iv = src.iv;
        if (isL(src)) copyc(c.c, src.c, ncell(src));
        sp -= 2; return true;
    }
    Val& b = st[sp - 2];  // binary: op(b, a); result into b
    int64_t x = b.iv, y = a.iv, r = 0;
    switch (t) {
    case ADD: r = x + y; break; case SUB: r = x - y; break; case MUL: r = x * y; break;
    case MOD: if (y == 0) return false; r = x % y; if (r != 0 && ((r < 0) != (y < 0))) r += y; break;
    case MAX: r = x < y ? y : x; break; case MIN: r = y < x ? y : x; break;
    case EQ: b.iv = x == y; b.k = KB; sp--; return true;
    case LT: b.iv = x < y; b.k = KB; sp--; return true;
    case AND: b.iv = x ? y : x; sp--; return true;
    case OR: b.iv = x ? x : y; sp--; return true;
    case NTH: {
        int n = llen(b); if (y < 0 || y >= n) return false;
        if (b.k == KL1) { b.iv = b.c[y]; b.k = KI; }
        else { int w = b.w; for (int j = 0; j < w; ++j) b.c[j] = b.c[y * w + j]; b.k = KL1; b.h = 1; }
        sp--; return true; }
    case TAKE: case DROP: {  // b = n (int), a = list -> result into b slot; n < 0 acts as 0 (seed_value max(n,0))
        int n = llen(a); int k = x < 0 ? 0 : (x > n ? n : int(x));
        int w = a.k == KL1 ? 1 : a.w, lo = t == TAKE ? 0 : k, cnt = t == TAKE ? k : n - k;
        copyc(b.c, a.c + lo * w, cnt * w);
        b.k = a.k; if (a.k == KL1) { b.h = 1; b.w = cnt; } else { b.h = cnt; b.w = cnt ? a.w : 0; }
        sp--; return true; }
    case CONS: {
        if (b.k == KI) {  // cons(int, L1)
            if (!ok8(x) || a.w + 1 > MAXC) return false;
            int8_t v = int8_t(x); for (int i = a.w; i > 0; --i) a.c[i] = a.c[i - 1]; a.c[0] = v;
            b.k = KL1; b.h = 1; b.w = a.w + 1; copyc(b.c, a.c, b.w); sp--; return true;
        }
        int w = b.w;  // cons(row, L2): uniform width only
        if (w == 0 || (a.h > 0 && a.w != w) || (a.h + 1) * w > MAXC) return false;
        for (int i = a.h * w - 1; i >= 0; --i) a.c[i + w] = a.c[i];
        copyc(a.c, b.c, w);
        b.k = KL2; b.h = a.h + 1; b.w = w; copyc(b.c, a.c, b.h * w); sp--; return true; }
    case APPEND: {
        if (b.k == KL1) { if (b.w + a.w > MAXC) return false; copyc(b.c + b.w, a.c, a.w); b.w += a.w; sp--; return true; }
        if (a.h == 0) { sp--; return true; }
        if (b.h == 0) { b.h = a.h; b.w = a.w; copyc(b.c, a.c, a.h * a.w); sp--; return true; }
        if (a.w != b.w || (a.h + b.h) * b.w > MAXC) return false;
        copyc(b.c + b.h * b.w, a.c, a.h * a.w); b.h += a.h; sp--; return true; }
    case REPEAT: {
        int64_t n = x < 0 ? 0 : x;
        if (a.k == KI) {
            if (!ok8(y) || n > MAXC) return false;
            for (int i = 0; i < n; ++i) b.c[i] = int8_t(y);
            b.k = KL1; b.h = 1; b.w = int(n); sp--; return true;
        }
        int w = a.w;
        if (n > 0 && (w == 0 || n * w > MAXC)) return false;
        for (int i = 0; i < n; ++i) copyc(b.c + i * w, a.c, w);
        b.k = KL2; b.h = int(n); b.w = n ? w : 0; sp--; return true; }
    case COUNT: { int64_t k = 0; for (int i = 0; i < a.w; ++i) k += a.c[i] == x; b.iv = k; sp--; return true; }
    }
    if (!okint(r)) return false;
    b.iv = r; sp--; return true;
}
__device__ int weight(int t, int sp, int prev) {
    if (sp == 0) return t == T_IN ? 8 : 1;
    if (t == prev && (t == REVERSE || t == TRANSPOSE || t == SORT || t == NEG || t == NOT)) return 0;
    switch (t) {
    case REVERSE: case TRANSPOSE: case TAKE: case DROP: return 1;
    case T_IN: return sp >= 2 ? 1 : 2;
    case T_C: return sp >= 3 ? 1 : 4;
    default: return 4;
    }
}
__global__ void synth(const int8_t* cells, const Grid* grids, int ngrids, uint64_t seed, uint64_t base, int maxt, int mint,
                      Sample* out, unsigned* nout, unsigned cap) {
    uint64_t tid = blockIdx.x * uint64_t(blockDim.x) + threadIdx.x;
    uint64_t s = mix(seed ^ (tid * 0x9e3779b97f4a7c15ull)) | 1;
    int gi = int((base + tid) % uint64_t(ngrids));
    const Grid g = grids[gi]; const int8_t* in = cells + g.off;
    Val st[SD], snap; int sp = 0, snapn = 0; uint8_t tok[MAXT]; int8_t cst[MAXT]; int nt = 0, prev = -1;
    int target = mint + int(rng(s) % uint64_t(maxt - mint + 1));  // depth stratum: stop at first valid state at/after it
    for (; nt < maxt; ) {
        int cand[NTOK], cw[NTOK], nc = 0, tw = 0;
        bool late = nt >= target;  // past the depth target: stop pushing so the stack folds to one value
        for (int pass = 0; pass < 2 && !nc; ++pass, late = false)
            for (int t = 0; t < NTOK; ++t) if (can(t, st, sp)) {
                int w = weight(t, sp, prev); if (late && (t == T_IN || t == T_C)) w = 0;
                if (w) { cand[nc] = t; cw[nc++] = w; tw += w; } }
        if (!nc) return;
        int r = int(rng(s) % uint64_t(tw)), i = 0; while (r >= cw[i]) r -= cw[i++];
        int t = cand[i]; int c = t == T_C ? int(rng(s) % 10) : 0;
        if (!step(t, c, st, sp, in, g.h, g.w)) return;
        tok[nt] = uint8_t(t); cst[nt] = int8_t(c); ++nt; prev = t;
        if (sp == 1 && st[0].k == KL2 && st[0].h > 0 && st[0].w > 0 && st[0].h < 256 && st[0].w < 256 && nt >= mint) {
            if (nt >= target) { snapn = 0; break; }
            snap.k = KL2; snap.h = st[0].h; snap.w = st[0].w; copyc(snap.c, st[0].c, st[0].h * st[0].w); snapn = nt;
        }
    }
    // fall back to the last valid prefix (>= mint tokens) if the walk ended in an unusable state
    bool fin = sp == 1 && st[0].k == KL2 && st[0].h > 0 && st[0].w > 0 && st[0].h < 256 && st[0].w < 256 && nt >= mint;
    if (!fin) { if (!snapn) return; nt = snapn; }
    const Val& v = fin ? st[0] : snap;
    for (int i = 0; i < v.h * v.w; ++i) if (v.c[i] < 0 || v.c[i] > 9) return;
    if (v.h == g.h && v.w == g.w) { bool same = true; for (int i = 0; i < g.h * g.w && same; ++i) same = v.c[i] == in[i]; if (same) return; }
    unsigned k = atomicAdd(nout, 1u); if (k >= cap) return;
    Sample& o = out[k]; o.grid = gi; o.ntok = nt; o.h = v.h; o.w = v.w;
    for (int i = 0; i < nt; ++i) { o.tok[i] = tok[i]; o.cst[i] = cst[i]; }
    copyc(o.c, v.c, v.h * v.w);
}
#define CK(x) do { cudaError_t e_ = (x); if (e_ != cudaSuccess) { fprintf(stderr, "cuda %s line %d\n", cudaGetErrorString(e_), __LINE__); return 1; } } while (0)
struct Prog { int32_t grid; uint8_t ntok; uint8_t tok[MAXT]; int8_t cst[MAXT]; };
static std::string prog_json(const Prog& s) {
    std::vector<std::string> st;
    for (int i = 0; i < s.ntok; ++i) {
        int t = s.tok[i];
        if (t == T_IN) { st.push_back("[\"$in\"]"); continue; }
        if (t == T_C) { st.push_back(std::to_string(int(s.cst[i]))); continue; }
        std::string e = std::string("[\"") + TN[t] + "\"";
        size_t base = st.size() - arity(t);
        for (size_t j = base; j < st.size(); ++j) e += "," + st[j];
        st.resize(base); st.push_back(e + "]");
    }
    return st.back();
}
static uint64_t fp(int grid, int h, int w, const int8_t* c) {
    uint64_t z = 1469598103934665603ull ^ (uint64_t(uint32_t(grid)) * 0x9e3779b97f4a7c15ull) ^ (uint64_t(h) << 40 | uint64_t(w) << 48);
    for (int j = 0; j < h * w; ++j) z = (z ^ uint8_t(c[j])) * 1099511628211ull;
    z ^= z >> 29; z *= 0xbf58476d1ce4e5b9ull; return z ^ (z >> 32);
}
int main(int argc, char** argv) {
    std::string gpath, npath, opath = "synth.jsonl"; double secs = 10, mark = 30; long batch = 1 << 18, wcap = 100000;
    int maxt = 12, mint = 4, dedup = 1; long scap = 0;
    for (int i = 1; i + 1 < argc; i += 2) {
        std::string a = argv[i];
        if (a == "--grids") gpath = argv[i + 1]; else if (a == "--names") npath = argv[i + 1];
        else if (a == "--out") opath = argv[i + 1]; else if (a == "--seconds") secs = atof(argv[i + 1]);
        else if (a == "--batch") batch = atol(argv[i + 1]); else if (a == "--write") wcap = atol(argv[i + 1]);
        else if (a == "--maxt") maxt = std::max(2, std::min(MAXT, atoi(argv[i + 1])));
        else if (a == "--mark") mark = atof(argv[i + 1]); else if (a == "--stratum-cap") scap = atol(argv[i + 1]);
        else if (a == "--mint") mint = atoi(argv[i + 1]);
        else if (a == "--dedup") dedup = atoi(argv[i + 1]);
    }
    mint = std::max(2, std::min(maxt, mint));
    FILE* f = fopen(gpath.c_str(), "rb"); if (!f) { fprintf(stderr, "no grids\n"); return 1; }
    int32_t n; if (fread(&n, 4, 1, f) != 1) return 1;
    std::vector<Grid> grids(n); std::vector<int8_t> cells;
    for (int i = 0; i < n; ++i) {
        int32_t t; int16_t e; uint8_t hw[2];
        if (fread(&t, 4, 1, f) != 1 || fread(&e, 2, 1, f) != 1 || fread(hw, 1, 2, f) != 2) return 1;
        grids[i] = Grid{uint32_t(cells.size()), t, e, hw[0], hw[1]};
        cells.resize(cells.size() + hw[0] * hw[1]);
        if (fread(cells.data() + grids[i].off, 1, hw[0] * hw[1], f) != size_t(hw[0] * hw[1])) return 1;
    }
    fclose(f);
    std::vector<std::string> names;  // names.json: ["id", ...]
    { FILE* g = fopen(npath.c_str(), "rb"); std::string s; char buf[4096]; size_t r;
      while (g && (r = fread(buf, 1, sizeof buf, g)) > 0) s.append(buf, r); if (g) fclose(g);
      for (size_t p = 0; (p = s.find('"', p)) != std::string::npos;) { size_t q = s.find('"', p + 1); names.push_back(s.substr(p + 1, q - p - 1)); p = q + 1; } }
    int8_t* dcells; Grid* dgrids; Sample* dout; unsigned* dn;
    unsigned cap = unsigned(batch);
    CK(cudaMalloc(&dcells, cells.size())); CK(cudaMalloc(&dgrids, n * sizeof(Grid)));
    CK(cudaMalloc(&dout, size_t(cap) * sizeof(Sample))); CK(cudaMalloc(&dn, 4));
    CK(cudaMemcpy(dcells, cells.data(), cells.size(), cudaMemcpyHostToDevice));
    CK(cudaMemcpy(dgrids, grids.data(), n * sizeof(Grid), cudaMemcpyHostToDevice));
    std::vector<Sample> h(cap);
    std::unordered_map<uint64_t, Prog> best; best.reserve(1 << 22);
    uint64_t attempts = 0, accepted = 0, shorter = 0; double gpu_s = 0, host_s = 0; int launches = 0;
    std::string markjs;
    auto T0 = std::chrono::steady_clock::now();
    auto el = [&] { return std::chrono::duration<double>(std::chrono::steady_clock::now() - T0).count(); };
    while (el() < secs) {
        auto t0 = std::chrono::steady_clock::now();
        CK(cudaMemset(dn, 0, 4));
        synth<<<unsigned((batch + 127) / 128), 128>>>(dcells, dgrids, n, 0x1234567ull + uint64_t(launches) * 0x9e3779b97f4a7c15ull,
                                                     uint64_t(launches) * uint64_t(batch), maxt, mint, dout, dn, cap);
        CK(cudaGetLastError());
        unsigned k; CK(cudaMemcpy(&k, dn, 4, cudaMemcpyDeviceToHost)); if (k > cap) k = cap;
        CK(cudaMemcpy(h.data(), dout, size_t(k) * sizeof(Sample), cudaMemcpyDeviceToHost));
        gpu_s += std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
        attempts += uint64_t(batch); accepted += k; ++launches;
        auto t1 = std::chrono::steady_clock::now();
        for (unsigned i = 0; i < k; ++i) {
            const Sample& s = h[i];
            uint64_t key = dedup ? fp(s.grid, s.h, s.w, s.c) : accepted - k + i;
            auto it = best.find(key);
            if (it != best.end() && it->second.ntok <= s.ntok) continue;
            if (it != best.end()) ++shorter;
            Prog& p = best[key]; p.grid = s.grid; p.ntok = s.ntok;
            memcpy(p.tok, s.tok, MAXT); memcpy(p.cst, s.cst, MAXT);
        }
        host_s += std::chrono::duration<double>(std::chrono::steady_clock::now() - t1).count();
        if (markjs.empty() && el() >= mark) {
            char b[256]; snprintf(b, sizeof b, "{\"t\": %.2f, \"accepted\": %llu, \"distinct\": %zu, \"distinct_rate\": %.4f}", el(),
                                  (unsigned long long)accepted, best.size(), double(best.size()) / double(accepted ? accepted : 1));
            markjs = b;
        }
    }
    double wall = el();
    // write: re-evaluate each kept program on the host (same step()) to get its output
    auto tw0 = std::chrono::steady_clock::now();
    FILE* fo = fopen(opath.c_str(), "w");
    uint64_t written = 0; uint64_t tokcnt[NTOK] = {0}, rootcnt[NTOK] = {0}, lencnt[MAXT + 1] = {0}, progs_with[NTOK] = {0};
    std::map<int, uint64_t> strat;
    static Val st[SD];
    for (auto& kv : best) {
        if (written >= uint64_t(wcap)) break;
        const Prog& p = kv.second; const Grid& g = grids[p.grid];
        int root = p.tok[p.ntok - 1];
        if (scap) { uint64_t& sc = strat[root * 64 + p.ntok]; if (sc >= uint64_t(scap)) continue; ++sc; }
        int sp = 0; bool ok = true;
        for (int i = 0; i < p.ntok && ok; ++i) ok = step(p.tok[i], p.cst[i], st, sp, cells.data() + g.off, g.h, g.w);
        if (!ok || sp != 1) { fprintf(stderr, "re-eval failed\n"); continue; }
        const Val& v = st[0];
        bool seen[NTOK] = {false};
        for (int i = 0; i < p.ntok; ++i) { tokcnt[p.tok[i]]++; seen[p.tok[i]] = true; }
        for (int t = 0; t < NTOK; ++t) progs_with[t] += seen[t];
        rootcnt[root]++; lencnt[p.ntok]++;
        std::string o = "{\"task\":\"" + (g.task < int(names.size()) ? names[g.task] : std::to_string(g.task)) +
                        "\",\"ex\":" + std::to_string(g.ex) + ",\"prog\":" + prog_json(p) + ",\"out\":[";
        for (int r = 0; r < v.h; ++r) { o += r ? ",[" : "["; for (int c = 0; c < v.w; ++c) { if (c) o += ","; o += char('0' + v.c[r * v.w + c]); } o += "]"; }
        o += "]}\n"; fwrite(o.data(), 1, o.size(), fo); ++written;
    }
    fclose(fo);
    double write_s = std::chrono::duration<double>(std::chrono::steady_clock::now() - tw0).count();
    size_t fr, tot; cudaMemGetInfo(&fr, &tot);
    auto arr = [&](const uint64_t* a, int m, bool named) {
        std::string s = named ? "{" : "[";
        for (int i = 0; i < m; ++i) {
            if (named) { if (!a[i]) continue; if (s.size() > 1) s += ", "; s += "\"" + std::string(i == T_C ? "const" : TN[i]) + "\": " + std::to_string(a[i]); }
            else { if (i) s += ", "; s += std::to_string(a[i]); }
        }
        return s + (named ? "}" : "]");
    };
    printf("{\"gpusynth\": 2, \"grids\": %d, \"mint\": %d, \"maxt\": %d, \"dedup\": %d, \"launches\": %d, \"batch\": %ld, \"attempts\": %llu, \"accepted\": %llu, "
           "\"accept_rate\": %.4f, \"distinct\": %zu, \"distinct_rate\": %.4f, \"replaced_by_shorter\": %llu, \"written\": %llu, "
           "\"wall_s\": %.3f, \"gpu_s\": %.3f, \"host_s\": %.3f, \"write_s\": %.3f, \"accepted_per_s_wall\": %.0f, \"distinct_per_s_wall\": %.0f, "
           "\"mark\": %s, \"tok_count\": %s, \"progs_with\": %s, \"root_count\": %s, \"ntok_hist\": %s}\n",
           n, mint, maxt, dedup, launches, batch, (unsigned long long)attempts, (unsigned long long)accepted, double(accepted) / double(attempts),
           best.size(), double(best.size()) / double(accepted ? accepted : 1), (unsigned long long)shorter, (unsigned long long)written,
           wall, gpu_s, host_s, write_s, double(accepted) / wall, double(best.size()) / wall,
           markjs.empty() ? "null" : markjs.c_str(), arr(tokcnt, NTOK, true).c_str(), arr(progs_with, NTOK, true).c_str(),
           arr(rootcnt, NTOK, true).c_str(), arr(lencnt, maxt + 1, false).c_str());
    return 0;
}
