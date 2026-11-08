#include "objects.hpp"
#include <algorithm>
#include <deque>
#include <unordered_map>

namespace arc {
int attr_index(const std::string& attr) {
    auto it=std::find(ATTRS.begin(),ATTRS.end(),attr);
    if (it==ATTRS.end()) fail();
    return int(it-ATTRS.begin());
}
Component hole_cells(const Component& cells) {
    Box b=cells_bbox(cells);
    int h=b.h+2,w=b.w+2;
    std::vector<bool> own(h*w),seen(h*w);
    for (auto [y,x]:cells) own[(y-b.top+1)*w+x-b.left+1]=true;
    Component stack={{0,0}},out;
    seen[0]=true;
    const Component dirs={{-1,0},{1,0},{0,-1},{0,1}};
    while (!stack.empty()) {
        auto [y,x]=stack.back(); stack.pop_back();
        for (auto [dy,dx]:dirs) {
            int ny=y+dy,nx=x+dx;
            if (ny<0 || ny>=h || nx<0 || nx>=w || seen[ny*w+nx] || own[ny*w+nx]) continue;
            seen[ny*w+nx]=true; stack.emplace_back(ny,nx);
        }
    }
    for (int y=1;y<h-1;++y) for (int x=1;x<w-1;++x)
        if (!seen[y*w+x] && !own[y*w+x]) out.emplace_back(y-1+b.top,x-1+b.left);
    return out;
}
Extracted extract(const Grid& g,const std::string& conn) {
    if (std::find(CONNS.begin(),CONNS.end(),conn)==CONNS.end()) fail();
    int bg=object_background(g);
    std::string key=std::to_string(g.h)+","+std::to_string(g.w)+","+std::to_string(bg)+","+conn+":";
    for (int c:g.data) { key+=std::to_string(c); key+=','; }
    static std::unordered_map<std::string,Extracted> cache;
    static std::deque<std::string> order;
    if (auto it=cache.find(key);it!=cache.end()) return it->second;
    auto raw=objects(g,bg,conn[0]=='8',conn.ends_with("same"));
    auto out=std::make_shared<Objs>();
    std::vector<int> sizes,cs,distinct;
    std::vector<std::string> shapes;
    std::map<int,int> color_counts;
    std::map<std::string,int> shape_counts;
    for (const auto& cells:raw) {
        // Counter.most_common ties follow the component's DFS traversal order.
        std::map<int,int> ns;
        for (auto [y,x]:cells) ++ns[g.at(y,x)];
        int color=g.at(cells[0].first,cells[0].second);
        for (auto [y,x]:cells) if (ns[g.at(y,x)]>ns[color]) color=g.at(y,x);
        cs.push_back(color); ++color_counts[color];
        sizes.push_back(int(cells.size()));
        Box b=cells_bbox(cells);
        std::string bits(b.h*b.w,'0');
        for (auto [y,x]:cells) bits[(y-b.top)*b.w+x-b.left]='1';
        shapes.push_back(std::to_string(b.h)+"x"+std::to_string(b.w)+":"+bits);
        ++shape_counts[shapes.back()];
    }
    distinct=sizes;
    std::sort(distinct.begin(),distinct.end(),std::greater<int>());
    distinct.erase(std::unique(distinct.begin(),distinct.end()),distinct.end());
    for (size_t i=0;i<raw.size();++i) {
        Obj o; o.cells=std::move(raw[i]);
        std::sort(o.cells.begin(),o.cells.end());
        bool border=false;
        for (auto [y,x]:o.cells) {
            o.colors.push_back(g.at(y,x));
            border=border || y==0 || y==g.h-1 || x==0 || x==g.w-1;
        }
        Box b=cells_bbox(o.cells);
        o.props={Json(cs[i]),Json(shape_counts[shapes[i]]),Json(color_counts[cs[i]]),
            Json(int(sizes[i]==distinct.front())),Json(int(sizes[i]==distinct.back())),
            Json(int(std::find(distinct.begin(),distinct.end(),sizes[i])-distinct.begin()+1)),
            Json(sizes[i]),Json(int(border)),Json(int(!hole_cells(o.cells).empty())),Json(b.h),Json(b.w),Json(shapes[i])};
        out->push_back(std::move(o));
    }
    if (cache.size()>=8192) { cache.erase(order.front()); order.pop_front(); }
    order.push_back(key); cache.emplace(std::move(key),out);
    return out;
}
namespace {
bool number(const Json& j) { return std::holds_alternative<double>(j.value) || std::holds_alternative<bool>(j.value); }
int integer(const Json& j) { return std::holds_alternative<bool>(j.value)?int(std::get<bool>(j.value)):j.integer(); }
bool equal(const Json& a,const Json& b) {
    return number(a) && number(b)?integer(a)==integer(b):a==b;
}
Json prop(const Obj& o,const Json& attr) {
    if (!std::holds_alternative<std::string>(attr.value)) fail();
    auto it=std::find(ATTRS.begin(),ATTRS.end(),attr.str());
    return it==ATTRS.end()?Json():o.props[it-ATTRS.begin()];
}
}
bool validate_predicate(const Json& body) {
    if (!body.array() || !body.size() || !std::holds_alternative<std::string>(body[0].value)) return false;
    const auto& op=body[0].str();
    if (op=="eq" || op=="ne" || op=="gt" || op=="lt")
        return body.size()==3 && std::holds_alternative<std::string>(body[1].value);
    if (op=="rank") return body.size()==3 && (body[2]==Json("max") || body[2]==Json("min"));
    if (op=="not") return body.size()==2 && validate_predicate(body[1]);
    if (op!="and" && op!="or") return false;
    if (body.size()<2) return false;
    for (size_t i=1;i<body.size();++i) if (!validate_predicate(body[i])) return false;
    return true;
}
bool evaluate_predicate(const Json& body,const Obj& obj,const Objs& group) {
    const auto& op=body[0].str();
    if (op=="eq" || op=="ne" || op=="gt" || op=="lt") {
        Json have=prop(obj,body[1]); const auto& want=body[2];
        if (op=="eq") return equal(have,want);
        if (op=="ne") return !equal(have,want);
        if (!number(have) || !number(want)) return false;
        return op=="gt"?integer(have)>integer(want):integer(have)<integer(want);
    }
    if (op=="rank") {
        std::optional<int> best;
        for (const auto& o:group) {
            Json v=prop(o,body[1]);
            if (number(v) && (!best || (body[2]==Json("max")?integer(v)>*best:integer(v)<*best))) best=integer(v);
        }
        return best && equal(prop(obj,body[1]),Json(*best));
    }
    if (op=="not") return !evaluate_predicate(body[1],obj,group);
    if (op=="and" || op=="or") {
        for (size_t i=1;i<body.size();++i) {
            bool v=evaluate_predicate(body[i],obj,group);
            if (op=="and" && !v) return false;
            if (op=="or" && v) return true;
        }
        return op=="and";
    }
    fail();
}
std::vector<size_t> selected(const Objs& objs,const std::string& attr,const Json& value,const Spec& spec) {
    std::vector<size_t> out;
    int index=attr=="all" || attr=="pred"?-1:attr_index(attr);
    const Json* body=&value;
    if (attr=="pred") {
        if (std::holds_alternative<std::string>(value.value)) body=&spec.predicates.at(value.str());
        else if (!validate_predicate(value)) fail();
    }
    for (size_t i=0;i<objs.size();++i)
        if (attr=="all" || (attr=="pred"?evaluate_predicate(*body,objs[i],objs):equal(objs[i].props[index],value))) out.push_back(i);
    return out;
}
std::vector<Selector> separate(const std::vector<Extracted>& groups,const Labels& labels) {
    std::vector<const Obj*> pos,neg;
    for (size_t i=0;i<groups.size();++i) for (size_t j=0;j<groups[i]->size();++j) {
        if (labels[i][j]==1) pos.push_back(&groups[i]->at(j));
        if (labels[i][j]==0) neg.push_back(&groups[i]->at(j));
    }
    if (pos.empty()) return {};
    if (neg.empty()) return {{"all",1}};
    std::vector<Selector> out;
    for (size_t a=0;a<ATTRS.size();++a) {
        const auto& value=pos[0]->props[a];
        if (std::all_of(pos.begin(),pos.end(),[&](auto p){return p->props[a]==value;}) &&
            std::all_of(neg.begin(),neg.end(),[&](auto p){return p->props[a]!=value;})) out.emplace_back(ATTRS[a],value);
        if (out.size()==2) break;
    }
    return out;
}
std::vector<std::string> pred_selectors(const std::vector<Extracted>& groups,const Labels& labels,const Spec& spec) {
    bool positive=false;
    for (const auto& labs:labels) for (int lab:labs) positive=positive || lab==1;
    if (!positive) return {};
    std::vector<std::string> out;
    for (const auto& name:spec.predicate_names) {
        const auto& body=spec.predicates.at(name);
        bool ok=true;
        for (size_t i=0;i<groups.size() && ok;++i) for (size_t j=0;j<groups[i]->size();++j)
            if (labels[i][j]!=-1 && bool(labels[i][j])!=evaluate_predicate(body,groups[i]->at(j),*groups[i])) { ok=false; break; }
        if (ok) out.push_back(name);
        if (out.size()==2) break;
    }
    return out;
}
std::vector<Selector> wide_selectors(const std::vector<Extracted>& groups) {
    std::vector<Selector> out;
    if (groups.empty()) return out;
    for (size_t a=0;a<ATTRS.size();++a) {
        std::vector<Json> values;
        for (const auto& o:*groups[0]) if (std::find(values.begin(),values.end(),o.props[a])==values.end()) values.push_back(o.props[a]);
        std::vector<size_t> indices;
        for (size_t i=0;i<values.size();++i) indices.push_back(i);
        std::sort(indices.begin(),indices.end(),[&](size_t i,size_t j){
            const auto& x=values[i]; const auto& y=values[j];
            return std::holds_alternative<std::string>(x.value)?x.str()<y.str():x.integer()<y.integer();
        });
        for (size_t i:indices) {
            const auto& v=values[i];
            bool common=true;
            for (const auto& group:groups)
                if (std::none_of(group->begin(),group->end(),[&](const Obj& o){return o.props[a]==v;})) { common=false; break; }
            if (common) out.emplace_back(ATTRS[a],v);
            if (out.size()==24) return out;
        }
    }
    return out;
}
bool changed(const Obj& o,const Grid& target) {
    for (size_t i=0;i<o.cells.size();++i) if (target.at(o.cells[i].first,o.cells[i].second)!=o.colors[i]) return true;
    return false;
}
std::optional<int> uniform(const Obj& o,const Grid& target) {
    int color=target.at(o.cells[0].first,o.cells[0].second);
    for (auto [y,x]:o.cells) if (target.at(y,x)!=color) return std::nullopt;
    return color;
}
}
