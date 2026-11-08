#include "objects.hpp"
#include <algorithm>
#include <functional>
#include <iterator>

namespace arc {
namespace {
using Label=std::function<int(const Obj&,const Grid&,size_t)>;
const std::vector<std::pair<std::string,Point>> directions={
    {"up",{-1,0}},{"down",{1,0}},{"left",{0,-1}},{"right",{0,1}}};
std::vector<Step> cap(const std::vector<Step>& in) {
    std::vector<Step> out;
    for (const auto& s:in) if (s[2]!=Json("pred") && out.size()<8) out.push_back(s);
    int preds=0;
    for (const auto& s:in) if (s[2]==Json("pred") && preds<2) { out.push_back(s); ++preds; }
    return out;
}
std::vector<Step> selectors(const std::string& name,const Grids& states,const Label& label,
        const Spec& spec,const Json* extra=nullptr,const std::vector<std::string>& conns=CONNS) {
    std::vector<Step> out;
    for (const auto& conn:conns) {
        std::vector<Extracted> groups;
        Labels labels;
        for (size_t i=0;i<states.size();++i) {
            groups.push_back(extract(states[i],conn));
            std::vector<int> labs;
            for (const auto& o:*groups.back()) labs.push_back(label(o,states[i],i));
            labels.push_back(std::move(labs));
        }
        auto append=[&](const std::string& attr,const Json& value) {
            Step s={name,conn,attr,value}; if (extra) s.push_back(*extra); out.push_back(std::move(s));
        };
        for (const auto& [attr,value]:separate(groups,labels)) append(attr,value);
        for (const auto& pred:pred_selectors(groups,labels,spec)) append("pred",pred);
    }
    return cap(out);
}
std::set<std::string> shift_dirs(const Obj& o,const Grid& target) {
    std::set<std::string> out;
    for (const auto& [name,delta]:directions) {
        auto [dy,dx]=delta;
        for (int k=1;k<std::max(target.h,target.w);++k) {
            bool bounds=true,match=true;
            for (size_t j=0;j<o.cells.size();++j) {
                auto [y,x]=o.cells[j]; y+=dy*k; x+=dx*k;
                if (y<0 || y>=target.h || x<0 || x>=target.w) { bounds=false; break; }
                if (target.at(y,x)!=o.colors[j]) match=false;
            }
            if (!bounds) break;
            if (match) { out.insert(name); break; }
        }
    }
    return out;
}
std::set<std::string> grow_dirs(const Obj& o,const Grid& target,const Grid& state) {
    std::set<std::string> out;
    int bg=object_background(state);
    for (const auto& [name,delta]:directions) {
        auto [dy,dx]=delta;
        for (size_t j=0;j<o.cells.size();++j) {
            auto [y,x]=o.cells[j]; y+=dy; x+=dx;
            if (y<0 || y>=target.h || x<0 || x>=target.w || std::binary_search(o.cells.begin(),o.cells.end(),Point{y,x})) continue;
            if (state.at(y,x)==bg && target.at(y,x)==o.colors[j]) { out.insert(name); break; }
        }
    }
    return out;
}
std::set<std::string> common_dirs(const Grids& states,const Grids& targets,bool move) {
    std::optional<std::set<std::string>> common;
    for (size_t i=0;i<states.size();++i) {
        auto objs=extract(states[i],"8multi");
        for (const auto& o:*objs) {
            if (move && !changed(o,targets[i])) continue;
            auto dirs=move?shift_dirs(o,targets[i]):grow_dirs(o,targets[i],states[i]);
            if (!move && dirs.empty()) continue;
            if (!common) common=dirs;
            else {
                std::set<std::string> both;
                std::set_intersection(common->begin(),common->end(),dirs.begin(),dirs.end(),std::inserter(both,both.end()));
                common=std::move(both);
            }
        }
    }
    return common.value_or(std::set<std::string>{});
}
}
std::vector<Step> narrow_objects(const std::string& name,const Grids& states,const Grids& targets,const Spec& spec) {
    if (states.size()!=targets.size()) fail();
    for (size_t i=0;i<states.size();++i) if (!same_shape(states[i],targets[i])) return {};
    std::vector<Step> out;
    if (name=="recolor_sel") {
        for (const auto& conn:CONNS) {
            std::set<int> cs;
            for (size_t i=0;i<states.size();++i) {
                auto objs=extract(states[i],conn);
                for (const auto& o:*objs) if (changed(o,targets[i])) if (auto c=uniform(o,targets[i])) cs.insert(*c);
            }
            if (cs.size()!=1) continue;
            int c=*cs.begin(); Json extra=c;
            auto found=selectors(name,states,[&](const Obj& o,const Grid&,size_t i){
                if (!changed(o,targets[i])) return std::all_of(o.colors.begin(),o.colors.end(),[&](int v){return v==c;})?-1:0;
                return uniform(o,targets[i])==c?1:-1;
            },spec,&extra,{conn});
            out.insert(out.end(),found.begin(),found.end());
        }
        return cap(out);
    }
    if (name=="delete_sel" || name=="keep_sel") {
        bool keep=name=="keep_sel";
        out=selectors(name,states,[&](const Obj& o,const Grid& s,size_t i){
            if (!changed(o,targets[i])) return keep?1:0;
            return uniform(o,targets[i])==object_background(s)?(keep?0:1):-1;
        },spec);
        if (keep) std::erase_if(out,[](const Step& s){return s[2]==Json("all");});
        return out;
    }
    if (name=="fill_holes") {
        std::set<int> cs;
        for (size_t i=0;i<states.size();++i) {
            int bg=object_background(states[i]);
            for (size_t j=0;j<states[i].data.size();++j) if (states[i].data[j]!=targets[i].data[j]) {
                if (states[i].data[j]!=bg) return {};
                cs.insert(targets[i].data[j]);
            }
        }
        if (cs.size()==1) return {{name,*cs.begin()}};
        return {};
    }
    bool move=name=="move_sel";
    for (const auto& dir:common_dirs(states,targets,move)) {
        Json extra=dir;
        auto found=selectors(name,states,[&](const Obj& o,const Grid& s,size_t i){
            if (move) {
                if (!changed(o,targets[i])) return 0;
                return shift_dirs(o,targets[i]).contains(dir)?1:-1;
            }
            return grow_dirs(o,targets[i],s).contains(dir)?1:0;
        },spec,&extra);
        out.insert(out.end(),found.begin(),found.end());
    }
    return cap(out);
}
std::vector<Step> object_candidates(const std::string& name,const Grids& states,const Grids& targets,const Spec& spec) {
    auto out=narrow_objects(name,states,targets,spec);
    auto append=[&](Step step) {
        if (std::find(out.begin(),out.end(),step)==out.end()) out.push_back(std::move(step));
    };
    if (name=="fill_holes") {
        for (int c:colors(targets)) append({name,c});
        return out;
    }
    for (const auto& conn:CONNS) {
        std::vector<Extracted> groups;
        for (const auto& s:states) groups.push_back(extract(s,conn));
        for (const auto& [attr,value]:wide_selectors(groups)) {
            if (name=="recolor_sel") for (int c:colors(targets)) append({name,conn,attr,value,c});
            else if (name=="move_sel" || name=="extend_sel")
                for (const auto& [dir,delta]:directions) { (void)delta; append({name,conn,attr,value,dir}); }
            else append({name,conn,attr,value});
        }
    }
    return out;
}
}
