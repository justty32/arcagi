// gpusearch: brute-force program search over native/gpu/space.hpp, on the GPU
// (kernel.cu) and/or on the CPU with arcsearch's own primitives (apply_step,
// fit_colormap), so both sides cover the same program space per task.
//
//   gpusearch --task FILE... | --tasks LIST [--data-dir DIR]
//             [--mode gpu|cpu|both] [--depth D] [--stop-first] [--budget SEC]
//             [--threads N] [--spec PATH] [--out JSONL] [--chunk N] [--cap N]
//             [--dedup P [--prefix-cap N]]
//
// --dedup P (GPU only): depths <= P are brute force; deeper programs are a
// unique depth-P prefix (CPU BFS, programs with identical states on every
// train and test input collapse to the first) followed by any suffix.
//
// One JSON line per task: program-space size, seconds, candidates/second and
// solutions per side, whether both sides found the same solution set, and the
// cheapest solution as an arcagi JSON program (colormap tables filled in).
#include "gpu.hpp"
#include "../src/background.hpp"
#include "../src/learners.hpp"
#include "../src/prims.hpp"
#include <algorithm>
#include <atomic>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <mutex>
#include <sstream>
#include <thread>
#include <unordered_set>

using namespace arc;
namespace fs = std::filesystem;
using Clock = std::chrono::steady_clock;

namespace {
struct Args {
    std::vector<std::string> tasks;
    std::string mode = "both", spec = "native/spec.json", out;
    int depth = 3, threads = 6;
    bool stop_first = false;
    double budget = 1e9;
    uint64_t chunk = 1ull << 24;
    unsigned cap = 1u << 18;
    int dedup = 0;
    size_t prefix_cap = 400000;
    bool shared = true;  // --kernel shared|flat
    int samples = 0;     // --samples K: also emit K materialised solutions per task
};
struct Task {
    std::string id;
    Grids train_in, train_out, test_in, test_out;
};

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

// Decode a solution word into its step list.
struct Prefixes { std::vector<uint8_t> table; int plen = 0; size_t rows = 0; bool truncated = false; };

Program decode(uint64_t word, int depth, const std::vector<gs::DStep>& alpha, const Prefixes* pre = nullptr) {
    uint64_t idx = word & ((1ull << 62) - 1);
    int plen = pre && depth > pre->plen ? pre->plen : 0;
    Program p(depth);
    for (int k = depth - 1; k >= plen; --k) { p[k] = to_step(alpha[idx % alpha.size()]); idx /= alpha.size(); }
    for (int k = 0; k < plen; ++k) p[k] = to_step(alpha[pre->table[idx * plen + k]]);
    return p;
}

// Run a program on the CPU (arcsearch primitives); empty optional on failure.
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

// ---- CPU twin: DFS with prefix reuse (one step per node, like arcsearch) --
struct CpuSide {
    const Task& t; const Spec& spec; const std::vector<gs::DStep>& alpha;
    std::vector<Step> steps;
    int depth; unsigned cap;
    std::mutex mu;
    std::vector<std::vector<uint64_t>> sols;  // per depth
    std::vector<uint64_t> nsol;
    std::atomic<uint64_t> nodes{0};
    size_t ntrain;

    CpuSide(const Task& t_, const Spec& s, const std::vector<gs::DStep>& a, int d, unsigned c)
        : t(t_), spec(s), alpha(a), depth(d), cap(c), sols(d + 1), nsol(d + 1, 0), ntrain(t_.train_in.size()) {
        for (auto st : alpha) steps.push_back(to_step(st));
    }
    void evaluate(const Grids& g, int d, uint64_t idx) {
        bool exact = true, matching = true;
        for (size_t i = 0; i < ntrain; ++i) {
            if (g[i] != t.train_out[i]) exact = false;
            if (!same_shape(g[i], t.train_out[i])) matching = false;
        }
        uint64_t kind = 0;
        Grids tests(g.begin() + ntrain, g.end());
        if (exact) {
            bool ok = true;
            for (const auto& x : tests) if (!x.valid()) ok = false;
            if (ok) kind = gs::EXACT;
        } else if (matching) {
            Grids train(g.begin(), g.begin() + ntrain);
            if (fit_colormap(train, t.train_out, tests)) kind = gs::CMAP;
        }
        if (!kind) return;
        std::lock_guard<std::mutex> lock(mu);
        ++nsol[d];
        if (sols[d].size() < cap) sols[d].push_back(idx | (kind << 62));
    }
    void dfs(const Grids& g, int d, uint64_t idx) {
        for (size_t s = 0; s < steps.size(); ++s) node(g, d, idx * steps.size() + s, s);
    }
    void node(const Grids& g, int d, uint64_t idx, size_t s) {
        ++nodes;
        Grids child;
        try {
            for (const auto& x : g) {
                child.push_back(apply_step(steps[s], x, spec));
                if (!child.back().bounds()) return;
            }
        } catch (const std::exception&) { return; }
        evaluate(child, d + 1, idx);
        if (d + 1 < depth) dfs(child, d + 1, idx);
    }
    void run(int threads) {
        Grids root = t.train_in; root.insert(root.end(), t.test_in.begin(), t.test_in.end());
        std::atomic<size_t> next{0};
        std::vector<std::thread> pool;
        for (int i = 0; i < threads; ++i) pool.emplace_back([&] {
            set_task_background(std::nullopt);
            for (size_t s; (s = next++) < steps.size();) node(root, 0, s, s);
        });
        for (auto& th : pool) th.join();
    }
};

// Unique depth-P prefixes by BFS with observational dedup over all inputs.
Prefixes unique_prefixes(const Task& t, const Spec& spec, const std::vector<gs::DStep>& alpha, int P, size_t cap) {
    std::vector<Step> steps; for (auto s : alpha) steps.push_back(to_step(s));
    Grids root = t.train_in; root.insert(root.end(), t.test_in.begin(), t.test_in.end());
    std::unordered_set<uint64_t> seen{signature(root, root.size())};
    std::vector<std::pair<std::vector<uint8_t>, Grids>> level{{{}, root}};
    Prefixes out;
    // Stored intermediate states are capped (~1.6 GB of cells); past it the
    // table is marked truncated, like hitting the row cap.
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

struct Best { Program program; double cost = 1e9; int kind = 0; bool test_ok = false; };

// Materialise a solution word (colormap table from fit_colormap) and score it.
std::optional<Best> materialise(uint64_t word, int d, const Task& t, const Spec& spec, const std::vector<gs::DStep>& alpha,
                                const Prefixes* pre) {
    Program p = decode(word, d, alpha, pre);
    Grids all = t.train_in; all.insert(all.end(), t.test_in.begin(), t.test_in.end());
    auto st = run_all(p, all, spec);
    if (!st) return std::nullopt;
    size_t n = t.train_in.size();
    Grids train(st->begin(), st->begin() + n), tests(st->begin() + n, st->end());
    int kind = int(word >> 62);
    if (kind == gs::CMAP) {
        auto table = fit_colormap(train, t.train_out, tests);
        if (!table) return std::nullopt;
        p.push_back(Json(Step{"colormap", *table}));
        for (auto& x : tests) x = apply_colormap(x, *table);
    }
    Best b{p, cost(p), kind, false};
    b.test_ok = !t.test_out.empty() && t.test_out.size() == tests.size();
    for (size_t i = 0; b.test_ok && i < tests.size(); ++i) if (tests[i] != t.test_out[i]) b.test_ok = false;
    return b;
}

Json side_json(double seconds, uint64_t space, const std::vector<uint64_t>& nsol, bool complete, int reached) {
    Json::Array per; uint64_t total = 0;
    for (size_t d = 1; d < nsol.size(); ++d) { per.emplace_back(double(nsol[d])); total += nsol[d]; }
    return Json::Object{{"seconds", seconds}, {"space", double(space)}, {"cands_per_sec", seconds > 0 ? space / seconds : 0.0},
                        {"solutions", double(total)}, {"solutions_per_depth", per}, {"complete", complete}, {"depth_reached", reached}};
}
}

int main(int argc, char** argv) {
    Args a;
    std::string data_dir;
    std::vector<std::string> lists;
    for (int i = 1; i < argc; ++i) {
        std::string k = argv[i];
        if (k == "--stop-first") { a.stop_first = true; continue; }
        if (i + 1 >= argc) { std::cerr << "missing value for " << k << "\n"; return 2; }
        std::string v = argv[++i];
        if (k == "--task") a.tasks.push_back(v);
        else if (k == "--tasks") lists.push_back(v);
        else if (k == "--data-dir") data_dir = v;
        else if (k == "--mode") a.mode = v;
        else if (k == "--depth") a.depth = std::stoi(v);
        else if (k == "--budget") a.budget = std::stod(v);
        else if (k == "--threads") a.threads = std::stoi(v);
        else if (k == "--spec") a.spec = v;
        else if (k == "--out") a.out = v;
        else if (k == "--chunk") a.chunk = std::stoull(v);
        else if (k == "--cap") a.cap = unsigned(std::stoul(v));
        else if (k == "--samples") a.samples = std::stoi(v);
        else if (k == "--kernel") a.shared = v != "flat";
        else if (k == "--dedup") a.dedup = std::stoi(v);
        else if (k == "--prefix-cap") a.prefix_cap = std::stoull(v);
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
    Spec spec(read_json(a.spec));
    bool use_gpu = a.mode != "cpu", use_cpu = a.mode != "gpu";
    if (a.dedup && (use_cpu || a.dedup > 4)) { std::cerr << "--dedup needs --mode gpu and P <= 4\n"; return 2; }
    gs::GpuCtx* ctx = use_gpu ? gs::gpu_open(a.cap) : nullptr;
    std::ofstream file;
    if (!a.out.empty()) file.open(a.out, std::ios::app);
    std::ostream& out = a.out.empty() ? std::cout : file;

    for (const auto& path : a.tasks) {
        Task t;
        try { t = load(path); } catch (const std::exception& e) { std::cerr << path << ": " << e.what() << "\n"; continue; }
        size_t nall = t.train_in.size() + t.test_in.size();
        Json::Object rec{{"task", t.id}};
        if (nall > size_t(gs::MAX_PAIRS)) { rec["skipped"] = "too many pairs"; out << Json(rec).dump() << "\n" << std::flush; continue; }
        auto alpha = alphabet(t);
        rec["alphabet"] = int(alpha.size());
        rec["max_depth"] = a.depth;
        std::vector<std::vector<uint64_t>> gsols(a.depth + 1);
        std::vector<uint64_t> gn(a.depth + 1, 0);
        int found_depth = 0;
        Prefixes pre;
        bool prefix_ok = false;  // prefix table complete (not truncated by --prefix-cap)

        if (use_gpu) {
            gs::DTask dt{};
            std::vector<uint8_t> ins, tgs;
            dt.ntrain = int(t.train_in.size()); dt.nall = int(nall);
            for (size_t i = 0; i < nall; ++i)
                pack(i < t.train_in.size() ? t.train_in[i] : t.test_in[i - t.train_in.size()], ins, dt.ih[i], dt.iw[i], dt.ioff[i]);
            for (size_t i = 0; i < t.train_out.size(); ++i) pack(t.train_out[i], tgs, dt.th[i], dt.tw[i], dt.toff[i]);
            gs::gpu_load(ctx, dt, ins, tgs, alpha);
            auto t0 = Clock::now();
            uint64_t space = 0; bool complete = true; int reached = 0;
            double bfs_seconds = 0;
            for (int d = 1; d <= a.depth && complete; ++d) {
                bool use_prefix = a.dedup > 0 && d > a.dedup;
                if (use_prefix && !pre.plen) {
                    auto b0 = Clock::now();
                    pre = unique_prefixes(t, spec, alpha, a.dedup, a.prefix_cap);
                    prefix_ok = pre.rows < a.prefix_cap && !pre.truncated;
                    gs::gpu_set_prefixes(ctx, pre.table, pre.plen);
                    bfs_seconds = secs(b0);
                    rec["prefixes"] = Json::Object{{"plen", pre.plen}, {"rows", double(pre.rows)}, {"truncated", !prefix_ok}, {"bfs_seconds", bfs_seconds}};
                    if (!pre.rows) break;
                }
                uint64_t total = use_prefix ? pre.rows * ipow(alpha.size(), d - pre.plen) : ipow(alpha.size(), d);
                // The shared kernel ranges over depth-1 prefixes (A programs each).
                uint64_t unit = a.shared ? alpha.size() : 1, threads = total / unit;
                uint64_t step = std::max<uint64_t>(1, a.chunk / unit);
                for (uint64_t s = 0; s < threads; s += step) {
                    if (secs(t0) > a.budget) { complete = false; break; }
                    uint64_t n = std::min(step, threads - s);
                    std::vector<uint64_t> got;
                    gn[d] += gs::gpu_run(ctx, d, s, n, got, use_prefix, a.shared);
                    n *= unit;
                    for (auto w : got) if (gsols[d].size() < a.cap) gsols[d].push_back(w);
                    space += n;
                }
                if (complete) reached = d;
                if (gn[d] && !found_depth) found_depth = d;
                if (a.stop_first && found_depth) break;
            }
            for (auto& v : gsols) std::sort(v.begin(), v.end());
            rec["gpu"] = side_json(secs(t0), space, gn, complete, reached);
        }
        if (use_cpu) {
            CpuSide cpu(t, spec, alpha, a.depth, a.cap);
            auto t0 = Clock::now();
            cpu.run(a.threads);
            uint64_t space = 0;
            for (int d = 1; d <= a.depth; ++d) space += ipow(alpha.size(), d);
            for (auto& v : cpu.sols) std::sort(v.begin(), v.end());
            Json side = side_json(secs(t0), space, cpu.nsol, true, a.depth);
            side.value = [&] { auto o = side.fields(); o["nodes_visited"] = double(cpu.nodes.load()); return o; }();
            rec["cpu"] = side;
            if (use_gpu) {
                bool agree = true;
                for (int d = 1; d <= a.depth; ++d) {
                    if (gn[d] != cpu.nsol[d]) agree = false;
                    if (gn[d] <= a.cap && gsols[d] != cpu.sols[d]) agree = false;
                }
                rec["agree"] = agree;
            } else {
                gsols = cpu.sols; gn = cpu.nsol;
                for (int d = 1; d <= a.depth; ++d) if (gn[d] && !found_depth) found_depth = d;
            }
        }
        // Cheapest solution at the shallowest depth (first 4096 words checked).
        if (found_depth) {
            Best best; int checked = 0;
            for (uint64_t w : gsols[found_depth]) {
                if (++checked > 4096) break;
                auto b = materialise(w, found_depth, t, spec, alpha, pre.plen ? &pre : nullptr);
                if (b && b->cost < best.cost) best = *b;
            }
            if (best.kind) rec["best"] = Json::Object{{"program", best.program}, {"cost", best.cost},
                                                      {"kind", best.kind == gs::EXACT ? "exact" : "colormap"},
                                                      {"depth", found_depth}, {"test_ok", best.test_ok}};
        }
        if (a.samples > 0) {
            // Evenly spaced solution words over all depths, for Python re-checks.
            std::vector<std::pair<int, uint64_t>> all;
            for (int d = 1; d <= a.depth; ++d) for (auto w : gsols[d]) all.emplace_back(d, w);
            Json::Array picked;
            size_t k = std::min<size_t>(a.samples, all.size());
            for (size_t i = 0; i < k; ++i) {
                auto [d, w] = all[i * all.size() / k];
                if (auto b = materialise(w, d, t, spec, alpha, pre.plen ? &pre : nullptr)) picked.emplace_back(b->program);
            }
            rec["samples"] = picked;
        }
        out << Json(rec).dump() << "\n" << std::flush;
    }
    if (ctx) gs::gpu_close(ctx);
    return 0;
}
