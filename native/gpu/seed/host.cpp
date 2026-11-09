// gpuseed: one seed-Enumerator layer on the GPU vs the CPU Enumerator itself.
// CPU (the real seed::Enumerator, included from native/src unchanged) builds
// the bank of sizes < L; the GPU generates + evaluates + fingerprints + dedups
// layer L for all tasks in one launch. Checks per task and layer: fingerprint
// set of new entries and node count equal. Then times layer L: GPU kernel vs
// CPU Enumerator on --threads threads. reports/seed-gpu-1110/.
#include "../../src/seed_enum.cpp"  // Enumerator, Op, Level, splits_cached (read-only include)
#include "gpuseed.hpp"
#include <algorithm>
#include <chrono>
#include <climits>
#include <filesystem>
#include <thread>

using namespace seed;
using gseed::GVal; using gseed::GItem; using gseed::GJob;

namespace {
// first-order primitives the GPU does not implement (enumerated on neither side)
const std::vector<std::string> UNSUPPORTED = {"if", "cons", "append", "concat", "range", "repeat",
                                              "count", "sort", "map", "filter", "zipwith", "fold"};
constexpr int NO_TYPE = -999;  // out_type no entry has: the layer never stops on a hit

struct TaskIn { std::string id; std::vector<arc::Json> ins, outs; };

uint64_t hv(V v) {
    if (tag(v) == T_INT) return gseed::h_int(ival(v));
    if (tag(v) == T_BOOL) return gseed::h_bool(ival(v));
    if (!is_list(v)) throw std::runtime_error("closure value");
    const Store& S = store();
    uint64_t h = gseed::h_list0(S.size(v));
    for (size_t i = 0; i < S.size(v); ++i) h = gseed::h_step(h, hv(S.data(v)[i]));
    return h;
}

// One CPU enumeration (sizes 1..Lmax) of a task with the GPU primitive subset.
struct Cpu {
    Types T;
    LibView lib;
    SubProblem sp;
    std::unique_ptr<Enumerator> E;
    std::vector<int> esize;  // entry -> size
    std::vector<long> nodes_at;  // nodes after size s
    std::vector<V> vals;
    explicit Cpu(const TaskIn& t) : lib(make_view(Lib{}, T)) {
        store().reset(); arena().reset();
        set_exclude(UNSUPPORTED);
        std::vector<V> xs, outs;
        for (const auto& j : t.ins) xs.push_back(from_data(j));
        for (const auto& j : t.outs) outs.push_back(from_data(j));
        std::vector<V> all = xs; all.insert(all.end(), outs.begin(), outs.end());
        sp = SubProblem{xs, outs, T.INPUT, NO_TYPE, {}, false, task_consts(all)};
        E = std::make_unique<Enumerator>(T, lib, sp, LONG_MAX, 2, std::vector<std::pair<int, double>>{}, false);
        vals.resize(xs.size());
        nodes_at.assign(2, 0);
    }
    void level1() {  // Enumerator::run, size 1 (no library blocks, no extras)
        E->bank.push_back(Level{});
        PP in = p_leaf(SY().in);
        E->offer(1, [&] { return in; }, sp.in_type, sp.xs.data());
        for (int64_t c : sp.consts) {
            for (auto& x : vals) x = mk_int(c);
            E->offer(1, [&] { return p_int(c); }, T.INT, vals.data());
        }
        esize.resize(E->entries.size(), 1);
        nodes_at[1] = E->nodes;
    }
    void layer(int size) {  // Enumerator::run, one size
        E->bank.push_back(Level{});
        for (const Op& op : E->ops)
            for (const auto& comp : splits_cached(size - 1, op.arity())) {
                if (op.comm && comp[0] > comp[1]) continue;
                E->apply(size, op, comp, vals);
            }
        esize.resize(E->entries.size(), size);
        nodes_at.push_back(E->nodes);
    }
};

struct Global {  // GPU-side arrays for all tasks
    std::vector<GVal> vals;
    std::vector<int8_t> cells;
    std::vector<GItem> items;
    std::vector<uint32_t> ids;
    std::vector<std::vector<GJob>> jobs;  // per layer
};
struct TaskRes {
    std::string id;
    bool ok = true; std::string why;
    std::vector<int> esize; std::vector<uint64_t> efp;
    std::vector<long> nodes;  // per size
    uint32_t base = 0;
};

bool to_gval(V v, int typ, Types& T, Global& G, GVal& g) {
    g = GVal{}; g.iv = 0;
    if (tag(v) == T_INT) { g.kind = gseed::K_I; g.iv = ival(v); return true; }
    if (tag(v) == T_BOOL) { g.kind = gseed::K_B; g.iv = ival(v); return true; }
    if (!is_list(v)) return false;
    const Store& S = store();
    g.off = uint32_t(G.cells.size());
    size_t n = S.size(v);
    auto cell = [&](V x) {
        if (tag(x) != T_INT || ival(x) < -128 || ival(x) > 127) return false;
        G.cells.push_back(int8_t(ival(x)));
        return true;
    };
    if (typ == T.list(T.INT)) {
        g.kind = gseed::K_L1; g.h = uint16_t(n);
        for (size_t i = 0; i < n; ++i) if (!cell(S.data(v)[i])) return false;
        return true;
    }
    if (typ == T.INPUT) {
        g.kind = gseed::K_L2; g.h = uint16_t(n); g.w = 0;
        for (size_t i = 0; i < n; ++i) {
            V r = S.data(v)[i];
            if (!is_list(r)) return false;
            if (i == 0) g.w = uint16_t(S.size(r));
            else if (S.size(r) != g.w) return false;  // ragged
            for (size_t k = 0; k < S.size(r); ++k) if (!cell(S.data(r)[k])) return false;
        }
        return n ? true : (g.w = 0, true);
    }
    return false;
}

std::vector<TaskIn> load(const std::string& dir, int limit) {
    std::vector<std::string> files;
    for (const auto& e : std::filesystem::directory_iterator(dir))
        if (e.path().extension() == ".json") files.push_back(e.path().string());
    std::sort(files.begin(), files.end());
    if (int(files.size()) > limit) files.resize(size_t(limit));
    std::vector<TaskIn> out;
    for (const auto& f : files) {
        arc::Json j = arc::read_json(f);
        TaskIn t; t.id = std::filesystem::path(f).stem().string();
        for (const auto& ex : j["train"].items()) { t.ins.push_back(ex["input"]); t.outs.push_back(ex["output"]); }
        out.push_back(std::move(t));
    }
    return out;
}

// CPU reference + GPU inputs for one task (sizes 1..Lmax on CPU, jobs for 2..Lmax)
TaskRes prepare(const TaskIn& tin, int Lmax, Global& G) {
    TaskRes R; R.id = tin.id;
    Cpu c(tin);
    c.level1();
    for (int L = 2; L <= Lmax; ++L) c.layer(L);
    Enumerator& E = *c.E;
    size_t n = c.sp.xs.size();
    R.esize = c.esize; R.nodes = c.nodes_at;
    R.base = uint32_t(G.items.size());
    std::vector<GVal> gv(n);
    for (size_t i = 0; i < E.entries.size(); ++i) {
        const auto& e = E.entries[i];
        uint64_t f = gseed::fp_begin(e.typ);
        for (size_t j = 0; j < n; ++j) f = gseed::h_step(f, hv(E.flat[e.voff + j]));
        R.efp.push_back(gseed::fp_end(f));
        G.items.push_back(GItem{uint32_t(G.vals.size()), e.seq});
        bool okv = true;
        for (auto& x : gv) x = GVal{};
        if (c.esize[i] < Lmax)
            for (size_t j = 0; j < n; ++j) okv = okv && to_gval(E.flat[e.voff + j], e.typ, c.T, G, gv[j]);
        if (!okv && R.ok) { R.ok = false; R.why = "value outside GPU layout: " + to_json(e.prog).dump(); }
        G.vals.insert(G.vals.end(), gv.begin(), gv.end());
    }
    // jobs (Enumerator::choose on the type buckets, first-order ops only)
    for (int L = 2; L <= Lmax; ++L) {
        for (const Op& op : E.ops) {
            if (op.prim < 0) { R.ok = false; R.why = "block op"; continue; }
            for (const auto& comp : splits_cached(L - 1, op.arity())) {
                if (op.comm && comp[0] > comp[1]) continue;
                const Level& la = E.bank[size_t(comp[0])];
                for (const auto& ka : la.by) {
                    Subst s1;
                    if (!unify(c.T, resolve(c.T, op.args[0], s1), ka.first, s1)) continue;
                    auto push_ids = [&](const std::vector<uint32_t>& v) {
                        uint32_t off = uint32_t(G.ids.size());
                        for (uint32_t x : v) G.ids.push_back(R.base + x);
                        return off;
                    };
                    if (op.arity() == 1) {
                        GJob j{}; j.aOff = push_ids(ka.second); j.aCnt = uint32_t(ka.second.size());
                        j.bOff = 0; j.bCnt = 1; j.prim = op.prim; j.ret = resolve(c.T, op.ret, s1);
                        j.n = int(n); j.arity = 1; j.comm = 0; j.task = -1;
                        if (j.aCnt) G.jobs[size_t(L)].push_back(j);
                        continue;
                    }
                    const Level& lb = E.bank[size_t(comp[1])];
                    for (const auto& kb : lb.by) {
                        Subst s2 = s1;
                        if (!unify(c.T, resolve(c.T, op.args[1], s2), kb.first, s2)) continue;
                        GJob j{}; j.aOff = push_ids(ka.second); j.aCnt = uint32_t(ka.second.size());
                        j.bOff = push_ids(kb.second); j.bCnt = uint32_t(kb.second.size());
                        j.prim = op.prim; j.ret = resolve(c.T, op.ret, s2); j.n = int(n); j.arity = 2;
                        j.comm = op.comm && comp[0] == comp[1]; j.task = -1;
                        if (j.aCnt && j.bCnt) G.jobs[size_t(L)].push_back(j);
                    }
                }
            }
        }
    }
    return R;
}

double now() { return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count(); }
}  // namespace

int main(int argc, char** argv) {
    std::string data = "../data/ARC-AGI/data/training";
    int limit = 100, Lmax = 3, reps_gpu = 20, reps_cpu = 5, threads = 4;
    for (int i = 1; i + 1 < argc; i += 2) {
        std::string a = argv[i], v = argv[i + 1];
        if (a == "--data") data = v;
        else if (a == "--limit") limit = std::stoi(v);
        else if (a == "--max-layer") Lmax = std::stoi(v);
        else if (a == "--reps-gpu") reps_gpu = std::stoi(v);
        else if (a == "--reps-cpu") reps_cpu = std::stoi(v);
        else if (a == "--threads") threads = std::stoi(v);
    }
    auto tasks = load(data, limit);
    Global G; G.jobs.resize(size_t(Lmax) + 1);
    std::vector<TaskRes> res;
    std::vector<size_t> jobs_from(size_t(Lmax) + 1, 0);
    for (size_t t = 0; t < tasks.size(); ++t) {
        std::vector<size_t> before(size_t(Lmax) + 1);
        for (int L = 2; L <= Lmax; ++L) before[size_t(L)] = G.jobs[size_t(L)].size();
        res.push_back(prepare(tasks[t], Lmax, G));
        for (int L = 2; L <= Lmax; ++L)
            for (size_t k = before[size_t(L)]; k < G.jobs[size_t(L)].size(); ++k) G.jobs[size_t(L)][k].task = int(t);
    }
    printf("{\"tasks\": %zu, \"items\": %zu, \"cells\": %zu, \"unsupported_prims\": \"%s\"}\n", tasks.size(),
           G.items.size(), G.cells.size(), "if cons append concat range repeat count sort map filter zipwith fold");
    for (const auto& r : res) if (!r.ok) printf("{\"task\": \"%s\", \"gpu_unsupported\": \"%s\"}\n", r.id.c_str(), r.why.c_str());

    // CPU timing: the real Enumerator, layer by layer, on `threads` threads
    std::vector<std::vector<double>> tsec(size_t(threads), std::vector<double>(size_t(Lmax) + 1, 0));
    {
        std::vector<std::thread> th;
        for (int w = 0; w < threads; ++w)
            th.emplace_back([&, w] {
                for (size_t t = size_t(w); t < tasks.size(); t += size_t(threads))
                    for (int rep = 0; rep < reps_cpu; ++rep) {
                        Cpu c(tasks[t]);
                        c.level1();
                        for (int L = 2; L <= Lmax; ++L) {
                            double t0 = now();
                            c.layer(L);
                            tsec[size_t(w)][size_t(L)] += now() - t0;
                        }
                    }
            });
        for (auto& x : th) x.join();
    }

    for (int L = 2; L <= Lmax; ++L) {
        auto& jobs = G.jobs[size_t(L)];
        uint64_t ncand = 0;
        for (auto& j : jobs) { j.start = ncand; ncand += uint64_t(j.aCnt) * j.bCnt; }
        std::vector<gseed::GTask> gt(tasks.size());
        std::vector<uint64_t> cand_t(tasks.size(), 0);
        for (const auto& j : jobs) cand_t[size_t(j.task)] += uint64_t(j.aCnt) * j.bCnt;
        uint64_t tabsize = 0;
        for (size_t t = 0; t < tasks.size(); ++t) {
            uint64_t need = 2 * (cand_t[t] + res[t].efp.size()) + 64, cap = 64;
            while (cap < need) cap *= 2;
            gt[t] = gseed::GTask{tabsize, cap - 1};
            tabsize += cap;
        }
        std::vector<uint64_t> table0(tabsize, 0);
        for (size_t t = 0; t < tasks.size(); ++t)
            for (size_t i = 0; i < res[t].efp.size(); ++i) {
                if (res[t].esize[i] >= L) continue;
                uint64_t f = res[t].efp[i], p = f & gt[t].mask;
                while (table0[gt[t].tabOff + p] && table0[gt[t].tabOff + p] != f) p = (p + 1) & gt[t].mask;
                table0[gt[t].tabOff + p] = f;
            }
        gseed::LayerIn in{G.vals.data(), G.vals.size(), G.cells.data(), G.cells.size(), G.items.data(),
                          G.items.size(), G.ids.data(), G.ids.size(), jobs.data(), jobs.size(), ncand,
                          gt.data(), int(tasks.size()), table0.data(), tabsize, reps_gpu};
        std::vector<uint64_t> gnodes(tasks.size());
        std::vector<gseed::GOut> outs(ncand + 1);
        gseed::LayerOut out{gnodes.data(), outs.data(), ncand + 1, 0, 0, 0, 0, 0, 0};
        if (gseed::run_layer(in, out)) { fprintf(stderr, "run_layer failed\n"); return 1; }
        // consistency
        std::vector<std::vector<uint64_t>> gfp(tasks.size());
        for (uint64_t k = 0; k < out.nout && k < out.maxout; ++k) gfp[size_t(outs[k].task)].push_back(outs[k].fp);
        int bad_set = 0, bad_nodes = 0, skipped = 0;
        uint64_t cpu_nodes = 0, gpu_nodes = 0, cpu_new = 0;
        for (size_t t = 0; t < tasks.size(); ++t) {
            const auto& r = res[t];
            if (!r.ok) { ++skipped; continue; }
            std::vector<uint64_t> cf;
            for (size_t i = 0; i < r.efp.size(); ++i) if (r.esize[i] == L) cf.push_back(r.efp[i]);
            std::sort(cf.begin(), cf.end()); std::sort(gfp[t].begin(), gfp[t].end());
            long cn = r.nodes[size_t(L)] - r.nodes[size_t(L) - 1];
            cpu_nodes += uint64_t(cn); gpu_nodes += gnodes[t]; cpu_new += cf.size();
            bool sok = cf == gfp[t], nok = uint64_t(cn) == gnodes[t];
            bad_set += !sok; bad_nodes += !nok;
            if (!sok || !nok)
                printf("{\"layer\": %d, \"task\": \"%s\", \"cpu_new\": %zu, \"gpu_new\": %zu, \"cpu_nodes\": %ld, \"gpu_nodes\": %lu}\n",
                       L, r.id.c_str(), cf.size(), gfp[t].size(), cn, (unsigned long)gnodes[t]);
        }
        double cpu_wall = 0, cpu_sum = 0;
        for (int w = 0; w < threads; ++w) { cpu_wall = std::max(cpu_wall, tsec[size_t(w)][size_t(L)]); cpu_sum += tsec[size_t(w)][size_t(L)]; }
        double cpu_rate = double(cpu_nodes) * reps_cpu / cpu_wall;
        double cpu1_rate = double(cpu_nodes) * reps_cpu / cpu_sum;
        double g_best = double(gpu_nodes) / (out.kernel_ms_best / 1e3);
        double g_mean = double(gpu_nodes) / (out.kernel_ms_mean / 1e3);
        double g_reset = double(gpu_nodes) / ((out.kernel_ms_mean + out.reset_ms_mean) / 1e3);
        printf("{\"layer\": %d, \"tasks_compared\": %zu, \"skipped\": %d, \"set_mismatch\": %d, \"node_mismatch\": %d, "
               "\"cpu_nodes\": %lu, \"gpu_nodes\": %lu, \"cpu_new\": %lu, \"gpu_new\": %lu, \"jobs\": %zu, \"cand_incl_comm_skip\": %lu, "
               "\"cpu%d_wall_s\": %.6f, \"cpu%d_rate\": %.4g, \"cpu_per_thread_rate\": %.4g, \"gpu_kernel_ms_best\": %.4f, "
               "\"gpu_kernel_ms_mean\": %.4f, \"gpu_reset_ms_mean\": %.4f, \"gpu_upload_ms\": %.2f, \"gpu_mb\": %.1f, "
               "\"gpu_rate_best\": %.4g, \"gpu_rate_mean\": %.4g, \"gpu_rate_incl_reset\": %.4g, \"ratio_best\": %.3g, \"ratio_mean\": %.3g}\n",
               L, tasks.size() - size_t(skipped), skipped, bad_set, bad_nodes, (unsigned long)cpu_nodes,
               (unsigned long)gpu_nodes, (unsigned long)cpu_new, (unsigned long)out.nout, jobs.size(),
               (unsigned long)ncand, threads, cpu_wall / reps_cpu, threads, cpu_rate, cpu1_rate, out.kernel_ms_best,
               out.kernel_ms_mean, out.reset_ms_mean, out.upload_ms, double(out.gpu_bytes) / 1e6, g_best, g_mean,
               g_reset, g_best / cpu_rate, g_mean / cpu_rate);
        fflush(stdout);
    }
    return 0;
}
