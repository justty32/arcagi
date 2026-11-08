#include "search.hpp"
#include "learners.hpp"
#include "objects.hpp"
#include <algorithm>
#include <chrono>
#include <unordered_map>

namespace arc {
namespace {
using Clock=std::chrono::steady_clock;
struct Search {
    const Spec& spec;
    Options opt;
    Grids root,targets;
    size_t n;
    Clock::time_point started=Clock::now();
    uint64_t nodes=0,prefix_order=0;
    std::vector<uint64_t> per_depth;
    int limit=0;
    bool stopped=false,out_of_budget=false,seeded=false;
    std::unordered_map<uint64_t,int> seen;
    std::unordered_set<uint64_t> fitted;
    Program path;
    struct Seed { Program program; Grids grids; };
    std::vector<Seed> seeds;
    struct Solution { Program program; double value; bool seeded; };
    std::vector<Solution> solutions;
    struct Prefix { Program program; double acc; uint64_t order,hash; };
    std::vector<Prefix> prefixes;

    Search(const Json& request,const Spec& s,Options o):spec(s),opt(std::move(o)) {
        const Json& task=request["task"];
        Grids context;
        for (const auto& e:task["train"].items()) { root.push_back(from_json(e["input"])); targets.push_back(from_json(e["output"])); }
        n=root.size();
        if (!n) fail();
        context=root; context.insert(context.end(),targets.begin(),targets.end());
        set_task_background(task_background(context));
        for (const auto& e:task["test"].items()) root.push_back(from_json(e["input"]));
        for (const auto& seed:opt.seeds) {
            Seed entry{seed["program"].items(),{}};
            if (entry.program.empty() || seed["grids"].size()!=root.size()) continue;
            bool ok=true;
            for (const auto& g:seed["grids"].items()) {
                entry.grids.push_back(from_json(g));
                if (!entry.grids.back().bounds()) ok=false;
            }
            if (ok) seeds.push_back(std::move(entry));
        }
    }
    double elapsed() const { return std::chrono::duration<double>(Clock::now()-started).count(); }
    bool exhausted() {
        if (nodes>=opt.max_nodes || elapsed()>=opt.budget) { stopped=true; out_of_budget=true; }
        return stopped;
    }
    void add(const Grids& tests,const Step* step=nullptr) {
        if (solutions.size()>=opt.max_solutions) return;
        for (const auto& t:tests) if (!t.valid()) return;
        if (step) path.emplace_back(*step);
        solutions.push_back({path,cost(path),seeded});
        if (step) path.pop_back();
    }
    static bool better(const Prefix& a,const Prefix& b) {
        if (a.acc!=b.acc) return a.acc>b.acc;
        if (a.program.size()!=b.program.size()) return a.program.size()<b.program.size();
        return a.order<b.order;
    }
    void remember_prefix(const Grids& grids,uint64_t hash) {
        if (!opt.dump_prefixes || path.empty() || path.size()>2) return;
        double acc=0;
        for (size_t i=0;i<n;++i) {
            size_t same=0;
            for (size_t j=0;j<grids[i].data.size();++j) same+=grids[i].data[j]==targets[i].data[j];
            acc+=double(same)/targets[i].data.size();
        }
        Prefix entry{path,acc/n,prefix_order++,hash};
        for (auto& p:prefixes) if (p.hash==hash) {
            if (better(entry,p)) p=std::move(entry);
            return;
        }
        if (prefixes.size()<opt.dump_prefixes) prefixes.push_back(std::move(entry));
        else {
            auto worst=std::max_element(prefixes.begin(),prefixes.end(),better);
            if (better(entry,*worst)) *worst=std::move(entry);
        }
    }
    void evaluate(const Grids& grids,uint64_t hash) {
        Grids tests(grids.begin()+n,grids.end());
        bool exact=true,matching=true;
        for (size_t i=0;i<n;++i) {
            if (grids[i]!=targets[i]) exact=false;
            if (!same_shape(grids[i],targets[i])) matching=false;
        }
        if (exact) { add(tests); return; }
        if (!matching) return;
        remember_prefix(grids,hash);
        if (!fitted.insert(hash).second || exhausted()) return;
        Grids train(grids.begin(),grids.begin()+n);
        if (auto table=fit_colormap(train,targets,tests)) {
            Step step={"colormap",*table};
            Grids outs; for (const auto& t:tests) outs.push_back(apply_colormap(t,*table));
            add(outs,&step);
        }
        if (exhausted()) return;
        if (auto table=fit_object_colormap(train,targets,tests)) {
            Step step={"object_colormap",*table};
            Grids outs; for (const auto& t:tests) outs.push_back(apply_object_colormap(t,*table));
            add(outs,&step);
        }
        for (const auto& features:{"n4","n8"}) {
            if (exhausted()) return;
            auto table=fit_local_rule(train,targets,tests,features);
            if (!table) continue;
            Step step={"local_rule",features,*table};
            Grids outs; for (const auto& t:tests) outs.push_back(apply_local_rule(t,features,*table));
            add(outs,&step); break;
        }
    }
    void dfs(const Grids& grids,int depth) {
        if (depth>=limit || exhausted()) return;
        Grids train(grids.begin(),grids.begin()+n);
        auto expand=[&](const std::string& name) {
            if (name=="colormap" && !path.empty() && path.back()[0]==Json("colormap")) return;
            if (exhausted()) return;
            auto choices=candidates(name,train,targets,depth+1==limit,spec);
            for (const auto& step:choices) {
                if (exhausted()) return;
                ++nodes; ++per_depth[depth];
                Grids child;
                bool ok=true;
                try {
                    for (const auto& g:grids) {
                        child.push_back(apply_step(step,g,spec));
                        if (!child.back().bounds()) { ok=false; break; }
                    }
                } catch (const std::exception&) { ok=false; }
                if (!ok) continue;
                uint64_t hash=signature(child,n);
                auto [it,inserted]=seen.emplace(hash,depth+1);
                if (!inserted) {
                    if (it->second<=depth+1) continue;
                    it->second=depth+1;
                }
                path.emplace_back(step);
                evaluate(child,hash);
                dfs(child,depth+1);
                path.pop_back();
                if (stopped) return;
            }
        };
        for (const auto& name:spec.names) { expand(name); if (stopped) return; }
        expand("colormap");
    }
    Json run() {
        uint64_t root_hash=signature(root,n);
        for (limit=1;limit<=opt.max_depth;++limit) {
            per_depth.resize(limit,0);
            seen.clear(); seen.emplace(root_hash,0);
            seeded=false; path.clear();
            if (limit==1) evaluate(root,root_hash);
            if (!exhausted()) dfs(root,0);
            for (const auto& seed:seeds) {
                if (exhausted()) break;
                int depth=int(seed.program.size());
                if (depth>=limit) continue;
                uint64_t hash=signature(seed.grids,n);
                auto [it,inserted]=seen.emplace(hash,depth);
                if (!inserted && it->second<=depth) continue;
                it->second=depth;
                path=seed.program; seeded=true;
                evaluate(seed.grids,hash);
                dfs(seed.grids,depth);
            }
            if (!solutions.empty() || stopped) break;
        }
        int reached=std::min(limit,opt.max_depth);
        std::stable_sort(solutions.begin(),solutions.end(),[](const auto& a,const auto& b){return a.value<b.value;});
        std::stable_sort(prefixes.begin(),prefixes.end(),better);
        Json::Array sols,depths,dumped;
        for (const auto& s:solutions) sols.emplace_back(Json::Object{{"program",s.program},{"cost",s.value},{"origin",s.seeded?"seed":"cpp"}});
        for (const auto& p:prefixes) dumped.emplace_back(Json::Object{{"program",p.program},{"acc",p.acc}});
        if (!opt.prefix_out.empty()) write_json(opt.prefix_out,dumped);
        for (uint64_t v:per_depth) depths.emplace_back(double(v));
        double seconds=elapsed();
        return Json::Object{{"solutions",sols},{"stats",Json::Object{
            {"nodes",double(nodes)},{"nodes_per_depth",depths},{"depth_reached",reached},
            {"elapsed",seconds},{"nodes_per_second",seconds>0?nodes/seconds:0},
            {"seeds",int(seeds.size())},{"prefixes",int(prefixes.size())},{"out_of_budget",out_of_budget}}}};
    }
};
}
Json search(const Json& request,const Spec& spec,const Options& options) { return Search(request,spec,options).run(); }
}
