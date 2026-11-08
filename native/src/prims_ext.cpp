// S1 extension primitives (x_*): rays, connecting lines, compression,
// crop by color and periodic fill/extension. Semantics are mirrored by the
// Python module src/arcagi/dsl/ext/ once the registry hook exists.
#include "prims.hpp"
#include "background.hpp"
#include <algorithm>

namespace arc {
namespace {
using Dir=std::pair<int,int>;
const std::map<std::string,std::vector<Dir>>& ray_dirs() {
    static const std::map<std::string,std::vector<Dir>> table={
        {"u",{{-1,0}}},{"d",{{1,0}}},{"l",{{0,-1}}},{"r",{{0,1}}},
        {"h",{{0,-1},{0,1}}},{"v",{{-1,0},{1,0}}},
        {"hv",{{-1,0},{1,0},{0,-1},{0,1}}},
        {"ul",{{-1,-1}}},{"ur",{{-1,1}}},{"dl",{{1,-1}}},{"dr",{{1,1}}},
        {"x",{{-1,-1},{-1,1},{1,-1},{1,1}}},
        {"all",{{-1,0},{1,0},{0,-1},{0,1},{-1,-1},{-1,1},{1,-1},{1,1}}}};
    return table;
}
bool inside(const Grid& g,int y,int x) { return y>=0 && y<g.h && x>=0 && x<g.w; }
bool open(const Grid& g,int y,int x,int bg) { return !inside(g,y,x) || g.at(y,x)==bg; }

Grid ray(const Grid& g,const std::string& dirs,const std::string& mode,int color) {
    auto it=ray_dirs().find(dirs);
    if (it==ray_dirs().end() || (mode!="pass" && mode!="stop")) fail();
    int bg=object_background(g);
    Grid out=g;
    for (int y=0;y<g.h;++y) for (int x=0;x<g.w;++x) {
        int c=g.at(y,x);
        if (c==bg || (color>=0 && c!=color)) continue;
        for (auto [dy,dx]:it->second) {
            int ny=y+dy,nx=x+dx;
            if (!inside(g,ny,nx) || g.at(ny,nx)!=bg) continue;
            if (dy && dx && !(open(g,y+dy,x,bg) && open(g,y,x+dx,bg))) continue;
            for (;inside(g,ny,nx);ny+=dy,nx+=dx) {
                if (g.at(ny,nx)!=bg) { if (mode=="stop") break; continue; }
                out.at(ny,nx)=c;
            }
        }
    }
    return out;
}
// Fill the bg run between consecutive same-colored non-bg cells along lines.
void connect_lines(const Grid& g,Grid& out,int bg,int dy,int dx) {
    std::vector<Point> starts;
    if (dy==0) for (int y=0;y<g.h;++y) starts.push_back({y,0});
    else if (dx==0) for (int x=0;x<g.w;++x) starts.push_back({0,x});
    else if (dx==1) { for (int x=g.w-1;x>=0;--x) starts.push_back({0,x}); for (int y=1;y<g.h;++y) starts.push_back({y,0}); }
    else { for (int x=0;x<g.w;++x) starts.push_back({0,x}); for (int y=1;y<g.h;++y) starts.push_back({y,g.w-1}); }
    for (auto [sy,sx]:starts) {
        int ly=-1,lx=-1;
        for (int y=sy,x=sx;inside(g,y,x);y+=dy,x+=dx) {
            int c=g.at(y,x);
            if (c==bg) continue;
            if (ly>=0 && g.at(ly,lx)==c)
                for (int py=ly+dy,px=lx+dx;py!=y || px!=x;py+=dy,px+=dx) out.at(py,px)=c;
            ly=y; lx=x;
        }
    }
}
Grid connect(const Grid& g,const std::string& axes) {
    static const std::map<std::string,std::vector<Dir>> table={
        {"h",{{0,1}}},{"v",{{1,0}}},{"hv",{{0,1},{1,0}}},{"vh",{{1,0},{0,1}}},
        {"d",{{1,1},{1,-1}}},{"all",{{0,1},{1,0},{1,1},{1,-1}}}};
    auto it=table.find(axes);
    if (it==table.end()) fail();
    int bg=object_background(g);
    Grid out=g;
    for (auto [dy,dx]:it->second) connect_lines(g,out,bg,dy,dx);
    return out;
}
Grid keep_rows(const Grid& g,const std::vector<int>& rows) {
    if (rows.empty()) fail();
    Grid out(int(rows.size()),g.w);
    for (int i=0;i<out.h;++i) for (int x=0;x<g.w;++x) out.at(i,x)=g.at(rows[i],x);
    return out;
}
Grid compress_rows(const Grid& g,bool dup,int bg) {
    std::vector<int> rows;
    for (int y=0;y<g.h;++y) {
        bool drop=true;
        for (int x=0;x<g.w;++x) {
            int ref=dup?(y?g.at(y-1,x):-1):bg;
            if (g.at(y,x)!=ref) { drop=false; break; }
        }
        if (!drop) rows.push_back(y);
    }
    return keep_rows(g,rows);
}
Grid compress(const Grid& g,const std::string& mode) {
    bool dup=mode.starts_with("dup");
    if (!dup && !mode.starts_with("bg")) fail();
    std::string axes=mode.substr(dup?3:2);
    if (axes!="" && axes!="_rows" && axes!="_cols") fail();
    int bg=object_background(g);
    Grid out=g;
    if (axes!="_cols") out=compress_rows(out,dup,bg);
    if (axes!="_rows") out=transform(compress_rows(transform(out,"transpose"),dup,bg),"transpose");
    return out;
}
Grid crop_color(const Grid& g,int color,const std::string& mode) {
    Component cells;
    for (int y=0;y<g.h;++y) for (int x=0;x<g.w;++x) if (g.at(y,x)==color) cells.push_back({y,x});
    if (cells.empty()) fail();
    Box b=cells_bbox(cells);
    if (mode=="inner") {
        if (b.h<3 || b.w<3) fail();
        return crop(g,{b.top+1,b.left+1,b.h-2,b.w-2});
    }
    Grid out=crop(g,b);
    if (mode=="only") {
        int bg=object_background(g);
        for (int& c:out.data) if (c!=color) c=bg;
    } else if (mode!="bbox") fail();
    return out;
}
std::vector<Dir> periods(int h,int w) {
    std::vector<Dir> out;
    for (int py=1;py<=h;++py) for (int px=1;px<=w;++px) out.push_back({py,px});
    std::stable_sort(out.begin(),out.end(),[](Dir a,Dir b){
        return std::tuple(a.first*a.second,a.first,a.second)<std::tuple(b.first*b.second,b.first,b.second);});
    return out;
}
// Lattices for "fill": rect (py,px) plus the 1D diagonal ones (x+y)%p and
// (x-y)%p; tried by class count, then kind (rect, anti, main), then py, px.
struct Lattice { int kind,py,px; int classes() const { return kind?py:py*px; } };
int class_of(const Lattice& l,int y,int x) {
    if (l.kind==0) return (y%l.py)*l.px+x%l.px;
    if (l.kind==1) return (y+x)%l.py;
    return ((y-x)%l.py+l.py)%l.py;
}
std::vector<Lattice> lattices(int h,int w) {
    std::vector<Lattice> out;
    for (int py=1;py<=h;++py) for (int px=1;px<=w;++px) if (py<h || px<w) out.push_back({0,py,px});
    for (int kind=1;kind<=2;++kind) for (int p=2;p<h+w-1;++p) out.push_back({kind,p,0});
    std::stable_sort(out.begin(),out.end(),[](const Lattice& a,const Lattice& b){
        return std::tuple(a.classes(),a.kind,a.py,a.px)<std::tuple(b.classes(),b.kind,b.py,b.px);});
    return out;
}
Grid period(const Grid& g,const std::string& mode,int color) {
    if (mode=="fill") {
        bool any=false;
        for (int c:g.data) any=any || c==color;
        if (!any) fail();
        for (const auto& l:lattices(g.h,g.w)) {
            std::vector<int> val(size_t(l.classes()),-1);
            bool ok=true;
            for (int y=0;y<g.h && ok;++y) for (int x=0;x<g.w;++x) {
                int c=g.at(y,x);
                if (c==color) continue;
                int& v=val[size_t(class_of(l,y,x))];
                if (v<0) v=c; else if (v!=c) { ok=false; break; }
            }
            if (!ok) continue;
            Grid out=g;
            for (int y=0;y<g.h && ok;++y) for (int x=0;x<g.w;++x) if (g.at(y,x)==color) {
                int v=val[size_t(class_of(l,y,x))];
                if (v<0) { ok=false; break; }
                out.at(y,x)=v;
            }
            if (ok) return out;
        }
        fail();
    }
    if (mode!="extend") fail();
    Component cells;
    for (int y=0;y<g.h;++y) for (int x=0;x<g.w;++x) if (g.at(y,x)!=color) cells.push_back({y,x});
    if (cells.empty()) fail();
    Box b=cells_bbox(cells);
    if (b.h==g.h && b.w==g.w) fail();
    for (auto [py,px]:periods(b.h,b.w)) {
        bool ok=true;
        for (int y=0;y<b.h && ok;++y) for (int x=0;x<b.w;++x)
            if (g.at(b.top+y,b.left+x)!=g.at(b.top+y%py,b.left+x%px)) { ok=false; break; }
        if (!ok) continue;
        Grid out=g;
        for (int y=0;y<g.h;++y) for (int x=0;x<g.w;++x) {
            int ry=((y-b.top)%py+py)%py,rx=((x-b.left)%px+px)%px;
            out.at(y,x)=g.at(b.top+ry,b.left+rx);
        }
        return out;
    }
    fail();
}
// Color-variable local rule: the n4/n8 key is abstracted (off-grid -1, bg 0,
// other colors numbered 1.. by first appearance, center first) and the output
// is 0 (bg), a variable 1..9, or 10+c for the literal color c.
using VKey=std::vector<int>;
const std::vector<Dir>& vneighbors(const std::string& features) {
    static const std::vector<Dir> n4={{-1,0},{1,0},{0,-1},{0,1}};
    static const std::vector<Dir> n8={{-1,-1},{-1,0},{-1,1},{0,-1},{0,1},{1,-1},{1,0},{1,1}};
    if (features=="n4") return n4;
    if (features=="n8") return n8;
    fail();
}
VKey vkey(const Grid& g,int y,int x,const std::vector<Dir>& steps,int bg,std::vector<int>& vars) {
    vars.clear();
    VKey k;
    auto token=[&](int ny,int nx) {
        if (!inside(g,ny,nx)) return -1;
        int c=g.at(ny,nx);
        if (c==bg) return 0;
        auto it=std::find(vars.begin(),vars.end(),c);
        if (it!=vars.end()) return int(it-vars.begin())+1;
        vars.push_back(c); return int(vars.size());
    };
    k.push_back(token(y,x));
    for (auto [dy,dx]:steps) k.push_back(token(y+dy,x+dx));
    return k;
}
int vencode(int dst,int bg,const std::vector<int>& vars) {
    if (dst==bg) return 0;
    auto it=std::find(vars.begin(),vars.end(),dst);
    if (it!=vars.end()) return int(it-vars.begin())+1;
    return 10+dst;
}
int vdecode(int token,int bg,const std::vector<int>& vars) {
    if (token==0) return bg;
    if (token>=10) return token-10;
    if (token<0 || size_t(token)>vars.size()) fail();
    return vars[size_t(token)-1];
}
Grid vrule(const Grid& g,const std::string& features,const Json& table) {
    std::map<VKey,int> lookup;
    for (const auto& row:table.items()) {
        if (!row.size()) fail();
        VKey k;
        for (size_t i=0;i+1<row.size();++i) k.push_back(row[i].integer());
        lookup[k]=row[row.size()-1].integer();
    }
    const auto& steps=vneighbors(features);
    int bg=object_background(g);
    std::vector<int> vars;
    Grid out=g;
    for (int y=0;y<g.h;++y) for (int x=0;x<g.w;++x) {
        auto k=vkey(g,y,x,steps,bg,vars);
        auto it=lookup.find(k);
        if (it!=lookup.end()) out.at(y,x)=vdecode(it->second,bg,vars);
        else if (g.at(y,x)>9) fail();
    }
    return out;
}
}

std::optional<Json> fit_vrule(const Grids& states,const Grids& targets,const Grids& tests,const std::string& features) {
    const auto& steps=vneighbors(features);
    std::map<VKey,int> lookup;
    std::vector<int> vars;
    for (size_t i=0;i<states.size();++i) {
        const Grid& s=states[i]; const Grid& t=targets[i];
        if (!same_shape(s,t)) return std::nullopt;
        int bg=object_background(s);
        for (int y=0;y<s.h;++y) for (int x=0;x<s.w;++x) {
            auto k=vkey(s,y,x,steps,bg,vars);
            int v=vencode(t.at(y,x),bg,vars);
            auto [it,inserted]=lookup.emplace(k,v);
            if (!inserted && it->second!=v) return std::nullopt;
        }
    }
    Json::Array table;
    for (const auto& [k,v]:lookup) if (k[0]!=v) {
        Json::Array row;
        for (int n:k) row.emplace_back(n);
        row.emplace_back(v); table.emplace_back(row);
    }
    if (table.empty()) return std::nullopt;
    for (const auto& t:tests) {
        int bg=object_background(t);
        for (int y=0;y<t.h;++y) for (int x=0;x<t.w;++x)
            if (!lookup.contains(vkey(t,y,x,steps,bg,vars))) return std::nullopt;
    }
    return Json(table);
}
namespace {
bool same_shapes(const Grids& states,const Grids& targets) {
    for (size_t i=0;i<states.size();++i) if (!same_shape(states[i],targets[i])) return false;
    return true;
}
bool shrinks(const Grids& states,const Grids& targets) {
    bool strict=false;
    for (size_t i=0;i<states.size();++i) {
        if (targets[i].h>states[i].h || targets[i].w>states[i].w) return false;
        strict=strict || targets[i].h<states[i].h || targets[i].w<states[i].w;
    }
    return strict;
}
std::set<int> common_colors(const Grids& states) {
    std::set<int> out;
    for (int c=0;c<=10;++c) {
        bool all=true;
        for (const auto& g:states) all=all && std::find(g.data.begin(),g.data.end(),c)!=g.data.end();
        if (all) out.insert(c);
    }
    return out;
}
}

const std::vector<std::string>& ext_names() {
    static const std::vector<std::string> names={"x_ray","x_connect","x_compress","x_crop_color","x_period","x_vrule"};
    return names;
}
bool is_ext_primitive(const std::string& name) { return name.starts_with("x_"); }

Grid apply_ext(const Step& s,const Grid& g) {
    const std::string& name=s.at(0).str();
    if (name=="x_ray") return ray(g,s.at(1).str(),s.at(2).str(),s.at(3).integer());
    if (name=="x_connect") return connect(g,s.at(1).str());
    if (name=="x_compress") return compress(g,s.at(1).str());
    if (name=="x_crop_color") return crop_color(g,s.at(1).integer(),s.at(2).str());
    if (name=="x_period") return period(g,s.at(1).str(),s.at(2).integer());
    if (name=="x_vrule") return vrule(g,s.at(1).str(),s.at(2));
    fail();
}

std::vector<Step> ext_candidates(const std::string& name,const Grids& states,const Grids& targets) {
    std::vector<Step> out;
    if (name=="x_ray") {
        if (!same_shapes(states,targets)) return out;
        // A color is a ray source only if no example loses it and some gains it.
        std::vector<int> sources;
        bool any_gain=false;
        for (int c:colors(states)) {
            bool ok=true,gain=false;
            for (size_t i=0;i<states.size();++i) {
                auto a=std::count(states[i].data.begin(),states[i].data.end(),c);
                auto b=std::count(targets[i].data.begin(),targets[i].data.end(),c);
                if (b<a) ok=false;
                if (b>a) gain=true;
            }
            if (ok && gain) sources.push_back(c);
            any_gain=any_gain || gain;
        }
        if (!any_gain) return out;
        if (sources.size()!=1) sources.insert(sources.begin(),-1);
        for (int c:sources) for (const auto& [dirs,_]:ray_dirs()) for (const auto& mode:{"pass","stop"})
            out.push_back({name,dirs,mode,c});
    } else if (name=="x_connect") {
        if (same_shapes(states,targets)) for (const auto& a:{"h","v","hv","vh","d","all"}) out.push_back({name,a});
    } else if (name=="x_compress") {
        if (shrinks(states,targets))
            for (const auto& m:{"dup","dup_rows","dup_cols","bg","bg_rows","bg_cols"}) out.push_back({name,m});
    } else if (name=="x_crop_color") {
        if (shrinks(states,targets))
            for (int c:common_colors(states)) for (const auto& m:{"bbox","inner","only"}) out.push_back({name,c,m});
    } else if (name=="x_period") {
        if (same_shapes(states,targets))
            for (int c:common_colors(states)) for (const auto& m:{"fill","extend"}) out.push_back({name,m,c});
    }
    return out;
}
}
