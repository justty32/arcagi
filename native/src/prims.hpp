#pragma once
#include "grid.hpp"
#include <unordered_set>

namespace arc {
const std::vector<std::string> D4={"flip_lr","flip_ud","transpose","rot90","rot180","rot270","anti_transpose"};
const std::vector<std::string> SPLIT_OPS={"and","or","xor","nor","left"};
const std::vector<std::string> HOWS={"largest","smallest","unique_color","most_colors","top_left"};
const std::vector<std::string> MIRRORS={"lr","ud","both","transpose","rot"};
const std::vector<std::string> DIRS={"down","up","left","right"};
const std::vector<std::string> PICKS={"unique","unique_mask","most_colors","least_colors","most_pixels","least_pixels"};
const std::vector<std::string> OVERLAYS={"and","or","xor","nor","stack","stack_rev"};
const std::vector<std::string> SUMMARIES={"majority","any","uniform","max_pixels"};
const std::unordered_set<std::string>& ported();
struct Spec {
    std::vector<std::string> names;
    std::unordered_set<std::string> live;
    std::map<std::string,Program> macros;
    std::vector<std::string> predicate_names;
    std::map<std::string,Json> predicates;
    explicit Spec(const Json& j);
    void enable_ext();
};
Grid apply_base(const Step& s,const Grid& g);
Grid apply_more(const Step& s,const Grid& g);
Grid apply_cells(const Step& s,const Grid& g);
const std::vector<std::string>& ext_names();
bool is_ext_primitive(const std::string& name);
Grid apply_ext(const Step& s,const Grid& g);
std::vector<Step> ext_candidates(const std::string& name,const Grids& states,const Grids& targets);
Grid apply_step(const Step& s,const Grid& g,const Spec& spec,bool in_macro=false);
Grid run(const Program& program,Grid grid,const Spec& spec);
std::pair<Grid,Grid> halves(const Grid& g,const std::string& axis);
struct Layout { int color; std::vector<Point> rows,cols; };
std::optional<Layout> split(const Grid& g);
Grids cut(const Grid& g,const Layout& layout);
std::vector<Step> narrow(const std::string& name,const Grids& states,const Grids& targets);
std::vector<Step> candidates(const std::string& name,const Grids& states,const Grids& targets,bool last,const Spec& spec);
double cost(const Program& program);
}
