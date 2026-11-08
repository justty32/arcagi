#include "search.hpp"
#include "learners.hpp"
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
    uint64_t nodes=0;
    std::vector<uint64_t> per_depth;
    int limit=0;
    bool stopped=false,out_of_budget=false;
    std::unordered_map<uint64_t,int> seen;
    std::unordered_set<uint64_t> fitted;
    Program path;
    struct Solution { Program program; double value; };
    std::vector<Solution> solutions;

    Search(const Json& request,const Spec& s,Options o):spec(s),opt(o) {
        const Json& task=request["task"];
        for (const auto& e:task["train"].items()) { root.push_back(from_json(e["input"])); targets.push_back(from_json(e["output"])); }
        n=root.size();
        if (!n) fail();
        for (const auto& e:task["test"].items()) root.push_back(from_json(e["input"]));
    }
    double elapsed() const { return std::chrono::duration<double>(Clock::now()-started).count(); }
    bool exhausted(bool force=false) {
        if (nodes>=opt.max_nodes || ((force || !(nodes%1024)) && elapsed()>=opt.budget)) {
            stopped=true; out_of_budget=true;
        }
        return stopped;
    }
    void add(const Grids& tests,const Step* step=nullptr) {
        if (solutions.size()>=opt.max_solutions) return;
        for (const auto& t:tests) if (!t.valid()) return;
        if (step) path.emplace_back(*step);
        solutions.push_back({path,cost(path)});
        if (step) path.pop_back();
    }
    void evaluate(const Grids& grids,uint64_t hash) {
        Grids tests(grids.begin()+n,grids.end());
        bool exact=true,matching=true;
        for (size_t i=0;i<n;++i) {
            if (grids[i]!=targets[i]) exact=false;
            if (!same_shape(grids[i],targets[i])) matching=false;
        }
        if (exact) { add(tests); return; }
        if (!matching || !fitted.insert(hash).second) return;
        Grids train(grids.begin(),grids.begin()+n);
        if (auto table=fit_colormap(train,targets,tests)) {
            Step step={"colormap",*table};
            Grids outs; for (const auto& t:tests) outs.push_back(apply_colormap(t,*table));
            add(outs,&step);
        }
        for (const auto& features:{"n4","n8"}) {
            auto table=fit_local_rule(train,targets,tests,features);
            if (!table) continue;
            Step step={"local_rule",features,*table};
            Grids outs; for (const auto& t:tests) outs.push_back(apply_local_rule(t,features,*table));
            add(outs,&step); break;
        }
    }
    void dfs(const Grids& grids,int depth) {
        if (depth>=limit || stopped) return;
        Grids train(grids.begin(),grids.begin()+n);
        auto expand=[&](const std::string& name) {
            auto choices=candidates(name,train,targets,depth+1==limit);
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
                bool is_root=true;
                for (size_t i=0;i<n;++i) if (child[i]!=root[i]) { is_root=false; break; }
                if (is_root) continue;
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
            if (limit==1) evaluate(root,root_hash);
            if (!exhausted(true)) dfs(root,0);
            if (!solutions.empty() || stopped) break;
        }
        int reached=std::min(limit,opt.max_depth);
        std::stable_sort(solutions.begin(),solutions.end(),[](const auto& a,const auto& b){return a.value<b.value;});
        Json::Array sols,depths;
        for (const auto& s:solutions) sols.emplace_back(Json::Object{{"program",s.program},{"cost",s.value}});
        for (uint64_t v:per_depth) depths.emplace_back(double(v));
        return Json::Object{{"solutions",sols},{"stats",Json::Object{
            {"nodes",double(nodes)},{"nodes_per_depth",depths},{"depth_reached",reached},
            {"elapsed",elapsed()},{"out_of_budget",out_of_budget}}}};
    }
};
}
Json search(const Json& request,const Spec& spec,const Options& options) { return Search(request,spec,options).run(); }
}
