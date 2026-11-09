// gpgp: GPU genetic program search using the N2 alphabet and evaluator.
// Usage: gpgp --tasks LIST | --task FILE... --out JSONL [--budget SEC]
//        [--data-dir DIR ...] [--pop N] [--island N] [--lmax N] [--linit N]
//        [--tourn N] [--immigrants N] [--migrate N] [--pcx F] [--pmut F]
//        [--seed S] [--random] [--spec native/spec.json]
//        [--holdout loo] [--mdl LAMBDA] [--simplify greedy|min]   (gpgp-ho; defaults = original)
//          --holdout loo: last train pair is hidden from GPU fitness/verdict; a hit
//            counts as solved only if the host re-check also gets that pair right.
//          --mdl L: length penalty L * log2(alphabet) per step (bits) instead of 0.002.
//          --simplify min: shortest sub-program (any steps removed) still fitting train.
//        gpgp --synth OUTDIR --tasks LIST --synth-len L [--synth-per-task N]
//        [--min-depth D] [--attempts N] [--seed S]
#include "gp.hpp"
#include "../../src/background.hpp"
#include "../../src/learners.hpp"
#include "../../src/prims.hpp"
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <memory>
#include <random>
#include <sstream>

using namespace arc;
namespace fs = std::filesystem;
using Clock = std::chrono::steady_clock;
namespace {
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

std::vector<gs::DStep> alphabet(const Task& t, bool all_colors = false) {
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
    if (all_colors) for (int c = 0; c < 10; ++c) to.insert(c);
    for (int x : from) for (int y : to) if (x != y) a.push_back({COLORMAP, uint8_t(x), uint8_t(y), 0});
    return a;
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

void pack(const Grid& g, std::vector<uint8_t>& buf, int& h, int& w, int& off) {
    h = g.h; w = g.w; off = int(buf.size());
    for (int c : g.data) buf.push_back(uint8_t(c));
}

struct Args {
    gs::GpCfg cfg;
    std::vector<std::string> tasks, lists, dirs;
    std::string out, synth, spec = "native/spec.json";
    double budget = 60;
    int synth_len = 0, synth_per_task = 1, min_depth = 4, attempts = 300;
    bool holdout = false, min_simplify = false;
    double mdl = -1;
};

void check_stop() {
    const char* home = std::getenv("HOME");
    if (home && fs::exists(fs::path(home) / "arcagi-STOP"))
        throw std::runtime_error("arcagi-STOP exists; stopped");
}

void load_gpu(gs::GpCtx* ctx, const Task& t, const std::vector<gs::DStep>& alpha) {
    gs::DTask dt{};
    std::vector<uint8_t> inputs, targets;
    dt.ntrain = int(t.train_in.size());
    dt.nall = int(t.train_in.size() + t.test_in.size());
    for (int p = 0; p < dt.nall; ++p)
        pack(p < dt.ntrain ? t.train_in[p] : t.test_in[p - dt.ntrain],
             inputs, dt.ih[p], dt.iw[p], dt.ioff[p]);
    for (int p = 0; p < dt.ntrain; ++p)
        pack(t.train_out[p], targets, dt.th[p], dt.tw[p], dt.toff[p]);
    gs::gp_load(ctx, dt, inputs, targets, alpha);
}

Program genome(gs::GpCtx* ctx, uint32_t idx, const std::vector<gs::DStep>& alpha) {
    std::vector<uint8_t> genes;
    gs::gp_genome(ctx, idx, genes);
    Program p;
    for (auto g : genes) p.emplace_back(to_step(alpha[g]));
    return p;
}

struct Best {
    Program program;
    double cost;
    int kind, depth;
    bool test_ok;
};

// Recheck every train output and legal test prediction with arcsearch's CPU primitives.
std::optional<Best> materialise(const Program& raw, const Task& t, const Spec& spec) {
    Grids all = t.train_in;
    all.insert(all.end(), t.test_in.begin(), t.test_in.end());
    auto states = run_all(raw, all, spec);
    if (!states) return std::nullopt;
    size_t n = t.train_in.size();
    Grids train(states->begin(), states->begin() + n), tests(states->begin() + n, states->end());
    Program p = raw;
    int kind = gs::EXACT;
    if (train != t.train_out) {
        auto table = fit_colormap(train, t.train_out, tests);
        if (!table) return std::nullopt;
        for (size_t i = 0; i < n; ++i)
            if (apply_colormap(train[i], *table) != t.train_out[i]) return std::nullopt;
        p.emplace_back(Step{"colormap", *table});
        for (auto& g : tests) g = apply_colormap(g, *table);
        kind = gs::CMAP;
    }
    for (const auto& g : tests) if (!g.valid()) return std::nullopt;
    bool test_ok = !t.test_out.empty() && t.test_out.size() == tests.size();
    for (size_t i = 0; test_ok && i < tests.size(); ++i)
        if (tests[i] != t.test_out[i]) test_ok = false;
    return Best{p, cost(p), kind, int(raw.size()), test_ok};
}

Best simplify(Program raw, const Task& t, const Spec& spec) {
    Best best = *materialise(raw, t, spec);
    for (;;) {
        bool changed = false;
        for (size_t k = 0; k < raw.size(); ++k) {
            check_stop();
            Program candidate = raw;
            candidate.erase(candidate.begin() + k);
            if (auto b = materialise(candidate, t, spec)) {
                raw = std::move(candidate); best = std::move(*b); changed = true; break;
            }
        }
        if (!changed) return best;
    }
}

// Shortest sub-sequence of raw (steps removed anywhere) that still fits all train pairs.
Best simplify_min(const Program& raw, const Task& t, const Spec& spec) {
    int n = int(raw.size());
    for (int keep = 0; keep < n; ++keep)
        for (uint32_t mask = 0; mask < (1u << n); ++mask) {
            if (__builtin_popcount(mask) != keep) continue;
            check_stop();
            Program candidate;
            for (int k = 0; k < n; ++k) if (mask >> k & 1) candidate.push_back(raw[k]);
            if (auto b = materialise(candidate, t, spec)) return *b;
        }
    return *materialise(raw, t, spec);
}

std::string skip_reason(const Task& t, size_t A) {
    if (t.train_in.size() + t.test_in.size() > size_t(gs::MAX_PAIRS)) return "too many pairs";
    if (A > 256) return "alphabet > 256";
    if (t.train_in.empty()) return "no train pairs";
    return {};
}

void search(gs::GpCtx* ctx, const Task& t, const Spec& spec, const Args& a, std::ostream& out) {
    auto alpha = alphabet(t);
    std::string skip = skip_reason(t, alpha.size());
    if (!skip.empty()) {
        out << Json(Json::Object{{"task", t.id}, {"skipped", skip}}).dump() << '\n' << std::flush;
        return;
    }
    load_gpu(ctx, t, alpha);
    int holdout = a.holdout && t.train_in.size() >= 2 ? int(t.train_in.size()) - 1 : -1;
    float len_pen = a.mdl >= 0 ? float(a.mdl * std::log2(double(alpha.size()))) : a.cfg.len_pen;
    if (a.holdout || a.mdl >= 0) gs::gp_tune(ctx, holdout, len_pen);
    int host_rejects = 0;
    auto start = Clock::now();
    uint32_t gen = 0;
    float best_fitness = -std::numeric_limits<float>::infinity();
    Program partial;
    std::optional<Best> solved;
    double solve_seconds = 0;
    int raw_length = 0;
    do {
        check_stop();
        std::vector<std::pair<uint32_t, uint8_t>> hits;
        uint32_t best_idx;
        float f = gs::gp_eval(ctx, hits, best_idx);
        ++gen;
        if (f > best_fitness) { best_fitness = f; partial = genome(ctx, best_idx, alpha); }
        for (size_t k = 0; k < std::min<size_t>(64, hits.size()); ++k) {
            Program raw = genome(ctx, hits[k].first, alpha);
            if (!materialise(raw, t, spec)) { ++host_rejects; continue; }
            solve_seconds = secs(start);
            raw_length = int(raw.size());
            solved = a.min_simplify ? simplify_min(raw, t, spec) : simplify(std::move(raw), t, spec);
            break;
        }
        if (gen % 200 == 0)
            std::cerr << t.id << " gen=" << gen << " best=" << best_fitness << " seconds=" << secs(start) << '\n';
        if (solved || secs(start) >= a.budget) break;
        gs::gp_breed(ctx, gen);
    } while (true);
    double seconds = secs(start), evals = double(gen) * a.cfg.pop;
    Json::Object rec{{"task", t.id}, {"alphabet", int(alpha.size())}, {"budget", a.budget},
        {"seconds", seconds}, {"generations", double(gen)}, {"evals", evals},
        {"evals_per_sec", seconds > 0 ? evals / seconds : 0.0}, {"best_fitness", double(best_fitness)},
        {"solved", bool(solved)}, {"solve_seconds", solved ? Json(solve_seconds) : Json()},
        {"solve_generation", solved ? Json(double(gen)) : Json()},
        {"raw_length", solved ? Json(raw_length) : Json()}};
    if (a.holdout || a.mdl >= 0 || a.min_simplify) {
        rec["holdout"] = holdout;
        rec["len_pen"] = double(len_pen);
        rec["host_rejects"] = host_rejects;
        rec["simplify"] = a.min_simplify ? "min" : "greedy";
    }
    if (solved) rec["best"] = Json::Object{{"program", solved->program},
        {"kind", solved->kind == gs::EXACT ? "exact" : "colormap"}, {"depth", solved->depth},
        {"test_ok", solved->test_ok}, {"cost", solved->cost}};
    else rec["partial"] = Json::Object{{"program", partial}, {"fitness", double(best_fitness)}};
    out << Json(rec).dump() << '\n' << std::flush;
    if (!out) throw std::runtime_error("cannot write search output");
}

bool shallow_feasible(size_t A, int depth) {
    uint64_t n = 1;
    for (int d = 0; d < depth; ++d) {
        if (n > 2000000000ull / A) return false;
        n *= A;
    }
    return true;
}

bool contains_step(const std::vector<gs::DStep>& alpha, gs::DStep step) {
    return std::any_of(alpha.begin(), alpha.end(), [step](gs::DStep s) {
        return s.op == step.op && s.a == step.a && s.b == step.b;
    });
}

Json task_json(const Task& t) {
    Json::Array train, test;
    for (size_t i = 0; i < t.train_in.size(); ++i)
        train.emplace_back(Json::Object{{"input", to_json(t.train_in[i])}, {"output", to_json(t.train_out[i])}});
    for (size_t i = 0; i < t.test_in.size(); ++i)
        test.emplace_back(Json::Object{{"input", to_json(t.test_in[i])}, {"output", to_json(t.test_out[i])}});
    return Json::Object{{"train", train}, {"test", test}};
}

void synth(gs::GpCtx* ctx, const Task& source, const Spec& spec, const Args& a,
           std::mt19937_64& rng, std::ostream& planted) {
    if (source.train_in.empty() || source.train_in.size() + source.test_in.size() > size_t(gs::MAX_PAIRS)) {
        std::cerr << source.id << " synth skipped: unsupported pair count\n";
        return;
    }
    auto alpha = alphabet(source, true);
    Grids inputs = source.train_in;
    inputs.insert(inputs.end(), source.test_in.begin(), source.test_in.end());
    auto pick = [&]() { return std::uniform_int_distribution<size_t>(0, alpha.size() - 1)(rng); };
    for (int k = 0; k < a.synth_per_task; ++k) {
        bool accepted = false;
        int attempt = 0;
        for (; attempt < a.attempts; ++attempt) {
            check_stop();
            Program program;
            std::vector<gs::DStep> steps;
            for (int d = 0; d < a.synth_len; ++d) {
                auto step = alpha[pick()];
                steps.push_back(step); program.emplace_back(to_step(step));
            }
            Grids states = inputs;
            bool ok = true;
            for (const auto& step : program) {
                auto next = run_all(Program{step}, states, spec);
                if (!next || *next == states) { ok = false; break; }
                states = std::move(*next);
            }
            if (!ok || states == inputs) continue;
            if (std::any_of(states.begin(), states.end(), [](const Grid& g) { return !g.valid(); })) continue;
            Task t;
            t.id = source.id + "-L" + std::to_string(a.synth_len) + "-s" + std::to_string(a.cfg.seed) + "-" + std::to_string(k);
            t.train_in = source.train_in; t.test_in = source.test_in;
            t.train_out.assign(states.begin(), states.begin() + source.train_in.size());
            t.test_out.assign(states.begin() + source.train_in.size(), states.end());
            auto target_alpha = alphabet(t);
            if (!skip_reason(t, target_alpha.size()).empty()) continue;
            for (auto step : steps) if (!contains_step(target_alpha, step)) { ok = false; break; }
            if (!ok) continue;
            bool checked = shallow_feasible(target_alpha.size(), a.min_depth - 1);
            if (checked) {
                load_gpu(ctx, t, target_alpha);
                for (int d = 1; d < a.min_depth; ++d)
                    if (gs::gp_brute(ctx, d)) { ok = false; break; }
            }
            if (!ok) continue;
            check_stop();
            auto path = fs::path(a.synth) / (t.id + ".json");
            if (fs::exists(path)) throw std::runtime_error("synth output already exists: " + path.string());
            write_json(path.string(), task_json(t));
            planted << Json(Json::Object{{"task", t.id}, {"source", source.id}, {"len", a.synth_len},
                {"program", program}, {"shallow_checked", checked}, {"attempts", attempt + 1}}).dump() << '\n' << std::flush;
            if (!planted) throw std::runtime_error("cannot write planted.jsonl");
            std::cerr << source.id << " synth success " << t.id << " attempts=" << attempt + 1
                      << " shallow_checked=" << (checked ? "true" : "false") << '\n';
            accepted = true;
            break;
        }
        if (!accepted) std::cerr << source.id << " synth gave up k=" << k << " attempts=" << attempt << '\n';
    }
}

Args parse(int argc, char** argv) {
    Args a;
    for (int i = 1; i < argc; ++i) {
        std::string key = argv[i];
        if (key == "--random") { a.cfg.random = true; continue; }
        if (i + 1 >= argc) throw std::runtime_error("missing value for " + key);
        std::string v = argv[++i];
        if (key == "--task" || key == "--data-dir") {
            auto& dest = key == "--task" ? a.tasks : a.dirs;
            dest.push_back(v);
            while (i + 1 < argc && std::string(argv[i + 1]).rfind("--", 0) != 0) dest.push_back(argv[++i]);
        } else if (key == "--tasks") a.lists.push_back(v);
        else if (key == "--out") a.out = v;
        else if (key == "--spec") a.spec = v;
        else if (key == "--synth") a.synth = v;
        else if (key == "--budget") a.budget = std::stod(v);
        else if (key == "--pop") a.cfg.pop = std::stoi(v);
        else if (key == "--island") a.cfg.island = std::stoi(v);
        else if (key == "--lmax") a.cfg.lmax = std::stoi(v);
        else if (key == "--linit") a.cfg.linit = std::stoi(v);
        else if (key == "--tourn") a.cfg.tourn = std::stoi(v);
        else if (key == "--immigrants") a.cfg.immigrants = std::stoi(v);
        else if (key == "--migrate") a.cfg.migrate = std::stoi(v);
        else if (key == "--pcx") a.cfg.pcx = std::stof(v);
        else if (key == "--pmut") a.cfg.pmut = std::stof(v);
        else if (key == "--seed") a.cfg.seed = std::stoull(v);
        else if (key == "--holdout") {
            if (v != "loo") throw std::runtime_error("--holdout supports only loo");
            a.holdout = true;
        } else if (key == "--mdl") {
            a.mdl = std::stod(v);
            if (!std::isfinite(a.mdl) || a.mdl < 0) throw std::runtime_error("--mdl must be >= 0");
        } else if (key == "--simplify") {
            if (v != "greedy" && v != "min") throw std::runtime_error("--simplify greedy|min");
            a.min_simplify = v == "min";
        }
        else if (key == "--synth-len") a.synth_len = std::stoi(v);
        else if (key == "--synth-per-task") a.synth_per_task = std::stoi(v);
        else if (key == "--min-depth") a.min_depth = std::stoi(v);
        else if (key == "--attempts") a.attempts = std::stoi(v);
        else throw std::runtime_error("unknown arg " + key);
    }
    if (!std::isfinite(a.budget) || a.budget <= 0) throw std::runtime_error("budget must be positive");
    if (!a.synth.empty() && (a.synth_len < 1 || a.synth_per_task < 1 || a.min_depth < 1 || a.attempts < 1))
        throw std::runtime_error("synth length, count, minimum depth and attempts must be positive");
    if (a.dirs.empty()) a.dirs = {"data/ARC-AGI/data/training", "data/ARC-AGI/data/evaluation"};
    for (const auto& path : a.lists) {
        std::istringstream in(slurp(path));
        std::string line;
        while (std::getline(in, line)) {
            size_t first = line.find_first_not_of(" \t\r");
            if (first == std::string::npos || line[first] == '#') continue;
            line = line.substr(first);
            line = line.substr(0, line.find_first_of(" \t\r,"));
            a.tasks.push_back(line);
        }
    }
    if (a.tasks.empty()) throw std::runtime_error("provide --task FILE... or --tasks LIST");
    for (auto& task : a.tasks) {
        if (task.find('/') != std::string::npos || task.ends_with(".json")) continue;
        std::string found;
        for (const auto& dir : a.dirs) {
            auto path = fs::path(dir) / (task + ".json");
            if (fs::is_regular_file(path)) { found = path.string(); break; }
        }
        if (found.empty()) throw std::runtime_error("cannot resolve task " + task);
        task = std::move(found);
    }
    return a;
}
}

int main(int argc, char** argv) {
    try {
        check_stop();
        Args a = parse(argc, argv);
        Spec spec(read_json(a.spec));
        set_task_background(std::nullopt);
        std::unique_ptr<gs::GpCtx, decltype(&gs::gp_close)> ctx(gs::gp_open(a.cfg), gs::gp_close);
        std::ofstream file;
        if (!a.synth.empty()) {
            fs::create_directories(a.synth);
            file.open(fs::path(a.synth) / "planted.jsonl", std::ios::app);
        } else if (!a.out.empty()) file.open(a.out, std::ios::app);
        if ((!a.synth.empty() || !a.out.empty()) && !file) throw std::runtime_error("cannot open output");
        std::ostream& out = file.is_open() ? file : std::cout;
        std::mt19937_64 rng(a.cfg.seed);
        for (const auto& path : a.tasks) {
            check_stop();
            Task t;
            try { t = load(path); }
            catch (const std::exception& e) { std::cerr << path << ": " << e.what() << '\n'; continue; }
            if (a.synth.empty()) search(ctx.get(), t, spec, a, out);
            else synth(ctx.get(), t, spec, a, rng, out);
        }
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "gpgp: " << e.what() << '\n';
        return 2;
    }
}

