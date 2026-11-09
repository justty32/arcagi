// gpuprofile: near-miss profile of the gpusearch program space per task.
// Every program of length 1..depth is scored on the train pairs (overlap
// cells matching after the best single colormap / max area); per depth we
// report counts, a score histogram and the top-K distinct programs.
//
//   gpuprofile --task FILE... | --tasks LIST [--data-dir DIR] [--depth D]
//              [--dedup P [--prefix-cap N]] [--budget SEC] [--topk K]
//              [--pool M] [--chunk N] [--cap N] [--spec PATH] [--out JSONL]
//
// Helpers (task loading, alphabet, decode, unique_prefixes) are copied from
// gpu/driver.cpp, which keeps them in an anonymous namespace.
#include "profile.hpp"
#include "../../src/background.hpp"
#include "../../src/learners.hpp"
#include "../../src/prims.hpp"
#include <algorithm>
#include <chrono>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <sstream>
#include <unordered_set>

using namespace arc;
namespace fs = std::filesystem;
using Clock = std::chrono::steady_clock;

namespace {
struct Args {
    std::vector<std::string> tasks;
    std::string spec = "native/spec.json", out;
    int depth = 4, dedup = 0, topk = 8, pool = 64;
    double budget = 60;
    uint64_t chunk = 1ull << 22;
    unsigned cap = 1u << 16;
    size_t prefix_cap = 400000;
};
struct Task { std::string id; Grids train_in, train_out, test_in, test_out; };

double secs(Clock::time_point t) { return std::chrono::duration<double>(Clock::now() - t).count(); }

std::string slurp(const std::string& p) {
    std::ifstream in(p, std::ios::binary);
    if (!in) throw std::runtime_error("cannot read " + p);
    std::ostringstream o; o << in.rdbuf(); return o.str();
}

Task load(const std::string& path) {
    Task t; t.id = fs::path(path).stem().string();
    Json j = Json::parse(slurp(path));
    for (const auto& e : j["train"].items()) { t.train_in.push_back(from_json(e["input"])); t.train_out.push_back(from_json(e["output"])); }
    for (const auto& e : j["test"].items()) {
        t.test_in.push_back(from_json(e["input"]));
        if (e.fields().contains("output")) t.test_out.push_back(from_json(e["output"]));
    }
    return t;
}

const char* GRAV[] = {"down", "left", "up", "right"};
const char* MIRR[] = {"lr", "ud", "quad"};
const char* SELF[] = {"pos", "neg"};

Step to_step(gs::DStep s) {
    using namespace gs;
    switch (s.op) {
        case FLIP_LR: case FLIP_UD: case TRANSPOSE: case ROT90: case ROT180: case ROT270: case ANTI_TRANSPOSE:
            return {D4[s.op]};
        case UPSCALE: return {"upscale", int(s.a), int(s.b)};
        case TILE: return {"tile", int(s.a), int(s.b)};
        case DOWNSCALE: return {"downscale", int(s.a), int(s.b)};
        case MIRROR_TILE: return {"mirror_tile", MIRR[s.a]};
        case CROP_BBOX: return {"crop_bbox"};
        case GRAVITY: return {"gravity", GRAV[s.a]};
        case FILL_ENCLOSED: return {"fill_enclosed"};
        case SPLIT_OVERLAY: return {"split_overlay", s.a ? "v" : "h", SPLIT_OPS[s.b]};
        case SELF_TILE: return {"self_tile", SELF[s.a]};
        case COLORMAP: return {"colormap", Json::Array{Json::Array{int(s.a), int(s.b)}}};
    }
    fail();
}

std::vector<gs::DStep> alphabet(const Task& t) {
    using namespace gs;
    std::vector<DStep> a;
    for (int op = FLIP_LR; op <= ANTI_TRANSPOSE; ++op) a.push_back({uint8_t(op), 0, 0, 0});
    for (int op : {UPSCALE, TILE, DOWNSCALE})
        for (int fy = 1; fy <= 3; ++fy) for (int fx = 1; fx <= 3; ++fx)
            if (fy != 1 || fx != 1) a.push_back({uint8_t(op), uint8_t(fy), uint8_t(fx), 0});
    for (int m = 0; m < 3; ++m) a.push_back({MIRROR_TILE, uint8_t(m), 0, 0});
    a.push_back({CROP_BBOX, 0, 0, 0});
    for (int d = 0; d < 4; ++d) a.push_back({GRAVITY, uint8_t(d), 0, 0});
    a.push_back({FILL_ENCLOSED, 0, 0, 0});
    for (int ax = 0; ax < 2; ++ax) for (int op = 0; op < 5; ++op) a.push_back({SPLIT_OVERLAY, uint8_t(ax), uint8_t(op), 0});
    for (int m = 0; m < 2; ++m) a.push_back({SELF_TILE, uint8_t(m), 0, 0});
    Grids ins = t.train_in; ins.insert(ins.end(), t.test_in.begin(), t.test_in.end());
    auto from = colors(ins); from.insert(10);
    auto to = colors(t.train_out); to.insert(0);
    for (int x : from) for (int y : to) if (x != y) a.push_back({COLORMAP, uint8_t(x), uint8_t(y), 0});
    return a;
}

uint64_t ipow(uint64_t a, int d) { uint64_t r = 1; while (d--) r *= a; return r; }

struct Prefixes { std::vector<uint8_t> table; int plen = 0; size_t rows = 0; bool truncated = false; };

Program decode(uint64_t idx, int depth, const std::vector<gs::DStep>& alpha, const Prefixes* pre) {
    int plen = pre && depth > pre->plen ? pre->plen : 0;
    Program p(depth);
    for (int k = depth - 1; k >= plen; --k) { p[k] = to_step(alpha[idx % alpha.size()]); idx /= alpha.size(); }
    for (int k = 0; k < plen; ++k) p[k] = to_step(alpha[pre->table[idx * plen + k]]);
    return p;
}

std::optional<Grids> run_all(const Program& p, const Grids& in, const Spec& spec) {
    Grids out;
    try {
        for (Grid g : in) {
            for (const auto& s : p) { g = apply_step(s.items(), g, spec); if (!g.bounds()) return std::nullopt; }
            out.push_back(std::move(g));
        }
    } catch (const std::exception&) { return std::nullopt; }
    return out;
}

// Unique depth-P prefixes by BFS with observational dedup over all inputs
// (identical to gpusearch, so prefix rows and program words match).
Prefixes unique_prefixes(const Task& t, const Spec& spec, const std::vector<gs::DStep>& alpha, int P, size_t cap) {
    std::vector<Step> steps; for (auto s : alpha) steps.push_back(to_step(s));
    Grids root = t.train_in; root.insert(root.end(), t.test_in.begin(), t.test_in.end());
    std::unordered_set<uint64_t> seen{signature(root, root.size())};
    std::vector<std::pair<std::vector<uint8_t>, Grids>> level{{{}, root}};
    Prefixes out;
    constexpr size_t MAX_CELLS = 400000000;
    size_t cells = 0;
    for (int d = 1; d <= P; ++d) {
        std::vector<std::pair<std::vector<uint8_t>, Grids>> next;
        bool last = d == P;
        for (const auto& [prog, grids] : level) {
            for (size_t s = 0; s < steps.size(); ++s) {
                Grids child; bool ok = true;
                try {
                    for (const auto& g : grids) { child.push_back(apply_step(steps[s], g, spec)); if (!child.back().bounds()) { ok = false; break; } }
                } catch (const std::exception&) { ok = false; }
                if (!ok || !seen.insert(signature(child, child.size())).second) continue;
                auto p = prog; p.push_back(uint8_t(s));
                if (last) { out.table.insert(out.table.end(), p.begin(), p.end()); ++out.rows; }
                else {
                    for (const auto& g : child) cells += g.data.size();
                    next.emplace_back(std::move(p), std::move(child));
                }
                if ((last ? out.rows : next.size()) >= cap || cells > MAX_CELLS) break;
            }
            if ((last ? out.rows : next.size()) >= cap || cells > MAX_CELLS) break;
        }
        if (cells > MAX_CELLS) out.truncated = true;
        if (!last) level = std::move(next);
    }
    out.plen = P;
    return out;
}

void pack(const Grid& g, std::vector<uint8_t>& buf, int& h, int& w, int& off) {
    h = g.h; w = g.w; off = int(buf.size());
    for (int c : g.data) buf.push_back(uint8_t(c));
}

const char* OPNAME[] = {"flip_lr", "flip_ud", "transpose", "rot90", "rot180", "rot270", "anti_transpose",
                        "upscale", "tile", "downscale", "mirror_tile", "crop_bbox", "gravity",
                        "fill_enclosed", "split_overlay", "self_tile", "colormap"};

bool better(const gs::ProfHit& x, const gs::ProfHit& y) {
    if (x.q != y.q) return x.q > y.q;
    if (x.rq != y.rq) return x.rq > y.rq;
    return x.idx < y.idx;
}

// Lowest q of the highest bin b whose tail (bins >= b) holds >= m programs.
uint32_t tail_threshold(const std::vector<uint64_t>& hist, int m) {
    uint64_t acc = 0;
    for (int b = gs::PROF_BINS - 1; b >= 0; --b) { acc += hist[b]; if (acc >= uint64_t(m)) return uint32_t(b) << 6; }
    return 0;
}
}

int main(int argc, char** argv) {
    Args a;
    std::string data_dir;
    std::vector<std::string> lists;
    for (int i = 1; i < argc; ++i) {
        std::string k = argv[i];
        if (i + 1 >= argc) { std::cerr << "missing value for " << k << "\n"; return 2; }
        std::string v = argv[++i];
        if (k == "--task") a.tasks.push_back(v);
        else if (k == "--tasks") lists.push_back(v);
        else if (k == "--data-dir") data_dir = v;
        else if (k == "--depth") a.depth = std::stoi(v);
        else if (k == "--dedup") a.dedup = std::stoi(v);
        else if (k == "--prefix-cap") a.prefix_cap = std::stoull(v);
        else if (k == "--budget") a.budget = std::stod(v);
        else if (k == "--topk") a.topk = std::stoi(v);
        else if (k == "--pool") a.pool = std::stoi(v);
        else if (k == "--chunk") a.chunk = std::stoull(v);
        else if (k == "--cap") a.cap = unsigned(std::stoul(v));
        else if (k == "--spec") a.spec = v;
        else if (k == "--out") a.out = v;
        else { std::cerr << "unknown arg " << k << "\n"; return 2; }
    }
    for (const auto& l : lists) {
        std::istringstream in(slurp(l)); std::string line;
        while (std::getline(in, line)) {
            line = line.substr(0, line.find_first_of(" \t,"));
            if (line.empty() || line[0] == '#') continue;
            if (!data_dir.empty() && line.find('/') == std::string::npos) line = data_dir + "/" + line + ".json";
            a.tasks.push_back(line);
        }
    }
    if (a.depth < 1 || a.depth > 8) { std::cerr << "depth must be 1..8\n"; return 2; }
    if (a.dedup < 0 || a.dedup > 4) { std::cerr << "--dedup P needs 0 <= P <= 4\n"; return 2; }
    if (a.pool < 1 || a.topk < 1 || a.cap < unsigned(a.pool)) { std::cerr << "need pool, topk >= 1 and cap >= pool\n"; return 2; }
    Spec spec(read_json(a.spec));
    gs::ProfCtx* ctx = gs::prof_open(a.cap);
    std::ofstream file;
    if (!a.out.empty()) file.open(a.out, std::ios::app);
    std::ostream& out = a.out.empty() ? std::cout : file;

    for (const auto& path : a.tasks) {
        Task t;
        try { t = load(path); } catch (const std::exception& e) { std::cerr << path << ": " << e.what() << "\n"; continue; }
        size_t nall = t.train_in.size() + t.test_in.size();
        Json::Object rec{{"task", t.id}};
        if (nall > size_t(gs::MAX_PAIRS)) { rec["skipped"] = "too many pairs"; out << Json(rec).dump() << "\n" << std::flush; continue; }
        set_task_background(std::nullopt);
        auto alpha = alphabet(t);
        const uint64_t A = alpha.size();
        rec["alphabet"] = int(A);
        rec["max_depth"] = a.depth;
        rec["dedup"] = a.dedup;
        gs::DTask dt{};
        std::vector<uint8_t> ins, tgs;
        dt.ntrain = int(t.train_in.size()); dt.nall = int(nall);
        for (size_t i = 0; i < nall; ++i)
            pack(i < t.train_in.size() ? t.train_in[i] : t.test_in[i - t.train_in.size()], ins, dt.ih[i], dt.iw[i], dt.ioff[i]);
        for (size_t i = 0; i < t.train_out.size(); ++i) pack(t.train_out[i], tgs, dt.th[i], dt.tw[i], dt.toff[i]);
        gs::prof_load(ctx, dt, ins, tgs, alpha);

        auto t0 = Clock::now();
        Prefixes pre;
        Json::Array depths;
        uint32_t best_q = 0; int best_depth = 0, perfect_depth = 0;
        bool timed_out = false;
        for (int d = 1; d <= a.depth && !timed_out; ++d) {
            bool use_prefix = a.dedup > 0 && d > a.dedup;
            if (use_prefix && !pre.plen) {
                auto b0 = Clock::now();
                pre = unique_prefixes(t, spec, alpha, a.dedup, a.prefix_cap);
                gs::prof_set_prefixes(ctx, pre.table, pre.plen);
                rec["prefixes"] = Json::Object{{"plen", pre.plen}, {"rows", double(pre.rows)},
                                               {"truncated", pre.rows >= a.prefix_cap || pre.truncated}, {"bfs_seconds", secs(b0)}};
                if (!pre.rows) break;
            }
            auto d0 = Clock::now();
            uint64_t total = use_prefix ? pre.rows * ipow(A, d - pre.plen) : ipow(A, d);
            uint64_t threads = total / A, step = std::max<uint64_t>(1, a.chunk / A);
            std::vector<uint64_t> hist(gs::PROF_BINS, 0), lh;
            gs::ProfCounters sum, lc;
            std::vector<gs::ProfHit> pool, got;
            uint64_t space = 0;
            bool truncated = false;
            for (uint64_t s = 0; s < threads; s += step) {
                if (secs(t0) > a.budget) { timed_out = true; break; }
                uint64_t n = std::min(step, threads - s);
                uint32_t thr = pool.size() >= size_t(a.pool) ? pool[a.pool - 1].q : 0;
                uint64_t nh = gs::prof_run(ctx, d, s, n, use_prefix, thr, got, lh, lc);
                if (nh > a.cap) {
                    uint32_t thr2 = tail_threshold(lh, a.pool);
                    if (thr2 > thr) nh = gs::prof_run(ctx, d, s, n, use_prefix, thr2, got, lh, lc);
                    if (nh > a.cap) truncated = true;
                }
                for (int b = 0; b < gs::PROF_BINS; ++b) hist[b] += lh[b];
                sum.valid += lc.valid; sum.fail += lc.fail; sum.perfect += lc.perfect;
                space += n * A;
                pool.insert(pool.end(), got.begin(), got.end());
                std::sort(pool.begin(), pool.end(), better);
                if (pool.size() > size_t(a.pool)) pool.resize(a.pool);
            }
            if (!space) break;
            // Materialise the pool on the CPU; keep top-K distinct train outputs.
            Json::Array top;
            std::unordered_set<uint64_t> sigs;
            for (const auto& h : pool) {
                if (int(top.size()) >= a.topk) break;
                Program p = decode(h.idx, d, alpha, use_prefix ? &pre : nullptr);
                auto st = run_all(p, t.train_in, spec);
                if (!st || !sigs.insert(signature(*st, st->size())).second) continue;
                Json::Array ops;
                uint64_t r = h.idx;
                std::vector<std::string> names(d);
                int plen = use_prefix ? pre.plen : 0;
                for (int k = d - 1; k >= plen; --k) { names[k] = OPNAME[alpha[r % A].op]; r /= A; }
                for (int k = 0; k < plen; ++k) names[k] = OPNAME[alpha[pre.table[r * plen + k]].op];
                for (auto& nm : names) ops.emplace_back(nm);
                top.emplace_back(Json::Object{{"program", p}, {"score", h.q / 65535.0}, {"raw", h.rq / 65535.0}, {"ops", ops}});
            }
            Json::Object ge;
            for (auto [key, frac] : {std::pair{"50", 0.50}, {"80", 0.80}, {"90", 0.90}, {"95", 0.95}, {"99", 0.99}}) {
                uint64_t c = 0;
                for (int b = int(std::ceil(frac * gs::PROF_BINS)); b < gs::PROF_BINS; ++b) c += hist[b];
                ge[key] = double(c);
            }
            Json::Array h20(20, Json(0.0));
            std::vector<uint64_t> h20v(20, 0);
            for (int b = 0; b < gs::PROF_BINS; ++b) h20v[std::min(19, b * 20 / gs::PROF_BINS)] += hist[b];
            for (int i = 0; i < 20; ++i) h20[i] = double(h20v[i]);
            uint32_t dq = pool.empty() ? 0 : pool[0].q;
            if (dq > best_q) { best_q = dq; best_depth = d; }
            if (sum.perfect && !perfect_depth) perfect_depth = d;
            depths.emplace_back(Json::Object{
                {"d", d}, {"space", double(space)}, {"valid", double(sum.valid)}, {"fail", double(sum.fail)},
                {"perfect", double(sum.perfect)}, {"seconds", secs(d0)}, {"complete", !timed_out},
                {"truncated", truncated}, {"best", dq / 65535.0}, {"ge", ge}, {"hist20", h20}, {"top", top}});
        }
        rec["seconds"] = secs(t0);
        rec["depths"] = depths;
        rec["best"] = best_q / 65535.0;
        rec["best_depth"] = best_depth;
        rec["perfect_depth"] = perfect_depth;
        out << Json(rec).dump() << "\n" << std::flush;
    }
    gs::prof_close(ctx);
    return 0;
}
