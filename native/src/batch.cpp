// Batch evaluation: many (config, task) jobs in one process, C++ only.
// See reports/native-s1c/README.md for the config and output formats.
#include "batch.hpp"
#include "background.hpp"
#include "search.hpp"
#include <algorithm>
#include <atomic>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <mutex>
#include <sstream>
#include <thread>

namespace arc {
namespace {
const std::set<std::string> LEARNERS_={"colormap","object_colormap","local_rule","x_vrule"};
const std::set<std::string> PENALIZED_={"local_rule","x_vrule"};
double gnum(const Json::Object& o,const std::string& k,double d) {
    auto it=o.find(k); return it==o.end()?d:std::get<double>(it->second.value);
}
size_t table_rows(const Step& s) {
    const std::string& n=s[0].str();
    if (n=="local_rule" || n=="x_vrule") return s[2].size();
    if (n=="colormap") return s[1].size();
    if (n=="object_colormap") return s[1][2].size();
    return 0;
}
}
Gate Gate::from_json(const Json& j) {
    Gate g; const auto& o=j.fields();
    g.max_len_penalized=int(gnum(o,"max_len_penalized",g.max_len_penalized));
    g.max_steps_before_learner=int(gnum(o,"max_steps_before_learner",g.max_steps_before_learner));
    g.min_votes=gnum(o,"min_votes",g.min_votes);
    g.max_table_rows=int(gnum(o,"max_table_rows",g.max_table_rows));
    g.support_alone=gnum(o,"support_alone",g.support_alone);
    g.support_after=gnum(o,"support_after",g.support_after);
    return g;
}

bool Gate::rejects(const Program& p,double train_cells) const {
    if (p.empty()) return false;
    const std::string& last=p.back()[0].str();
    if (max_len_penalized>=0 && int(p.size())>max_len_penalized && PENALIZED_.contains(last)) return true;
    if (max_steps_before_learner>=0 && LEARNERS_.contains(last) && int(p.size())-1>max_steps_before_learner) return true;
    if (max_table_rows>=0 && LEARNERS_.contains(last) && int(table_rows(p.back().items()))>max_table_rows) return true;
    if (PENALIZED_.contains(last)) {
        double rows=double(table_rows(p.back().items()));
        if (rows>0 && train_cells/rows<(p.size()==1?support_alone:support_after)) return true;
    }
    return false;
}

namespace {
namespace fs=std::filesystem;
using Clock=std::chrono::steady_clock;

const std::set<std::string> LEARNERS={"colormap","object_colormap","local_rule","x_vrule"};
const std::set<std::string> PENALIZED={"local_rule","x_vrule"};

struct Task { std::string id,text; Json train,test_inputs; Grids test_outputs; };
struct Config { std::string name; Spec spec; Options opt; Gate gate; std::string key; };

uint64_t fnv(const std::string& s,uint64_t h=1469598103934665603ull) {
    for (unsigned char c:s) { h^=c; h*=1099511628211ull; }
    return h;
}
std::string hex(uint64_t v) { std::ostringstream o; o<<std::hex<<v; return o.str(); }
std::string slurp(const std::string& path) {
    std::ifstream in(path,std::ios::binary);
    if (!in) throw std::runtime_error("cannot read "+path);
    std::ostringstream o; o<<in.rdbuf(); return o.str();
}
double num(const Json::Object& o,const std::string& k,double d) {
    auto it=o.find(k); return it==o.end()?d:std::get<double>(it->second.value);
}
std::set<std::string> names_of(const Json& j) {
    std::set<std::string> out; for (const auto& n:j.items()) out.insert(n.str()); return out;
}

// Expand macro references inside a program, so macros may use macros.
void flatten(const Program& program,const std::map<std::string,Program>& macros,Program& out,int depth=0) {
    if (depth>8) throw std::runtime_error("macro nesting too deep");
    for (const auto& step:program) {
        auto it=macros.find(step[0].str());
        if (it!=macros.end() && step.size()==1) flatten(it->second,macros,out,depth+1);
        else out.push_back(step);
    }
}

Config make_config(const Json& j,const Spec& base) {
    const auto& o=j.fields();
    Config c{o.contains("name")?j["name"].str():"default",base,{},{},j.dump()};
    if (o.contains("macros")) {
        std::map<std::string,Program> raw;
        for (const auto& [name,program]:j["macros"].fields()) raw[name]=program.items();
        for (const auto& [name,program]:raw) {
            Program flat; flatten(program,raw,flat);
            for (const auto& step:flat)
                if (!ported().contains(step[0].str())) throw std::runtime_error("macro "+name+" uses unported "+step[0].str());
            c.spec.macros[name]=flat;
            if (c.spec.live.insert(name).second) c.spec.names.push_back(name);
        }
    }
    if (o.contains("prims")) {
        auto keep=names_of(j["prims"]);
        if (o.contains("macros")) for (const auto& [name,_]:j["macros"].fields()) keep.insert(name);
        std::erase_if(c.spec.names,[&](const std::string& n){ return !keep.contains(n); });
    }
    if (o.contains("drop")) {
        auto drop=names_of(j["drop"]);
        std::erase_if(c.spec.names,[&](const std::string& n){ return drop.contains(n); });
    }
    if (o.contains("learners")) {
        auto l=names_of(j["learners"]);
        c.opt.learn_colormap=l.contains("colormap");
        c.opt.colormap_step=l.contains("colormap_step");
        c.opt.learn_object_colormap=l.contains("object_colormap");
        c.opt.learn_local_rule=l.contains("local_rule");
        c.opt.learn_vrule=l.contains("x_vrule");
    }
    c.opt.budget=num(o,"budget",60.0);
    c.opt.max_depth=int(num(o,"max_depth",4));
    c.opt.max_nodes=uint64_t(num(o,"max_nodes",2e6));
    c.opt.max_solutions=size_t(num(o,"max_solutions",200));
    if (o.contains("gate")) c.gate=Gate::from_json(j["gate"]);
    return c;
}

Task load_task(const std::string& path) {
    Task t; t.text=slurp(path); t.id=fs::path(path).stem().string();
    Json j=Json::parse(t.text);
    t.train=j["train"];
    Json::Array tests;
    for (const auto& e:j["test"].items()) {
        tests.emplace_back(Json::Object{{"input",e["input"]}});
        if (e.fields().contains("output")) t.test_outputs.push_back(from_json(e["output"]));
    }
    t.test_inputs=Json(tests);
    return t;
}

struct Solved { Program program; double cost; size_t order; Grids tests; double votes=0; bool penalized=false; };

std::string key_of(const Grids& tests) {
    std::string k;
    for (const auto& g:tests) { k+=std::to_string(g.h)+"x"+std::to_string(g.w)+":"; for (int c:g.data) k+=char('0'+c); k+='|'; }
    return k;
}

struct Choice { Solved* top=nullptr; size_t gated=0; };
Choice choose(std::vector<Solved>& sols,const Gate& gate,double train_cells) {
    Choice out;
    std::vector<Solved*> kept;
    std::map<std::string,double> votes;
    for (auto& s:sols) {
        if (gate.rejects(s.program,train_cells)) { ++out.gated; continue; }
        bool learner=std::any_of(s.program.begin(),s.program.end(),[](const Json& st){ return LEARNERS.contains(st[0].str()); });
        votes[key_of(s.tests)]+=learner?0.5:1.0;
        s.penalized=std::any_of(s.program.begin(),s.program.end(),[](const Json& st){ return PENALIZED.contains(st[0].str()); });
        kept.push_back(&s);
    }
    for (auto* s:kept) s->votes=votes[key_of(s->tests)];
    std::stable_sort(kept.begin(),kept.end(),[](const Solved* a,const Solved* b){
        return std::tuple(a->penalized,a->cost,-a->votes,a->order)<std::tuple(b->penalized,b->cost,-b->votes,b->order);
    });
    if (!kept.empty() && kept[0]->votes>=gate.min_votes) out.top=kept[0];
    return out;
}

Json run_job(const Config& c,const Task& t,bool dump) {
    auto started=Clock::now();
    Json request(Json::Object{{"task_id",t.id},{"task",Json::Object{{"train",t.train},{"test",t.test_inputs}}}});
    Json result=search(request,c.spec,c.opt);
    // Same background as the search used (search sets it per thread).
    Grids context;
    for (const auto& e:t.train.items()) { context.push_back(from_json(e["input"])); context.push_back(from_json(e["output"])); }
    set_task_background(task_background(context));
    Grids test_in;
    for (const auto& e:t.test_inputs.items()) test_in.push_back(from_json(e["input"]));
    std::vector<Solved> sols;
    size_t order=0;
    for (const auto& s:result["solutions"].items()) {
        Solved x{s["program"].items(),std::get<double>(s["cost"].value),order++,{}};
        try { for (const auto& g:test_in) x.tests.push_back(run(x.program,g,c.spec)); }
        catch (const std::exception&) { continue; }
        sols.push_back(std::move(x));
    }
    double train_cells=0;
    for (const auto& e:t.train.items()) { Grid o=from_json(e["output"]); train_cells+=double(o.h)*o.w; }
    auto chosen=choose(sols,c.gate,train_cells);
    auto correct=[&](const Solved& s){ return !t.test_outputs.empty() && s.tests==t.test_outputs; };
    bool oracle=std::any_of(sols.begin(),sols.end(),correct);
    const Json& st=result["stats"];
    Json::Object out{
        {"config",c.name},{"task_id",t.id},
        {"train_fit",!sols.empty()},{"answered",chosen.top!=nullptr},
        {"test_correct",chosen.top?correct(*chosen.top):false},
        {"oracle_correct",oracle},
        {"n_solutions",int(sols.size())},{"gated",int(chosen.gated)},
        {"program",chosen.top?Json(chosen.top->program):Json()},
        {"cost",chosen.top?chosen.top->cost:0.0},
        {"votes",chosen.top?chosen.top->votes:0.0},
        {"nodes",st["nodes"]},{"nodes_to_first",st["first_solution_nodes"]},
        {"depth",st["depth_reached"]},{"out_of_budget",st["out_of_budget"]},
        {"seconds",std::chrono::duration<double>(Clock::now()-started).count()}};
    if (dump) {
        Json::Array all;
        for (const auto& s:sols) all.emplace_back(Json::Object{{"program",s.program},{"cost",s.cost},{"votes",s.votes},{"correct",correct(s)}});
        out["solutions"]=Json(all);
    }
    return Json(out);
}
}

int batch_main(const BatchArgs& a) {
    Spec base(read_json(a.spec_path));
    if (a.ext) base.enable_ext();
    std::vector<Config> configs;
    {
        std::istringstream in(a.configs_path.empty()?std::string("{}"):slurp(a.configs_path));
        std::string line;
        while (std::getline(in,line)) if (line.find_first_not_of(" \t\r")!=std::string::npos) configs.push_back(make_config(Json::parse(line),base));
    }
    std::vector<Task> tasks;
    for (const auto& p:a.task_paths) tasks.push_back(load_task(p));
    std::string build=hex(fnv(slurp("/proc/self/exe")))+hex(fnv(slurp(a.spec_path)));
    if (!a.cache_dir.empty()) fs::create_directories(a.cache_dir);
    std::vector<Json> results(configs.size()*tasks.size());
    std::vector<char> cached(results.size(),0);
    std::atomic<size_t> next{0};
    auto wall=Clock::now();
    auto worker=[&]{
        for (size_t i;(i=next++)<results.size();) {
            const Config& c=configs[i/tasks.size()];
            const Task& t=tasks[i%tasks.size()];
            std::string file;
            if (!a.cache_dir.empty()) {
                file=a.cache_dir+"/"+hex(fnv(build+c.key+t.text+(a.dump?"d":"")))+".json";
                if (fs::exists(file)) {
                    try { results[i]=Json::parse(slurp(file)); results[i].fields(); cached[i]=1; continue; }
                    catch (const std::exception&) {}
                }
            }
            try { results[i]=run_job(c,t,a.dump); }
            catch (const std::exception& e) {
                results[i]=Json(Json::Object{{"config",c.name},{"task_id",t.id},{"error",std::string(e.what())}});
            }
            if (!file.empty()) {
                std::string tmp=file+".tmp"+std::to_string(i);
                { std::ofstream o(tmp); o<<results[i].dump()<<'\n'; }
                fs::rename(tmp,file);
            }
        }
    };
    std::vector<std::thread> pool;
    for (int k=0;k<std::max(1,a.threads);++k) pool.emplace_back(worker);
    for (auto& th:pool) th.join();
    double wall_s=std::chrono::duration<double>(Clock::now()-wall).count();
    std::ofstream file;
    if (!a.out_path.empty()) file.open(a.out_path);
    std::ostream& out=a.out_path.empty()?std::cout:file;
    for (size_t ci=0;ci<configs.size();++ci) {
        double solved=0,fit=0,answered=0,wrong=0,oracle=0,nodes=0,secs=0,hits=0;
        for (size_t ti=0;ti<tasks.size();++ti) {
            size_t i=ci*tasks.size()+ti;
            Json& r=results[i];
            out<<r.dump()<<'\n';
            const auto& o=r.fields();
            if (o.contains("error")) continue;
            bool ok=std::get<bool>(r["test_correct"].value);
            solved+=ok; fit+=std::get<bool>(r["train_fit"].value);
            bool ans=std::get<bool>(r["answered"].value);
            answered+=ans; wrong+=ans && !ok; oracle+=std::get<bool>(r["oracle_correct"].value);
            nodes+=std::get<double>(r["nodes"].value); secs+=std::get<double>(r["seconds"].value);
            hits+=cached[i];
        }
        out<<Json(Json::Object{{"summary",true},{"config",configs[ci].name},{"tasks",int(tasks.size())},
            {"solved",solved},{"train_fit",fit},{"answered",answered},{"wrong",wrong},{"oracle",oracle},
            {"nodes",nodes},{"task_seconds",secs},{"cache_hits",hits},{"wall_seconds",wall_s},{"threads",a.threads}}).dump()<<'\n';
    }
    return 0;
}
}
