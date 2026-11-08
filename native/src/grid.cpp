#include "grid.hpp"
#include <algorithm>
#include <limits>
#include <tuple>

namespace arc {
Grid::Grid(int height,int width,int fill) : h(std::max(0,height)),w(std::max(0,width)) {
    if (!h) w=0;
    data.assign(size_t(h)*w,fill);
}
bool Grid::valid() const {
    return bounds() && std::all_of(data.begin(),data.end(),[](int c){return c>=0 && c<=9;});
}
Grid from_json(const Json& j) {
    int h=int(j.size()),w=h?int(j[0].size()):0;
    Grid g(h,w);
    for (int y=0;y<h;++y) {
        if (int(j[y].size())!=w) fail();
        for (int x=0;x<w;++x) g.at(y,x)=j[y][x].integer();
    }
    return g;
}
Json to_json(const Grid& g) {
    Json::Array rows;
    for (int y=0;y<g.h;++y) {
        Json::Array row;
        for (int x=0;x<g.w;++x) row.emplace_back(g.at(y,x));
        rows.emplace_back(row);
    }
    return rows;
}
bool same_shape(const Grid& a,const Grid& b) { return a.h==b.h && a.w==b.w; }
std::map<int,int> counts(const Grid& g) {
    std::map<int,int> out;
    for (int c:g.data) ++out[c];
    return out;
}
std::set<int> colors(const Grids& grids) {
    std::set<int> out;
    for (const auto& g:grids) out.insert(g.data.begin(),g.data.end());
    return out;
}
int background(const Grids& grids) {
    std::map<int,int> ns;
    for (const auto& g:grids) for (int c:g.data) ++ns[c];
    if (ns.empty()) fail();
    int best=ns.begin()->first;
    for (auto [c,n]:ns) if (std::tuple(n,c==0,-c)>std::tuple(ns[best],best==0,-best)) best=c;
    return best;
}
int background(const Grid& g) { return background(Grids{g}); }
Grid transform(const Grid& g,const std::string& name) {
    bool trans=name=="transpose" || name=="rot90" || name=="rot270" || name=="anti_transpose";
    Grid out(trans?g.w:g.h,trans?g.h:g.w);
    for (int y=0;y<out.h;++y) for (int x=0;x<out.w;++x) {
        int sy=y,sx=x;
        if (name=="flip_lr") sx=g.w-1-x;
        else if (name=="flip_ud") sy=g.h-1-y;
        else if (name=="rot180") { sy=g.h-1-y; sx=g.w-1-x; }
        else if (name=="transpose") { sy=x; sx=y; }
        else if (name=="rot90") { sy=g.h-1-x; sx=y; }
        else if (name=="rot270") { sy=x; sx=g.w-1-y; }
        else if (name=="anti_transpose") { sy=g.h-1-x; sx=g.w-1-y; }
        else fail();
        out.at(y,x)=g.at(sy,sx);
    }
    return out;
}
Grid scale(const Grid& g,int fy,int fx,const std::string& name) {
    if (name=="downscale") {
        if (!fy || !fx || g.h%fy || g.w%fx) fail();
        int ay=std::abs(fy),ax=std::abs(fx);
        Grid out(g.h/ay,g.w/ax);
        for (int y=0;y<out.h;++y) for (int x=0;x<out.w;++x)
            out.at(y,x)=g.at(fy>0?y*ay:g.h-1-y*ay,fx>0?x*ax:g.w-1-x*ax);
        return out;
    }
    long long nh=1LL*g.h*std::max(0,fy),nw=1LL*g.w*std::max(0,fx);
    if (nh>std::numeric_limits<int>::max() || nw>std::numeric_limits<int>::max()) fail();
    Grid out(int(nh),int(nw),0);
    for (int y=0;y<out.h;++y) for (int x=0;x<out.w;++x)
        out.at(y,x)=name=="tile"?g.at(y%g.h,x%g.w):g.at(y/fy,x/fx);
    return out;
}
Grid crop(const Grid& g,Box b) {
    auto norm=[](int x,int len){return std::clamp(x<0?x+len:x,0,len);};
    int y0=norm(b.top,g.h),y1=norm(b.top+b.h,g.h);
    int x0=norm(b.left,g.w),x1=norm(b.left+b.w,g.w);
    Grid out(std::max(0,y1-y0),std::max(0,x1-x0));
    for (int y=0;y<out.h;++y) for (int x=0;x<out.w;++x) out.at(y,x)=g.at(y0+y,x0+x);
    return out;
}
std::optional<Box> bbox(const Grid& g,int bg) {
    Component cells;
    for (int y=0;y<g.h;++y) for (int x=0;x<g.w;++x) if (g.at(y,x)!=bg) cells.emplace_back(y,x);
    if (cells.empty()) return std::nullopt;
    return cells_bbox(cells);
}
Box cells_bbox(const Component& cells) {
    if (cells.empty()) fail();
    int top=cells[0].first,left=cells[0].second,bottom=top,right=left;
    for (auto [y,x]:cells) { top=std::min(top,y); left=std::min(left,x); bottom=std::max(bottom,y); right=std::max(right,x); }
    return {top,left,bottom-top+1,right-left+1};
}
std::vector<Component> objects(const Grid& g,int bg,bool diagonal,bool by_color) {
    std::vector<Point> dirs={{-1,0},{1,0},{0,-1},{0,1}};
    if (diagonal) dirs.insert(dirs.end(),{{-1,-1},{-1,1},{1,-1},{1,1}});
    std::vector<bool> seen(g.data.size());
    std::vector<Component> out;
    for (int y=0;y<g.h;++y) for (int x=0;x<g.w;++x) {
        if (seen[y*g.w+x] || g.at(y,x)==bg) continue;
        int color=g.at(y,x);
        Component stack={{y,x}},part;
        seen[y*g.w+x]=true;
        while (!stack.empty()) {
            auto [r,c]=stack.back(); stack.pop_back(); part.emplace_back(r,c);
            for (auto [dy,dx]:dirs) {
                int nr=r+dy,nc=c+dx;
                if (nr<0 || nr>=g.h || nc<0 || nc>=g.w || seen[nr*g.w+nc]) continue;
                int v=g.at(nr,nc);
                if (v==bg || (by_color && v!=color)) continue;
                seen[nr*g.w+nc]=true; stack.emplace_back(nr,nc);
            }
        }
        out.push_back(std::move(part));
    }
    return out;
}
uint64_t signature(const Grids& grids,size_t n) {
    uint64_t h=14695981039346656037ULL;
    auto mix=[&h](uint64_t v){h^=v; h*=1099511628211ULL;};
    mix(n);
    for (size_t i=0;i<n;++i) {
        const Grid& g=grids[i]; mix(g.h); mix(g.w);
        for (int c:g.data) mix(uint64_t(c));
    }
    return h;
}
}
