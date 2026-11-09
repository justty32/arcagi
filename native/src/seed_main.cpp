// arcbatch --mode seed | seed-run | seed-sub (see reports/native-s1d/README.md)
#include "seed_enum.hpp"
#include <atomic>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <map>
#include <mutex>
#include <set>
#include <sstream>
#include <thread>

namespace seed {
namespace fs = std::filesystem;
using arc::Json;

namespace {
std::string slurp(const std::string& p) {
    std::ifstream f(p);
    if (!f) throw std::runtime_error("cannot read " + p);
    std::stringstream s;
    s << f.rdbuf();
    return s.str();
}
std::vector<Json> read_jsonl(const std::string& p) {
    std::vector<Json> out;
    std::istringstream in(slurp(p));
    std::string line;
    while (std::getline(in, line)) {
        size_t a = line.find_first_not_of(" \t\r");
        if (a == std::string::npos || line[a] == '#') continue;
        out.push_back(Json::parse(line));
    }
    return out;
}
bool has(const Json& j, const std::string& k) { return j.object() && j.fields().count(k); }
double num(const Json& j) { return std::get<double>(j.value); }
std::string fmt_num(double d) { std::ostringstream o; o.precision(17); o << d; return o.str(); }

fs::path root_dir() {
    fs::path exe = fs::read_symlink("/proc/self/exe");
    return exe.parent_path().parent_path().parent_path();  // native/bin/arcsearch -> repo
}

struct Task { std::string id; std::vector<Example> train, test; };

Task load_task(const std::string& path) {
    Task t;
    t.id = fs::path(path).stem().string();
    Json j = Json::parse(slurp(path));
    for (const auto& e : j["train"].items()) t.train.push_back({e["input"], e["output"], true});
    for (const auto& e : j["test"].items()) {
        bool ho = has(e, "output");
        t.test.push_back({e["input"], ho ? e["output"] : Json(), ho});
    }
    return t;
}

}  // namespace

Lib load_lib(const std::string& path) {
    Lib lib;
    if (path.empty() || !fs::exists(path)) return lib;
    Json j = Json::parse(slurp(path));
    for (const auto& b : j.items()) {
        Block x;
        x.name = b["name"].str();
        x.name_sym = sym(x.name);
        x.body = from_json(b["body"]);
        x.sig = b["sig"].str();
        lib.blocks.push_back(std::move(x));
    }
    return lib;
}

namespace {
struct Config { std::string name; Settings st; Lib lib; std::vector<PP> forbid; };  // forbid: set_forbid

Config parse_config(const Json& j) {
    Config c;
    c.name = has(j, "name") ? j["name"].str() : "default";
    if (has(j, "lib") && std::holds_alternative<std::string>(j["lib"].value)) c.lib = load_lib(j["lib"].str());
    if (has(j, "budget")) c.st.budget = long(num(j["budget"]));
    if (has(j, "lam_depth")) c.st.lam_depth = int(num(j["lam_depth"]));
    if (has(j, "decomp")) {
        const Json& d = j["decomp"];
        if (std::holds_alternative<bool>(d.value)) c.st.decompose = std::get<bool>(d.value);
        else {
            c.st.decompose = !d.items().empty();
            for (const auto& x : d.items()) c.st.splits.push_back(x.str());
        }
    }
    if (has(j, "exclude")) for (const auto& x : j["exclude"].items()) c.st.exclude.push_back(x.str());
    if (has(j, "order") && j["order"].object())
        for (const auto& kv : j["order"].fields()) c.st.order.push_back({kv.first, num(kv.second)});
    if (has(j, "forbid")) for (const auto& x : j["forbid"].items()) c.forbid.push_back(from_json(x));
    for (const auto& e : c.st.exclude) prim_of_sym(sym(e));
    { Types T; for (const auto& b : c.lib.blocks) T.parse(b.sig); }  // intern type variable names
    return c;
}

Json result_json(const Config& c, const Task& t, const SolveOut& r, long forbidden) {
    Json::Array near;
    for (const auto& kv : r.near) near.push_back(Json(Json::Array{to_json(kv.first), Json(kv.second)}));
    Json::Object o{{"config", c.name}, {"task_id", t.id},
                   {"program", r.program ? to_json(r.program) : Json()},
                   {"train_ok", r.train_ok}, {"test_ok", r.test_ok},
                   {"nodes", Json(double(r.nodes))},
                   {"nodes_to_first", r.nodes_to_first < 0 ? Json() : Json(double(r.nodes_to_first))},
                   {"seconds", r.seconds}, {"near", Json(near)},
                   {"eval_steps", Json(double(r.eval_steps))}};
    if (!c.forbid.empty()) o["forbidden"] = Json(double(forbidden));
    if (!r.error.empty()) o["error"] = Json(r.error);
    return Json(o);
}

template <class F>
void parallel(size_t n, int threads, F&& f) {
    std::atomic<size_t> next{0};
    std::vector<std::thread> pool;
    for (int k = 0; k < std::max(1, threads); ++k)
        pool.emplace_back([&] {
            for (size_t i; (i = next++) < n;) f(i);
        });
    for (auto& th : pool) th.join();
}

int mode_seed(const std::map<std::string, std::vector<std::string>>& a, int threads, std::ostream& out) {
    std::string data_dir = a.count("--data-dir") ? a.at("--data-dir")[0]
                                                 : (root_dir() / "data/ARC-AGI/data/training").string();
    std::vector<std::string> paths;
    auto add_id = [&](const std::string& id) { paths.push_back((fs::path(data_dir) / (id + ".json")).string()); };
    if (a.count("--taskset")) {
        Json ts = Json::parse(slurp(a.at("--taskset")[0]));
        std::vector<std::string> splits;
        if (a.count("--split")) {
            std::stringstream ss(a.at("--split")[0]);
            for (std::string s; std::getline(ss, s, ',');) splits.push_back(s);
        } else {
            for (const auto& kv : ts.fields()) if (kv.second.array()) splits.push_back(kv.first);
        }
        for (const auto& s : splits) {
            if (!has(ts, s)) throw std::runtime_error("taskset has no split " + s);
            for (const auto& e : ts[s].items())
                add_id(std::holds_alternative<std::string>(e.value) ? e.str() : e["task_id"].str());
        }
    }
    if (a.count("--tasks"))
        for (const auto& list : a.at("--tasks")) {
            std::istringstream in(slurp(list));
            for (std::string line; std::getline(in, line);) {
                size_t b = line.find_first_not_of(" \t\r");
                if (b == std::string::npos || line[b] == '#') continue;
                std::string w = line.substr(b, line.find_first_of(" \t\r,", b) - b);
                if (w.size() > 5 && w.substr(w.size() - 5) == ".json")
                    paths.push_back((fs::path(list).parent_path() / w).string());
                else add_id(w);
            }
        }
    if (a.count("--task")) for (const auto& p : a.at("--task")) paths.push_back(p);
    if (a.count("--ids")) {  // keep only these task ids (taskset subsets, e.g. CRN draws)
        std::set<std::string> keep;
        std::stringstream ss(a.at("--ids")[0]);
        for (std::string s; std::getline(ss, s, ',');) keep.insert(s);
        std::vector<std::string> p2;
        for (const auto& p : paths) if (keep.count(fs::path(p).stem().string())) p2.push_back(p);
        paths.swap(p2);
    }
    std::vector<Task> tasks;
    for (const auto& p : paths) tasks.push_back(load_task(p));
    std::vector<Config> configs;
    if (a.count("--configs")) for (const auto& j : read_jsonl(a.at("--configs")[0])) configs.push_back(parse_config(j));
    else configs.push_back(parse_config(Json(Json::Object{})));
    for (const auto& c : configs) {
        auto t0 = std::chrono::steady_clock::now();
        std::vector<Json> rows(tasks.size());
        std::vector<SolveOut> res(tasks.size());
        std::vector<long> fcount(tasks.size(), 0);
        parallel(tasks.size(), threads, [&](size_t i) {
            set_forbid(&c.forbid);  // thread-local; empty = off
            res[i] = solve_task(tasks[i].train, tasks[i].test, c.lib, c.st);
            fcount[i] = forbid_count();
            set_forbid(nullptr);
            rows[i] = result_json(c, tasks[i], res[i], fcount[i]);
        });
        double wall = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
        long nodes = 0, solved = 0, train_ok = 0, errors = 0, forbidden = 0;
        double secs = 0;
        for (size_t i = 0; i < rows.size(); ++i) {
            out << rows[i].dump() << '\n';
            nodes += res[i].nodes; solved += res[i].test_ok; train_ok += res[i].train_ok;
            secs += res[i].seconds; errors += !res[i].error.empty(); forbidden += fcount[i];
        }
        Json::Object summ{{"config", c.name}, {"summary", true}, {"tasks", int(tasks.size())},
                          {"solved", int(solved)}, {"train_ok", int(train_ok)}, {"errors", int(errors)},
                          {"nodes", double(nodes)}, {"task_seconds", secs}, {"wall_seconds", wall},
                          {"threads", threads}};
        if (!c.forbid.empty()) summ["forbidden"] = Json(double(forbidden));
        out << Json(summ).dump() << '\n';
        out.flush();
    }
    return 0;
}

int mode_run(const std::map<std::string, std::vector<std::string>>& a, int threads, std::ostream& out) {
    std::vector<Json> jobs = read_jsonl(a.at("--programs")[0]);
    std::map<std::string, Lib> libs;
    for (const auto& j : jobs)
        if (has(j, "lib")) { std::string p = j["lib"].str(); if (!libs.count(p)) libs[p] = load_lib(p); }
    std::vector<PP> progs;
    for (const auto& j : jobs) progs.push_back(from_json(j["program"]));
    std::vector<std::string> outs(jobs.size());
    static const Lib empty;
    parallel(jobs.size(), threads, [&](size_t i) {
        const Json& j = jobs[i];
        const Lib& lib = has(j, "lib") ? libs.at(j["lib"].str()) : empty;
        std::vector<std::string> ex;
        if (has(j, "exclude")) for (const auto& x : j["exclude"].items()) ex.push_back(x.str());
        Json::Array vals;
        if (has(j, "inputs")) for (const auto& x : j["inputs"].items()) vals.push_back(run_json(progs[i], x, lib, ex));
        Json::Object o{{"values", Json(vals)}};
        if (has(j, "input")) o["value"] = run_json(progs[i], j["input"], lib, ex);  // single-input form
        if (has(j, "id")) o["id"] = j["id"];
        outs[i] = Json(o).dump();
    });
    for (const auto& s : outs) out << s << '\n';
    return 0;
}

// One subproblem per line: notes/rounds/r08/05-S1介面規格.md §7, e.g.
// {"id", "lib", "budget": N, "examples": [[in, out], ...], "in_type", "out_type",
//  "extra": [{"leaf": "$u", "type": "...", "vals": [...]}], "sub": bool, "consts": [...],
//  "lam_depth": 2, "lam_body_max": 4, "order": {}, "exclude": [], "cond_limit": null|N}
// "budget" is the Enumerator budget. cond_limit: absolute limit of cond_witness;
// alternatively "cond_budget": the _direct budget (limit = cond_budget - nodes,
// as seed.decomp._Solver._direct computes it). "near" overrides keep-near (default !sub).
int mode_sub(const std::map<std::string, std::vector<std::string>>& a, int threads, std::ostream& out) {
    std::vector<Json> jobs = read_jsonl(a.at("--subproblems")[0]);
    std::map<std::string, Lib> libs;
    for (const auto& j : jobs)
        if (has(j, "lib") && !std::holds_alternative<std::nullptr_t>(j["lib"].value)) {
            std::string p = j["lib"].str();
            if (!libs.count(p)) libs[p] = load_lib(p);
        }
    std::vector<std::vector<PP>> extra_progs(jobs.size());
    for (size_t i = 0; i < jobs.size(); ++i) {  // parse on this thread (symbols)
        const Json& j = jobs[i];
        Types T;
        if (has(j, "in_type")) T.parse(j["in_type"].str());
        if (has(j, "out_type")) T.parse(j["out_type"].str());
        if (has(j, "extra"))
            for (const auto& e : j["extra"].items()) {
                T.parse(e["type"].str());
                extra_progs[i].push_back(has(e, "leaf") ? p_leaf(sym(e["leaf"].str())) : from_json(e["prog"]));
            }
        if (has(j, "order")) for (const auto& kv : j["order"].fields()) sym(kv.first);
        if (has(j, "exclude")) for (const auto& x : j["exclude"].items()) sym(x.str());
    }
    for (const auto& kv : libs) { Types T; for (const auto& b : kv.second.blocks) T.parse(b.sig); }
    std::vector<std::string> outs(jobs.size());
    static const Lib empty;
    parallel(jobs.size(), threads, [&](size_t i) {
        const Json& j = jobs[i];
        auto t0 = std::chrono::steady_clock::now();
        Json::Object o;
        try {
            store().reset();
            arena().reset();
            Types T;
            const Lib& lib_in = libs.count(has(j, "lib") && j["lib"].object() == false &&
                                           std::holds_alternative<std::string>(j["lib"].value) ? j["lib"].str() : "")
                                    ? libs.at(j["lib"].str()) : empty;
            LibView lib = make_view(lib_in, T);
            std::vector<std::string> ex;
            if (has(j, "exclude")) for (const auto& x : j["exclude"].items()) ex.push_back(x.str());
            set_exclude(ex);
            SubProblem sp;
            if (has(j, "examples"))
                for (const auto& e : j["examples"].items()) { sp.xs.push_back(from_data(e[0])); sp.outs.push_back(from_data(e[1])); }
            else {
                for (const auto& x : j["xs"].items()) sp.xs.push_back(from_data(x));
                for (const auto& x : j["outs"].items()) sp.outs.push_back(from_data(x));
            }
            sp.in_type = has(j, "in_type") ? T.parse(j["in_type"].str()) : T.INPUT;
            sp.out_type = has(j, "out_type") ? T.parse(j["out_type"].str()) : T.INPUT;
            sp.sub = has(j, "sub") && std::get<bool>(j["sub"].value);
            if (has(j, "lam_body_max")) sp.lam_body_max = int(num(j["lam_body_max"]));
            if (has(j, "extra")) {
                size_t k = 0;
                for (const auto& e : j["extra"].items()) {
                    std::vector<V> vals;
                    for (const auto& x : e["vals"].items()) vals.push_back(from_data(x));
                    sp.extra.push_back({extra_progs[i][k++], T.parse(e["type"].str()), vals});
                }
            }
            if (has(j, "consts")) for (const auto& x : j["consts"].items()) sp.consts.push_back(int64_t(num(x)));
            else {
                std::vector<V> all = sp.xs;
                all.insert(all.end(), sp.outs.begin(), sp.outs.end());
                sp.consts = task_consts(all);
            }
            long budget = has(j, "budget") ? long(num(j["budget"])) : 100000;
            bool cond = false, cond_abs = false;
            long cond_lim = 0;
            if (has(j, "cond_limit") && !std::holds_alternative<std::nullptr_t>(j["cond_limit"].value)) {
                cond = true; cond_abs = true; cond_lim = long(num(j["cond_limit"]));
            } else if (has(j, "cond_budget") && !std::holds_alternative<std::nullptr_t>(j["cond_budget"].value)) {
                cond = true; cond_lim = long(num(j["cond_budget"]));
            }
            bool keep_near = has(j, "near") ? std::get<bool>(j["near"].value) : !sp.sub;
            int ld = has(j, "lam_depth") ? int(num(j["lam_depth"])) : 2;
            std::vector<std::pair<int, double>> order;
            if (has(j, "order")) for (const auto& kv : j["order"].fields()) order.push_back({sym(kv.first), num(kv.second)});
            DirectOut d = run_enum(T, lib, sp, budget, ld, order, cond, cond_lim, keep_near, cond_abs);
            Json::Array near;
            for (const auto& kv : d.near) near.push_back(Json(Json::Array{to_json(kv.first), Json(kv.second)}));
            PP enum_prog = d.cond_hit ? nullptr : d.prog;
            o = Json::Object{{"program", enum_prog ? to_json(enum_prog) : Json()}, {"nodes", double(d.nodes)},
                             {"nodes_to_first", d.first < 0 ? Json() : Json(double(d.first))},
                             {"near", Json(near)}, {"eval_steps", double(d.eval_steps)}};
            if (cond)
                o["cond"] = Json(Json::Object{{"program", d.cond_hit ? to_json(d.prog) : Json()},
                                              {"used", double(d.cond_used)}});
        } catch (const std::exception& e) {
            o = Json::Object{{"program", Json()}, {"error", std::string(e.what())}};
        } catch (...) {
            o = Json::Object{{"program", Json()}, {"error", "EvalError raised during search (LamEntry compile)"}};
        }
        set_exclude({});
        o["seconds"] = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
        if (has(j, "id")) o["id"] = j["id"];
        outs[i] = Json(o).dump();
    });
    for (const auto& s : outs) out << s << '\n';
    return 0;
}
}  // namespace

int seed_main(int argc, char** argv) {
    // argv: ... --mode MODE [options]; options may repeat (--tasks, --task)
    std::map<std::string, std::vector<std::string>> a;
    std::string mode;
    for (int i = 1; i < argc; ++i) {
        std::string k = argv[i];
        if (k == "--batch") continue;
        if (i + 1 >= argc) throw std::runtime_error("missing value for " + k);
        std::string v = argv[++i];
        if (k == "--mode") mode = v;
        else a[k].push_back(v);
    }
    int threads = a.count("--threads") ? std::stoi(a["--threads"][0]) : 6;
    // intern every primitive symbol before threads start
    prim_of_sym(sym("add"));
    for (const char* s : {"$in", "$0", "$1", "lam", "blk", "$h0", "$h1", "$i", "if", "map", "zipwith", "range",
                          "len", "take", "append", "transpose", "reverse"})
        sym(s);
    std::ofstream file;
    std::ostream* out = &std::cout;
    if (a.count("--out")) { file.open(a["--out"][0]); out = &file; }
    if (mode == "seed") return mode_seed(a, threads, *out);
    if (mode == "seed-run") return mode_run(a, threads, *out);
    if (mode == "seed-sub") return mode_sub(a, threads, *out);
    throw std::runtime_error("unknown --mode " + mode);
}
}  // namespace seed
