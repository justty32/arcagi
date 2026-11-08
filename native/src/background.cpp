#include "background.hpp"
#include <algorithm>
#include <tuple>

namespace arc {
namespace { std::optional<int> current; }
std::optional<int> task_background(const Grids& grids) {
    std::map<int,int> total,border;
    for (const auto& g:grids) {
        for (int y=0;y<g.h;++y) for (int x=0;x<g.w;++x) {
            int c=g.at(y,x); ++total[c];
            if (y==0 || y==g.h-1 || x==0 || x==g.w-1) ++border[c];
        }
    }
    if (total.empty()) return std::nullopt;
    int best=total.begin()->first;
    for (auto [c,n]:total)
        if (std::tuple(n,border[c],c==0,-c)>std::tuple(total[best],border[best],best==0,-best)) best=c;
    return best;
}
void set_task_background(std::optional<int> color) {
    if (color && (*color<0 || *color>9)) fail();
    current=color;
}
int object_background(const Grid& g) {
    if (current && std::count(g.data.begin(),g.data.end(),*current)>=0.4*g.data.size()) return *current;
    return background(g);
}
}
