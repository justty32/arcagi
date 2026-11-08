#include "objects.hpp"
#include <algorithm>

namespace arc {
namespace {
Point direction(const std::string& name) {
    if (name=="up") return {-1,0};
    if (name=="down") return {1,0};
    if (name=="left") return {0,-1};
    if (name=="right") return {0,1};
    fail();
}
}
bool is_object_primitive(const std::string& name) {
    return name=="recolor_sel" || name=="delete_sel" || name=="keep_sel" ||
        name=="fill_holes" || name=="move_sel" || name=="extend_sel";
}
Grid apply_objects(const Step& s,const Grid& g,const Spec& spec) {
    Grid out=g;
    const auto& name=s.at(0).str();
    int bg=object_background(g);
    if (name=="fill_holes") {
        auto objs=extract(g,"8multi");
        for (const auto& o:*objs) for (auto [y,x]:hole_cells(o.cells))
            if (g.at(y,x)==bg) out.at(y,x)=s.at(1).integer();
        return out;
    }
    auto objs=extract(g,s.at(1).str());
    auto chosen=selected(*objs,s.at(2).str(),s.at(3),spec);
    if (name=="recolor_sel" || name=="delete_sel" || name=="keep_sel") {
        if (name=="keep_sel") {
            std::vector<size_t> drop;
            for (size_t i=0;i<objs->size();++i) if (std::find(chosen.begin(),chosen.end(),i)==chosen.end()) drop.push_back(i);
            chosen=std::move(drop);
        }
        int color=name=="recolor_sel"?s.at(4).integer():bg;
        for (size_t i:chosen) for (auto [y,x]:objs->at(i).cells) out.at(y,x)=color;
        return out;
    }
    auto [dy,dx]=direction(s.at(4).str());
    if (name=="move_sel") {
        for (size_t i:chosen) for (auto [y,x]:objs->at(i).cells) out.at(y,x)=bg;
        auto score=[&](size_t i) {
            int best=-1000;
            for (auto [y,x]:objs->at(i).cells) best=std::max(best,y*dy+x*dx);
            return best;
        };
        std::stable_sort(chosen.begin(),chosen.end(),[&](size_t a,size_t b){return score(a)>score(b);});
        for (size_t i:chosen) {
            const auto& o=objs->at(i);
            int shift=0;
            while (true) {
                int k=shift+1;
                bool ok=true;
                for (auto [y,x]:o.cells) {
                    int ny=y+dy*k,nx=x+dx*k;
                    if (ny<0 || ny>=g.h || nx<0 || nx>=g.w || out.at(ny,nx)!=bg) { ok=false; break; }
                }
                if (!ok) break;
                shift=k;
            }
            for (size_t j=0;j<o.cells.size();++j) {
                auto [y,x]=o.cells[j]; out.at(y+dy*shift,x+dx*shift)=o.colors[j];
            }
        }
        return out;
    }
    if (name=="extend_sel") {
        for (size_t i:chosen) {
            const auto& o=objs->at(i);
            for (size_t j=0;j<o.cells.size();++j) {
                auto [y,x]=o.cells[j];
                if (std::binary_search(o.cells.begin(),o.cells.end(),Point{y+dy,x+dx})) continue;
                y+=dy; x+=dx;
                while (y>=0 && y<g.h && x>=0 && x<g.w && g.at(y,x)==bg) {
                    out.at(y,x)=o.colors[j]; y+=dy; x+=dx;
                }
            }
        }
        return out;
    }
    fail();
}
}
