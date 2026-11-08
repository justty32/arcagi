#include "prims.hpp"
#include <algorithm>
#include <numeric>

namespace arc {
static std::vector<Point> runs(int n,const std::set<int>& lines) {
    std::vector<Point> out;
    int start=-1;
    for (int i=0;i<=n;++i) {
        if (i<n && !lines.contains(i)) { if (start<0) start=i; }
        else if (start>=0) { out.emplace_back(start,i-start); start=-1; }
    }
    return out;
}
Grids cut(const Grid& g,const Layout& layout) {
    Grids parts;
    for (auto [y,h]:layout.rows) for (auto [x,w]:layout.cols) parts.push_back(crop(g,{y,x,h,w}));
    return parts;
}
std::optional<Layout> split(const Grid& g) {
    if (!g.h || !g.w) return std::nullopt;
    std::map<int,int> full_rows,full_cols;
    std::set<int> cs;
    for (int y=0;y<g.h;++y) {
        bool same=true;
        for (int x=1;x<g.w;++x) if (g.at(y,x)!=g.at(y,0)) same=false;
        if (same) { full_rows[y]=g.at(y,0); cs.insert(g.at(y,0)); }
    }
    for (int x=0;x<g.w;++x) {
        bool same=true;
        for (int y=1;y<g.h;++y) if (g.at(y,x)!=g.at(0,x)) same=false;
        if (same) { full_cols[x]=g.at(0,x); cs.insert(g.at(0,x)); }
    }
    int bg=background(g);
    std::vector<int> order(cs.begin(),cs.end());
    std::stable_sort(order.begin(),order.end(),[bg](int a,int b){return (a==bg)<(b==bg);});
    for (int c:order) {
        std::set<int> rows,cols;
        for (auto [i,v]:full_rows) if (v==c) rows.insert(i);
        for (auto [i,v]:full_cols) if (v==c) cols.insert(i);
        if (int(rows.size())==g.h || int(cols.size())==g.w) continue;
        Layout layout{c,runs(g.h,rows),runs(g.w,cols)};
        if (layout.rows.size()*layout.cols.size()<2) continue;
        bool equal=true;
        for (auto [start,n]:layout.rows) { (void)start; if (n!=layout.rows[0].second) equal=false; }
        for (auto [start,n]:layout.cols) { (void)start; if (n!=layout.cols[0].second) equal=false; }
        if (equal && background(cut(g,layout))!=c) return layout;
    }
    return std::nullopt;
}
static int pixels(const Grid& g,int bg) {
    return int(std::count_if(g.data.begin(),g.data.end(),[bg](int c){return c!=bg;}));
}
static std::set<int> nonbg(const Grid& g,int bg) {
    std::set<int> cs(g.data.begin(),g.data.end()); cs.erase(bg); return cs;
}
static Grid mask(Grid g,int bg) { for (int& c:g.data) c=c!=bg; return g; }
static size_t unique(const Grids& keys) {
    size_t best=0;
    int lone=0;
    for (size_t i=0;i<keys.size();++i) if (std::count(keys.begin(),keys.end(),keys[i])==1) { best=i; ++lone; }
    if (lone!=1) fail();
    return best;
}
static std::vector<int> summaries(const Grids& parts,int bg,const std::string& mode) {
    std::vector<int> out;
    if (mode=="max_pixels") {
        for (const auto& p:parts) out.push_back(pixels(p,bg));
        int best=*std::max_element(out.begin(),out.end());
        for (int& n:out) n=n==best?10:0;
        return out;
    }
    for (const auto& p:parts) {
        auto ns=counts(p); ns.erase(bg);
        int best=bg;
        if (mode=="any") best=ns.empty()?0:10;
        else if (mode=="uniform") {
            if (ns.size()==1 && ns.begin()->second==int(p.data.size())) best=ns.begin()->first;
        } else if (!ns.empty()) {
            best=ns.begin()->first;
            for (auto [c,n]:ns) if (n>ns[best]) best=c;
        }
        out.push_back(best);
    }
    return out;
}
Grid apply_cells(const Step& s,const Grid& g) {
    auto layout=split(g);
    if (!layout) fail();
    Grids parts=cut(g,*layout);
    int bg=background(parts);
    const std::string& name=s.at(0).str();
    const std::string& mode=s.at(1).str();
    if (name=="pick_cell") {
        size_t best=0;
        if (mode=="unique") best=unique(parts);
        else if (mode=="unique_mask") {
            Grids keys;
            for (const auto& p:parts) keys.push_back(mask(p,bg));
            best=unique(keys);
        } else if (mode=="has_color") {
            int color=s.size()>2?s.at(2).integer():-1,hits=0;
            for (size_t i=0;i<parts.size();++i) if (nonbg(parts[i],bg).contains(color)) { best=i; ++hits; }
            if (hits!=1) fail();
        } else {
            bool colors=mode=="most_colors" || mode=="least_colors";
            bool most=mode=="most_colors" || mode=="most_pixels";
            if (!colors && mode!="most_pixels" && mode!="least_pixels") fail();
            std::vector<int> scores;
            for (const auto& p:parts) scores.push_back(colors?int(nonbg(p,bg).size()):pixels(p,bg));
            int value=most?*std::max_element(scores.begin(),scores.end()):*std::min_element(scores.begin(),scores.end());
            if (std::count(scores.begin(),scores.end(),value)!=1) fail();
            best=std::find(scores.begin(),scores.end(),value)-scores.begin();
        }
        return parts[best];
    }
    if (name=="overlay_cells") {
        if (std::find(OVERLAYS.begin(),OVERLAYS.end(),mode)==OVERLAYS.end()) fail();
        Grid out(parts[0].h,parts[0].w,bg);
        for (size_t i=0;i<out.data.size();++i) {
            if (mode=="stack" || mode=="stack_rev") {
                for (size_t j=0;j<parts.size();++j) {
                    size_t k=mode=="stack"?j:parts.size()-1-j;
                    if (parts[k].data[i]!=bg) { out.data[i]=parts[k].data[i]; break; }
                }
            } else {
                size_t hits=0;
                for (const auto& p:parts) hits+=p.data[i]!=bg;
                bool hit=mode=="and"?hits==parts.size():mode=="or"?hits>0:mode=="xor"?hits==1:hits==0;
                out.data[i]=hit?10:0;
            }
        }
        return out;
    }
    auto flat=summaries(parts,bg,mode);
    if (name=="cells_to_pixels") {
        Grid out(int(layout->rows.size()),int(layout->cols.size()));
        out.data=std::move(flat); return out;
    }
    if (name=="fill_cells") {
        Grid out=g;
        size_t i=0;
        for (auto [r,h]:layout->rows) for (auto [c,w]:layout->cols) {
            int value=flat[i++];
            for (int y=r;y<r+h;++y) for (int x=c;x<c+w;++x) out.at(y,x)=value;
        }
        return out;
    }
    fail();
}
}
