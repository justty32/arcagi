#include "objects.hpp"
#include <algorithm>
#include <iterator>

namespace arc {
namespace {
constexpr int KEEP=-1,SUPPORT=2;
struct Less {
    bool operator()(const Json& a,const Json& b) const {
        return std::holds_alternative<std::string>(a.value)?a.str()<b.str():a.integer()<b.integer();
    }
};
using Allowed=std::set<int>;
using Labeled=std::vector<std::pair<const Obj*,int>>;
Allowed allowed(const Obj& o,int label) {
    Allowed out={label};
    if (std::all_of(o.colors.begin(),o.colors.end(),[&](int c){return c==label;})) out.insert(KEEP);
    return out;
}
Allowed intersection(const Allowed& a,const Allowed& b) {
    Allowed out;
    std::set_intersection(a.begin(),a.end(),b.begin(),b.end(),std::inserter(out,out.end()));
    return out;
}
std::optional<Json> fit_attr(const Labeled& labeled,const std::vector<Extracted>& tests,int attr) {
    std::map<Json,Allowed,Less> options;
    std::map<Json,int,Less> support,lookup;
    for (const auto& [o,label]:labeled) {
        const auto& key=o->props[attr];
        auto can=allowed(*o,label);
        auto [it,inserted]=options.emplace(key,can);
        if (!inserted) it->second=intersection(it->second,can);
        if (it->second.empty()) return std::nullopt;
        ++support[key];
    }
    bool change=false;
    for (const auto& [key,can]:options) {
        int color=can.contains(KEEP)?KEEP:*can.begin();
        lookup[key]=color;
        if (color!=KEEP) {
            if (support[key]<SUPPORT) return std::nullopt;
            change=true;
        }
    }
    if (!change) return std::nullopt;
    for (const auto& group:tests) for (const auto& o:*group) {
        const auto& key=o.props[attr];
        if (!lookup.contains(key) || support[key]<SUPPORT) return std::nullopt;
    }
    Json::Array rows;
    for (const auto& [key,color]:lookup) if (color!=KEEP) rows.emplace_back(Json::Array{key,color});
    return rows;
}
std::optional<int> pick(const std::vector<Allowed>& sets,bool prefer_keep) {
    if (sets.empty()) return std::nullopt;
    auto common=sets[0];
    for (size_t i=1;i<sets.size();++i) common=intersection(common,sets[i]);
    if (common.empty()) return std::nullopt;
    if (prefer_keep && common.contains(KEEP)) return KEEP;
    common.erase(KEEP);
    return common.empty()?KEEP:*common.begin();
}
std::optional<std::pair<Json,int>> fit_split(const Labeled& labeled,int attr) {
    std::map<Json,std::vector<Allowed>,Less> grouped;
    for (const auto& [o,label]:labeled) grouped[o->props[attr]].push_back(allowed(*o,label));
    if (grouped.size()<2) return std::nullopt;
    std::vector<const Json*> keys;
    for (const auto& [key,sets]:grouped) { (void)sets; keys.push_back(&key); }
    auto str=[](const Json& j){return std::holds_alternative<std::string>(j.value)?j.str():std::to_string(j.integer());};
    std::sort(keys.begin(),keys.end(),[&](const Json* a,const Json* b){return str(*a)<str(*b);});
    for (const auto* key:keys) {
        const auto& value=*key;
        const auto& inside=grouped.at(value);
        std::vector<Allowed> outside;
        for (const auto& [key,sets]:grouped) if (key!=value) outside.insert(outside.end(),sets.begin(),sets.end());
        if (inside.size()<SUPPORT || outside.size()<SUPPORT) continue;
        auto color=pick(inside,false),other=pick(outside,true);
        if (!color || !other || *color==KEEP || *color==*other) continue;
        return std::pair<Json,int>{Json::Array{Json::Array{value,*color}},*other};
    }
    return std::nullopt;
}
}
Grid apply_object_colormap(const Grid& g,const Json& table) {
    const auto& conn=table[0].str();
    int attr=attr_index(table[1].str());
    int other=table.size()>3?table[3].integer():KEEP;
    std::map<Json,int,Less> lookup;
    for (const auto& row:table[2].items()) lookup[row[0]]=row[1].integer();
    Grid out=g;
    auto objs=extract(g,conn);
    for (const auto& o:*objs) {
        auto it=lookup.find(o.props[attr]);
        int color=it==lookup.end()?other:it->second;
        if (color!=KEEP) for (auto [y,x]:o.cells) out.at(y,x)=color;
    }
    return out;
}
std::optional<Json> fit_object_colormap(const Grids& states,const Grids& targets,const Grids& tests) {
    if (states.size()!=targets.size()) fail();
    bool change=false;
    for (size_t i=0;i<states.size();++i) {
        if (!same_shape(states[i],targets[i])) return std::nullopt;
        int bg=object_background(states[i]);
        for (size_t j=0;j<states[i].data.size();++j) if (states[i].data[j]!=targets[i].data[j]) {
            if (states[i].data[j]==bg) return std::nullopt;
            change=true;
        }
    }
    if (!change) return std::nullopt;
    std::optional<Json> best;
    auto rank=[](const Json& t){return std::pair(t.size(),t[2].size());};
    for (const auto& conn:CONNS) {
        std::vector<Extracted> groups,test_objs;
        Labeled labeled;
        bool ok=true;
        for (size_t i=0;i<states.size() && ok;++i) {
            groups.push_back(extract(states[i],conn));
            for (const auto& o:*groups.back()) {
                auto c=uniform(o,targets[i]);
                if (c) labeled.emplace_back(&o,*c);
                else if (!changed(o,targets[i])) labeled.emplace_back(&o,KEEP);
                else { ok=false; break; }
            }
        }
        if (!ok) continue;
        for (const auto& test:tests) test_objs.push_back(extract(test,conn));
        std::vector<Json> found;
        for (size_t a=0;a<ATTRS.size();++a)
            if (auto rows=fit_attr(labeled,test_objs,int(a))) found.emplace_back(Json::Array{conn,ATTRS[a],*rows});
        for (size_t a=0;a<ATTRS.size();++a)
            if (auto split=fit_split(labeled,int(a))) found.emplace_back(Json::Array{conn,ATTRS[a],split->first,split->second});
        for (const auto& table:found) {
            if (best && rank(table)>=rank(*best)) continue;
            bool match=true;
            for (size_t i=0;i<states.size();++i) if (apply_object_colormap(states[i],table)!=targets[i]) { match=false; break; }
            if (match) best=table;
        }
    }
    return best;
}
}
