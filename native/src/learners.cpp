#include "learners.hpp"
#include <algorithm>

namespace arc {
static const Component& neighbors(const std::string& features) {
    static const Component n4={{-1,0},{1,0},{0,-1},{0,1}};
    static const Component n8={{-1,-1},{-1,0},{-1,1},{0,-1},{0,1},{1,-1},{1,0},{1,1}};
    if (features=="n4") return n4;
    if (features=="n8") return n8;
    fail();
}
using Key=std::vector<int>;
static Key key(const Grid& g,int y,int x,const Component& steps) {
    Key out; out.reserve(steps.size()+1); out.push_back(g.at(y,x));
    for (auto [dy,dx]:steps) {
        int ny=y+dy,nx=x+dx;
        out.push_back(ny>=0 && ny<g.h && nx>=0 && nx<g.w?g.at(ny,nx):OUTSIDE);
    }
    return out;
}
Grid apply_colormap(const Grid& g,const Json& table) {
    std::map<int,int> mapping;
    for (const auto& row:table.items()) {
        if (row.size()!=2) fail();
        mapping[row[0].integer()]=row[1].integer();
    }
    Grid out=g;
    for (int& c:out.data) if (auto it=mapping.find(c);it!=mapping.end()) c=it->second;
    return out;
}
Grid apply_local_rule(const Grid& g,const std::string& features,const Json& table) {
    std::map<Key,int> lookup;
    for (const auto& row:table.items()) {
        if (!row.size()) fail();
        Key k;
        for (size_t i=0;i+1<row.size();++i) k.push_back(row[i].integer());
        lookup[k]=row[row.size()-1].integer();
    }
    const auto& steps=neighbors(features);
    Grid out=g;
    for (int y=0;y<g.h;++y) for (int x=0;x<g.w;++x) {
        auto k=key(g,y,x,steps);
        auto it=lookup.find(k);
        if (it!=lookup.end()) out.at(y,x)=it->second;
        else if (k[0]>9) fail();
    }
    return out;
}
std::optional<Json> fit_colormap(const Grids& states,const Grids& targets,const Grids& tests) {
    std::map<int,int> mapping;
    if (states.size()!=targets.size()) fail();
    for (size_t i=0;i<states.size();++i) {
        const Grid& s=states[i]; const Grid& t=targets[i];
        if (!same_shape(s,t)) return std::nullopt;
        for (size_t j=0;j<s.data.size();++j) {
            auto [it,inserted]=mapping.emplace(s.data[j],t.data[j]);
            if (!inserted && it->second!=t.data[j]) return std::nullopt;
        }
    }
    for (const auto& t:tests) for (int c:t.data) if (c>9 && !mapping.contains(c)) return std::nullopt;
    Json::Array table;
    for (auto [a,b]:mapping) if (a!=b) table.emplace_back(Json::Array{a,b});
    if (table.empty()) return std::nullopt;
    return Json(table);
}
std::optional<Json> fit_local_rule(const Grids& states,const Grids& targets,const Grids& tests,const std::string& features) {
    const auto& steps=neighbors(features);
    std::map<Key,int> lookup,support;
    if (states.size()!=targets.size()) fail();
    for (size_t i=0;i<states.size();++i) {
        const Grid& s=states[i]; const Grid& t=targets[i];
        if (!same_shape(s,t)) return std::nullopt;
        for (int y=0;y<s.h;++y) for (int x=0;x<s.w;++x) {
            auto k=key(s,y,x,steps);
            ++support[k];
            auto [it,inserted]=lookup.emplace(k,t.at(y,x));
            if (!inserted && it->second!=t.at(y,x)) return std::nullopt;
        }
    }
    bool changing=false;
    for (const auto& [k,v]:lookup) if (k[0]!=v) {
        changing=true;
        if (support[k]<MIN_SUPPORT) return std::nullopt;
    }
    if (!changing) return std::nullopt;
    for (const auto& t:tests) for (int y=0;y<t.h;++y) for (int x=0;x<t.w;++x)
        if (!lookup.contains(key(t,y,x,steps))) return std::nullopt;
    Json::Array table;
    for (const auto& [k,v]:lookup) if (k[0]!=v) {
        Json::Array row;
        for (int n:k) row.emplace_back(n);
        row.emplace_back(v); table.emplace_back(row);
    }
    return Json(table);
}
}
