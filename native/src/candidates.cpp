#include "prims.hpp"
#include "objects.hpp"
#include <algorithm>
#include <iterator>

namespace arc {
static bool shapes(const Grids& states,const Grids& targets) {
    for (size_t i=0;i<states.size();++i) if (!same_shape(states[i],targets[i])) return false;
    return true;
}
static std::set<int> intersect(const std::set<int>& a,const std::set<int>& b) {
    std::set<int> out;
    std::set_intersection(a.begin(),a.end(),b.begin(),b.end(),std::inserter(out,out.end()));
    return out;
}
static void modes(std::vector<Step>& out,const std::string& name,const std::vector<std::string>& values) {
    for (const auto& v:values) out.push_back({name,v});
}
std::vector<Step> narrow(const std::string& name,const Grids& states,const Grids& targets) {
    std::vector<Step> out;
    if (name=="upscale" || name=="tile" || name=="downscale") {
        int fy=0,fx=0;
        for (size_t i=0;i<states.size();++i) {
            const Grid& big=name=="downscale"?states[i]:targets[i];
            const Grid& small=name=="downscale"?targets[i]:states[i];
            if (!small.h || !small.w || big.h%small.h || big.w%small.w) return {};
            int y=big.h/small.h,x=big.w/small.w;
            if ((y==1 && x==1) || (fy && (y!=fy || x!=fx))) return {};
            fy=y; fx=x;
        }
        if (fy && std::max(fy,fx)<=10) out.push_back({name,fy,fx});
    } else if (name=="mirror_tile") modes(out,name,{"lr","ud","quad"});
    else if (name=="split_overlay") {
        for (const auto& axis:{"h","v"}) {
            bool ok=true;
            try {
                for (size_t i=0;i<states.size();++i) if (!same_shape(halves(states[i],axis).first,targets[i])) { ok=false; break; }
            } catch (const std::exception&) { ok=false; }
            if (ok) for (const auto& op:SPLIT_OPS) out.push_back({name,axis,op});
        }
    } else if (name=="crop_object") {
        for (size_t i=0;i<states.size();++i) if (same_shape(states[i],targets[i])) return {};
        for (const auto& conn:{"4same","8multi"}) for (const auto& how:HOWS) out.push_back({name,conn,how});
    } else if (name=="fill_enclosed") {
        if (shapes(states,targets)) out.push_back({name});
    } else if (name=="self_tile") {
        for (size_t i=0;i<states.size();++i)
            if (targets[i].h!=states[i].h*states[i].h || targets[i].w!=states[i].w*states[i].w) return {};
        modes(out,name,{"pos","neg"});
    } else if (name=="gravity") {
        if (shapes(states,targets)) modes(out,name,DIRS);
    } else if (name=="symmetrize") {
        if (!shapes(states,targets)) return {};
        std::set<int> holes;
        bool first=true;
        for (size_t i=0;i<states.size();++i) {
            auto gone=colors(Grids{states[i]});
            for (int c:targets[i].data) gone.erase(c);
            holes=first?gone:intersect(holes,gone); first=false;
        }
        if (holes.empty()) for (const auto& s:states) holes.insert(background(s));
        if (holes.size()!=1) return {};
        for (const auto& mode:MIRRORS) out.push_back({name,mode,*holes.begin()});
    } else if (name=="pick_cell" || name=="overlay_cells" || name=="cells_to_pixels" || name=="fill_cells") {
        std::vector<Layout> layouts;
        for (size_t i=0;i<states.size();++i) {
            auto lay=split(states[i]); if (!lay) return {};
            const auto& t=targets[i];
            if (name=="fill_cells") { if (!same_shape(states[i],t)) return {}; }
            else if (name=="cells_to_pixels") {
                if (int(lay->rows.size())!=t.h || int(lay->cols.size())!=t.w) return {};
            } else if (lay->rows[0].second!=t.h || lay->cols[0].second!=t.w) return {};
            layouts.push_back(*lay);
        }
        if (name=="pick_cell") {
            modes(out,name,PICKS);
            std::set<int> shared;
            bool first=true;
            for (size_t i=0;i<states.size();++i) {
                auto parts=cut(states[i],layouts[i]);
                int bg=background(parts);
                std::map<int,int> seen;
                for (const auto& p:parts) {
                    auto cs=colors(Grids{p}); cs.erase(bg);
                    for (int c:cs) ++seen[c];
                }
                std::set<int> lone;
                for (auto [c,n]:seen) if (n==1 && c!=layouts[i].color) lone.insert(c);
                shared=first?lone:intersect(shared,lone); first=false;
            }
            for (int c:shared) out.push_back({name,"has_color",c});
        } else modes(out,name,name=="overlay_cells"?OVERLAYS:SUMMARIES);
    } else out.push_back({name});
    return out;
}
std::vector<Step> candidates(const std::string& name,const Grids& states,const Grids& targets,bool last,const Spec& spec) {
    if (is_object_primitive(name)) return object_candidates(name,states,targets,spec);
    if (is_ext_primitive(name)) return ext_candidates(name,states,targets);
    if (name=="colormap") {
        std::vector<Step> out;
        auto destinations=colors(targets); destinations.insert(0);
        if (!last) for (int a:colors(states)) for (int b:destinations)
            if (a!=b) out.push_back({name,Json::Array{Json::Array{a,b}}});
        return out;
    }
    std::vector<Step> out=narrow(name,states,targets),wide;
    if (name=="upscale" || name=="tile" || name=="downscale") {
        for (int fy=1;fy<=4;++fy) for (int fx=1;fx<=4;++fx) {
            if (fy==1 && fx==1) continue;
            bool ok=true;
            for (const auto& g:states) {
                if (name=="downscale") { if (g.h%fy || g.w%fx) ok=false; }
                else if (g.h*fy>30 || g.w*fx>30) ok=false;
            }
            if (ok) wide.push_back({name,fy,fx});
        }
    } else if (name=="split_overlay") {
        for (const auto& axis:{"h","v"}) {
            bool ok=true;
            try { for (const auto& g:states) (void)halves(g,axis); }
            catch (const std::exception&) { ok=false; }
            if (ok) for (const auto& op:SPLIT_OPS) wide.push_back({name,axis,op});
        }
    } else if (name=="crop_object") {
        for (const auto& conn:{"4same","8multi"}) for (const auto& how:HOWS) wide.push_back({name,conn,how});
    } else if (name=="mirror_tile") modes(wide,name,{"lr","ud","quad"});
    else if (name=="self_tile") modes(wide,name,{"pos","neg"});
    else if (name=="gravity") modes(wide,name,DIRS);
    else if (name=="symmetrize") {
        auto cs=colors(states);
        for (const auto& mode:MIRRORS) for (int c:cs) wide.push_back({name,mode,c});
    } else if (name=="pick_cell" || name=="overlay_cells" || name=="cells_to_pixels" || name=="fill_cells") {
        bool ok=true;
        for (const auto& g:states) if (!split(g)) { ok=false; break; }
        if (ok) {
            modes(wide,name,name=="pick_cell"?PICKS:name=="overlay_cells"?OVERLAYS:SUMMARIES);
            if (name=="pick_cell") for (int c:colors(states)) wide.push_back({name,"has_color",c});
        }
    } else wide.push_back({name});
    for (auto& step:wide) if (std::find(out.begin(),out.end(),step)==out.end()) out.push_back(std::move(step));
    return out;
}
}
