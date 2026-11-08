#pragma once
#include "json.hpp"
#include <cstdint>
#include <optional>
#include <set>
#include <utility>

namespace arc {
struct Grid {
    int h=0, w=0;
    std::vector<int> data;
    Grid() = default;
    Grid(int height, int width, int fill=0);
    int& at(int y,int x) { return data.at(size_t(y)*w+x); }
    int at(int y,int x) const { return data.at(size_t(y)*w+x); }
    bool operator==(const Grid&) const = default;
    bool bounds() const { return h>0 && h<=30 && w>0 && w<=30; }
    bool valid() const;
};
using Grids=std::vector<Grid>;
using Point=std::pair<int,int>;
using Component=std::vector<Point>;
struct Box { int top,left,h,w; };
Grid from_json(const Json& j);
Json to_json(const Grid& g);
bool same_shape(const Grid& a,const Grid& b);
std::map<int,int> counts(const Grid& g);
std::set<int> colors(const Grids& grids);
int background(const Grid& g);
int background(const Grids& grids);
Grid transform(const Grid& g,const std::string& name);
Grid scale(const Grid& g,int fy,int fx,const std::string& name);
Grid crop(const Grid& g,Box box);
std::optional<Box> bbox(const Grid& g,int bg);
Box cells_bbox(const Component& cells);
std::vector<Component> objects(const Grid& g,int bg,bool diagonal,bool by_color);
uint64_t signature(const Grids& grids,size_t n);
}
