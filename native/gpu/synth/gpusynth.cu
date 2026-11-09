// E11 / E17 prototype (reports/m0-baseline-1110/): GPU "reverse synthesis" of training samples.
// Each GPU thread picks an ARC training input grid, grows a random typed postfix program over the
// first-order seed primitives (add sub mul neg mod eq lt max min and or not if len nth head last
// take drop reverse transpose), evaluating eagerly while it grows, and keeps the program if it
// ends as one non-empty grid different from the input. Host prints samples/s and writes up to
// --write N samples as jsonl {"task","ex","prog" (seed s-expr), "out"}.
// Semantics approximate seed_value.cpp (errors on out-of-range, |int| <= 1e9); NOT cross-checked.
// usage: gpusynth --grids g.bin --names names.json --seconds S --batch N --write N --out f.jsonl
#include <cuda_runtime.h>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <unordered_set>
#include <vector>

constexpr int MAXC = 900, MAXT = 12, SD = 4;
enum Kind : uint8_t { KI, KB, KL1, KL2 };
enum Tok : uint8_t { T_IN, T_C, ADD, SUB, MUL, NEG, MOD, EQ, LT, MAX, MIN, AND, OR, NOT, IF, LEN, NTH, HEAD, LAST,
                     TAKE, DROP, REVERSE, TRANSPOSE, NTOK };
static const char* TN[NTOK] = {"$in", "", "add", "sub", "mul", "neg", "mod", "eq", "lt", "max", "min", "and", "or",
                               "not", "if", "len", "nth", "head", "last", "take", "drop", "reverse", "transpose"};
#define AR_INIT {0, 0, 2, 2, 2, 1, 2, 2, 2, 2, 2, 2, 2, 1, 3, 1, 2, 1, 1, 2, 2, 1, 1}
__device__ constexpr int AR[NTOK] = AR_INIT;
static const int AR_H[NTOK] = AR_INIT;  // host copy
struct Val { uint8_t k, h, w; int64_t iv; int8_t c[MAXC]; };   // L1: h=1, w=len; L2: h x w (h=0 empty)
struct Grid { uint32_t off; int32_t task; int16_t ex; uint8_t h, w; };
struct Sample { int32_t grid; uint8_t ntok, h, w, pad; uint8_t tok[MAXT]; int8_t cst[MAXT]; int8_t c[MAXC]; };

__device__ __forceinline__ uint64_t rng(uint64_t& s) { s ^= s << 13; s ^= s >> 7; s ^= s << 17; return s; }
__device__ __forceinline__ uint64_t mix(uint64_t z) {
    z += 0x9e3779b97f4a7c15ull; z = (z ^ (z >> 30)) * 0xbf58476d1ce4e5b9ull; z = (z ^ (z >> 27)) * 0x94d049bb133111ebull;
    return z ^ (z >> 31);
}
__device__ bool isL(const Val& v) { return v.k == KL1 || v.k == KL2; }
__device__ int llen(const Val& v) { return v.k == KL1 ? v.w : v.h; }
__device__ bool okint(int64_t x) { return x <= 1000000000 && x >= -1000000000; }
// applicable? (stack top at st[sp-1])
__device__ bool can(int t, const Val* st, int sp) {
    const Val *a = sp >= 1 ? &st[sp - 1] : nullptr, *b = sp >= 2 ? &st[sp - 2] : nullptr;
    switch (t) {
    case T_IN: case T_C: return sp < SD;
    case ADD: case SUB: case MUL: case MOD: case EQ: case LT: case MAX: case MIN: return b && a->k == KI && b->k == KI;
    case NEG: return a && a->k == KI;
    case AND: case OR: return b && a->k == KB && b->k == KB;
    case NOT: return a && a->k == KB;
    case IF: return sp >= 3 && st[sp - 3].k == KB && a->k == b->k;
    case LEN: case REVERSE: return a && isL(*a);
    case HEAD: case LAST: return a && isL(*a) && llen(*a) > 0;
    case NTH: return b && isL(*b) && a->k == KI;
    case TAKE: case DROP: return b && b->k == KI && isL(*a);
    case TRANSPOSE: return a && a->k == KL2 && a->h > 0;
    }
    return false;
}
// apply token t to the stack (in place); false = runtime error
__device__ bool step(int t, int cst, Val* st, int& sp, const int8_t* in, int ih, int iw) {
    if (t == T_IN) { Val& v = st[sp++]; v.k = KL2; v.h = ih; v.w = iw; for (int i = 0; i < ih * iw; ++i) v.c[i] = in[i]; return true; }
    if (t == T_C) { Val& v = st[sp++]; v.k = KI; v.iv = cst; return true; }
    Val& a = st[sp - 1];
    if (AR[t] == 1) {
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
            for (int i = 0; i < h * w; ++i) a.c[i] = tmp[i];
            a.h = w; a.w = h; return true; }
        }
        return false;
    }
    if (AR[t] == 3) {  // if c x y  (postfix: c x y)
        Val& c = st[sp - 3]; bool cond = c.iv != 0;
        Val& src = cond ? st[sp - 2] : st[sp - 1];
        c.k = src.k; c.h = src.h; c.w = src.w; c.iv = src.iv;
        if (isL(src)) { int n = src.k == KL1 ? src.w : src.h * src.w; for (int i = 0; i < n; ++i) c.c[i] = src.c[i]; }
        sp -= 2; return true;
    }
    Val& b = st[sp - 2];  // binary: op(b, a); result into b
    int64_t x = b.iv, y = a.iv, r = 0;
    switch (t) {
    case ADD: r = x + y; break; case SUB: r = x - y; break; case MUL: r = x * y; break;
    case MOD: if (y == 0) return false; r = ((x % y) + y) % y; break;
    case MAX: r = x > y ? x : y; break; case MIN: r = x < y ? x : y; break;
    case EQ: b.iv = x == y; b.k = KB; sp--; return true;
    case LT: b.iv = x < y; b.k = KB; sp--; return true;
    case AND: b.iv = x && y; sp--; return true;
    case OR: b.iv = x || y; sp--; return true;
    case NTH: {
        int n = llen(b); if (y < 0 || y >= n) return false;
        if (b.k == KL1) { b.iv = b.c[y]; b.k = KI; }
        else { int w = b.w; for (int j = 0; j < w; ++j) b.c[j] = b.c[y * w + j]; b.k = KL1; b.h = 1; }
        sp--; return true; }
    case TAKE: case DROP: {  // b = n (int), a = list -> result into b slot
        int n = llen(a); if (x < 0) return false; int k = x > n ? n : int(x);
        int w = a.k == KL1 ? 1 : a.w, lo = t == TAKE ? 0 : k, cnt = t == TAKE ? k : n - k;
        for (int i = 0; i < cnt * w; ++i) b.c[i] = a.c[lo * w + i];
        b.k = a.k; if (a.k == KL1) { b.h = 1; b.w = cnt; } else { b.h = cnt; b.w = cnt ? a.w : 0; }
        sp--; return true; }
    }
    if (!okint(r)) return false;
    b.iv = r; sp--; return true;
}
__global__ void synth(const int8_t* cells, const Grid* grids, int ngrids, uint64_t seed, Sample* out, unsigned* nout, unsigned cap) {
    uint64_t tid = blockIdx.x * uint64_t(blockDim.x) + threadIdx.x;
    uint64_t s = mix(seed ^ (tid * 0x9e3779b97f4a7c15ull)) | 1;
    int gi = int(rng(s) % uint64_t(ngrids));
    const Grid g = grids[gi]; const int8_t* in = cells + g.off;
    Val st[SD]; int sp = 0; uint8_t tok[MAXT]; int8_t cst[MAXT]; int nt = 0;
    for (; nt < MAXT; ) {
        int cand[NTOK], nc = 0;
        for (int t = 0; t < NTOK; ++t) if (can(t, st, sp)) { cand[nc++] = t; if (t == T_IN && sp == 0) { cand[nc++] = t; cand[nc++] = t; } }
        if (!nc) return;
        int t = cand[rng(s) % nc]; int c = t == T_C ? int(rng(s) % 10) : 0;
        if (!step(t, c, st, sp, in, g.h, g.w)) return;
        tok[nt] = uint8_t(t); cst[nt] = int8_t(c); ++nt;
        if (sp == 1 && st[0].k == KL2 && nt >= 2 && (rng(s) & 3) == 0) break;
    }
    if (!(sp == 1 && st[0].k == KL2 && st[0].h > 0 && st[0].w > 0)) return;
    const Val& v = st[0];
    if (v.h == g.h && v.w == g.w) { bool same = true; for (int i = 0; i < g.h * g.w && same; ++i) same = v.c[i] == in[i]; if (same) return; }
    unsigned k = atomicAdd(nout, 1u); if (k >= cap) return;
    Sample& o = out[k]; o.grid = gi; o.ntok = nt; o.h = v.h; o.w = v.w;
    for (int i = 0; i < nt; ++i) { o.tok[i] = tok[i]; o.cst[i] = cst[i]; }
    for (int i = 0; i < v.h * v.w; ++i) o.c[i] = v.c[i];
}
#define CK(x) do { cudaError_t e_ = (x); if (e_ != cudaSuccess) { fprintf(stderr, "cuda %s line %d\n", cudaGetErrorString(e_), __LINE__); return 1; } } while (0)
static std::string prog_json(const Sample& s) {
    std::vector<std::string> st;
    for (int i = 0; i < s.ntok; ++i) {
        int t = s.tok[i];
        if (t == T_IN) { st.push_back("[\"$in\"]"); continue; }
        if (t == T_C) { st.push_back(std::to_string(int(s.cst[i]))); continue; }
        std::string e = std::string("[\"") + TN[t] + "\"";
        size_t base = st.size() - AR_H[t];
        for (size_t j = base; j < st.size(); ++j) e += "," + st[j];
        st.resize(base); st.push_back(e + "]");
    }
    return st.back();
}
int main(int argc, char** argv) {
    std::string gpath, npath, opath = "synth.jsonl"; double secs = 10; long batch = 1 << 18, wcap = 100000;
    for (int i = 1; i + 1 < argc; i += 2) {
        std::string a = argv[i];
        if (a == "--grids") gpath = argv[i + 1]; else if (a == "--names") npath = argv[i + 1];
        else if (a == "--out") opath = argv[i + 1]; else if (a == "--seconds") secs = atof(argv[i + 1]);
        else if (a == "--batch") batch = atol(argv[i + 1]); else if (a == "--write") wcap = atol(argv[i + 1]);
    }
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
    FILE* fo = fopen(opath.c_str(), "w");
    std::unordered_set<uint64_t> uniq_io, uniq_prog;
    uint64_t attempts = 0, accepted = 0, written = 0; double gpu_s = 0, write_s = 0; int launches = 0;
    auto T0 = std::chrono::steady_clock::now();
    auto el = [&] { return std::chrono::duration<double>(std::chrono::steady_clock::now() - T0).count(); };
    while (el() < secs) {
        auto t0 = std::chrono::steady_clock::now();
        CK(cudaMemset(dn, 0, 4));
        synth<<<unsigned((batch + 127) / 128), 128>>>(dcells, dgrids, n, 0x1234567ull + uint64_t(launches) * 0x9e3779b97f4a7c15ull, dout, dn, cap);
        CK(cudaGetLastError());
        unsigned k; CK(cudaMemcpy(&k, dn, 4, cudaMemcpyDeviceToHost)); if (k > cap) k = cap;
        CK(cudaMemcpy(h.data(), dout, size_t(k) * sizeof(Sample), cudaMemcpyDeviceToHost));
        gpu_s += std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
        attempts += uint64_t(batch); accepted += k; ++launches;
        auto t1 = std::chrono::steady_clock::now();
        for (unsigned i = 0; i < k; ++i) {
            const Sample& s = h[i];
            uint64_t ho = 1469598103934665603ull ^ uint64_t(s.grid) * 1315423911ull ^ (uint64_t(s.h) << 8 | s.w);
            for (int j = 0; j < s.h * s.w; ++j) ho = (ho ^ uint8_t(s.c[j])) * 1099511628211ull;
            uniq_io.insert(ho);
            if (written < uint64_t(wcap)) {
                const Grid& g = grids[s.grid];
                std::string o = "{\"task\":\"" + (g.task < int(names.size()) ? names[g.task] : std::to_string(g.task)) +
                                "\",\"ex\":" + std::to_string(g.ex) + ",\"prog\":" + prog_json(s) + ",\"out\":[";
                for (int r = 0; r < s.h; ++r) { o += r ? ",[" : "["; for (int c = 0; c < s.w; ++c) { if (c) o += ","; o += std::to_string(int(s.c[r * s.w + c])); } o += "]"; }
                o += "]}\n"; fwrite(o.data(), 1, o.size(), fo); ++written;
            }
        }
        write_s += std::chrono::duration<double>(std::chrono::steady_clock::now() - t1).count();
    }
    fclose(fo);
    size_t fr, tot; cudaMemGetInfo(&fr, &tot);
    printf("{\"gpusynth\": true, \"grids\": %d, \"launches\": %d, \"batch\": %ld, \"attempts\": %llu, \"accepted\": %llu, "
           "\"accept_rate\": %.4f, \"unique_io\": %zu, \"written\": %llu, \"wall_s\": %.3f, \"gpu_s\": %.3f, \"host_s\": %.3f, "
           "\"accepted_per_s_gpu\": %.0f, \"accepted_per_s_wall\": %.0f, \"sample_bytes\": %zu}\n",
           n, launches, batch, (unsigned long long)attempts, (unsigned long long)accepted, double(accepted) / double(attempts),
           uniq_io.size(), (unsigned long long)written, el(), gpu_s, write_s, double(accepted) / gpu_s, double(accepted) / el(), sizeof(Sample));
    return 0;
}
