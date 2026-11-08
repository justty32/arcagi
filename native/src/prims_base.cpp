#include "prims.hpp"
#include "learners.hpp"
#include "objects.hpp"
#include <algorithm>

namespace arc {
const std::unordered_set<std::string>& ported() {
    static const std::unordered_set<std::string> names={
        "flip_lr","flip_ud","transpose","rot90","rot180","rot270","anti_transpose",
        "upscale","downscale","tile","mirror_tile","crop_bbox","split_overlay","crop_object",
        "fill_enclosed","self_tile","symmetrize","gravity","pick_cell","overlay_cells","cells_to_pixels","fill_cells",
        "recolor_sel","delete_sel","keep_sel","fill_holes","move_sel","extend_sel"};
    return names;
}
Spec::Spec(const Json& j) {
    if (j.fields().contains("predicates")) predicates=j["predicates"].fields();
    if (j.fields().contains("predicate_names")) {
        for (const auto& name:j["predicate_names"].items()) predicate_names.push_back(name.str());
    } else for (const auto& [name,body]:predicates) { (void)body; predicate_names.push_back(name); }
    for (const auto& name:j["live"].items()) live.insert(name.str());
    for (const auto& [name,program]:j["macros"].fields()) {
        bool ok=live.contains(name);
        for (const auto& step:program.items()) ok=ok && ported().contains(step[0].str());
        if (ok) macros[name]=program.items();
    }
    for (const auto& name:j["live"].items())
        if (ported().contains(name.str()) || macros.contains(name.str())) names.push_back(name.str());
}
std::pair<Grid,Grid> halves(const Grid& g,const std::string& axis) {
    Grid work=axis=="h"?g:transform(g,"transpose");
    int mid=work.h/2;
    if (work.h%2) {
        if (!work.w) fail();
        for (int x=1;x<work.w;++x) if (work.at(mid,x)!=work.at(mid,0)) fail();
    }
    Grid a=crop(work,{0,0,mid,work.w}),b=crop(work,{mid+work.h%2,0,mid,work.w});
    if (axis=="v") { a=transform(a,"transpose"); b=transform(b,"transpose"); }
    return {a,b};
}
static Component select(const std::vector<Component>& objs,const Grid& g,const std::string& how) {
    if (objs.empty()) fail();
    size_t best=0;
    if (how=="top_left") return objs[0];
    std::vector<std::set<int>> colors;
    for (const auto& obj:objs) {
        std::set<int> cs;
        for (auto [y,x]:obj) cs.insert(g.at(y,x));
        colors.push_back(cs);
    }
    if (how=="unique_color") {
        std::map<int,int> ns;
        for (const auto& cs:colors) if (cs.size()==1) ++ns[*cs.begin()];
        int hits=0;
        for (size_t i=0;i<objs.size();++i) if (colors[i].size()==1 && ns[*colors[i].begin()]==1) { best=i; ++hits; }
        if (hits!=1) fail();
        return objs[best];
    }
    if (how!="largest" && how!="smallest" && how!="most_colors") fail();
    for (size_t i=1;i<objs.size();++i) {
        if ((how=="largest" && objs[i].size()>objs[best].size()) ||
            (how=="smallest" && objs[i].size()<objs[best].size()) ||
            (how=="most_colors" && colors[i].size()>colors[best].size())) best=i;
    }
    return objs[best];
}
Grid apply_base(const Step& s,const Grid& g) {
    const std::string& name=s.at(0).str();
    if (std::find(D4.begin(),D4.end(),name)!=D4.end()) return transform(g,name);
    if (name=="upscale" || name=="downscale" || name=="tile") return scale(g,s.at(1).integer(),s.at(2).integer(),name);
    if (name=="mirror_tile") {
        std::string mode=s.at(1).str();
        bool horizontal=mode!="ud",vertical=mode!="lr";
        Grid out(g.h*(vertical?2:1),g.w*(horizontal?2:1));
        for (int y=0;y<out.h;++y) for (int x=0;x<out.w;++x)
            out.at(y,x)=g.at(y<g.h?y:2*g.h-1-y,x<g.w?x:2*g.w-1-x);
        return out;
    }
    if (name=="crop_bbox") {
        auto b=bbox(g,background(g)); if (!b) fail(); return crop(g,*b);
    }
    if (name=="crop_object") {
        std::string conn=s.at(1).str();
        auto objs=objects(g,background(g),conn=="8multi",conn=="4same");
        return crop(g,cells_bbox(select(objs,g,s.at(2).str())));
    }
    if (name=="split_overlay") {
        auto [a,b]=halves(g,s.at(1).str());
        std::string op=s.at(2).str();
        if (std::find(SPLIT_OPS.begin(),SPLIT_OPS.end(),op)==SPLIT_OPS.end()) fail();
        int bg=std::find(g.data.begin(),g.data.end(),0)!=g.data.end()?0:background(g);
        Grid out(a.h,a.w);
        if (!same_shape(a,b)) fail();
        for (size_t i=0;i<a.data.size();++i) {
            bool x=a.data[i]!=bg,y=b.data[i]!=bg;
            bool hit=op=="and"?x&&y:op=="or"?x||y:op=="xor"?x!=y:op=="nor"?!(x||y):x&&!y;
            out.data[i]=hit?10:0;
        }
        return out;
    }
    if (name=="fill_enclosed") {
        int bg=background(g);
        Grid out=g;
        std::vector<bool> outside(g.data.size());
        Component stack;
        for (int y=0;y<g.h;++y) for (int x=0;x<g.w;++x)
            if ((y==0 || y==g.h-1 || x==0 || x==g.w-1) && g.at(y,x)==bg) {
                outside[y*g.w+x]=true; stack.emplace_back(y,x);
            }
        const Component dirs={{-1,0},{1,0},{0,-1},{0,1}};
        while (!stack.empty()) {
            auto [y,x]=stack.back(); stack.pop_back();
            for (auto [dy,dx]:dirs) {
                int ny=y+dy,nx=x+dx;
                if (ny<0 || ny>=g.h || nx<0 || nx>=g.w || outside[ny*g.w+nx] || g.at(ny,nx)!=bg) continue;
                outside[ny*g.w+nx]=true; stack.emplace_back(ny,nx);
            }
        }
        for (size_t i=0;i<g.data.size();++i) if (g.data[i]==bg && !outside[i]) out.data[i]=10;
        return out;
    }
    fail();
}
Grid apply_step(const Step& s,const Grid& g,const Spec& spec,bool in_macro) {
    const std::string& name=s.at(0).str();
    if (!in_macro && name=="colormap") return apply_colormap(g,s.at(1));
    if (!in_macro && name=="local_rule") return apply_local_rule(g,s.at(1).str(),s.at(2));
    if (!in_macro && name=="object_colormap") return apply_object_colormap(g,s.at(1));
    if (!in_macro && !spec.live.contains(name)) fail();
    if (auto it=spec.macros.find(name);it!=spec.macros.end() && !in_macro) {
        Grid out=g;
        for (const auto& step:it->second) out=apply_step(step.items(),out,spec,true);
        return out;
    }
    if (!ported().contains(name)) fail();
    if (is_object_primitive(name)) return apply_objects(s,g,spec);
    if (name=="self_tile" || name=="symmetrize" || name=="gravity") return apply_more(s,g);
    if (name=="pick_cell" || name=="overlay_cells" || name=="cells_to_pixels" || name=="fill_cells") return apply_cells(s,g);
    return apply_base(s,g);
}
Grid run(const Program& program,Grid g,const Spec& spec) {
    for (const auto& step:program) { g=apply_step(step.items(),g,spec); if (!g.bounds()) fail(); }
    if (!g.valid()) fail();
    return g;
}
double cost(const Program& program) {
    double out=0;
    for (const auto& step:program) {
        for (size_t i=1;i<step.size();++i) {
            const Json& param=step[0].str()=="object_colormap"?step[i][2]:step[i];
            out+=param.array()?0.05*param.size():0.1;
        }
        out+=1;
    }
    return out;
}
}
