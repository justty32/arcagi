#pragma once
#include "prims.hpp"
#include "background.hpp"
#include <array>
#include <memory>

namespace arc {
inline const std::vector<std::string> CONNS={"4same","8same","4multi","8multi"};
inline const std::array<std::string,12> ATTRS={
    "color","shape_count","color_count","is_largest","is_smallest","size_rank",
    "size","touches_border","has_hole","h","w","shape"};
struct Obj { Component cells; std::vector<int> colors; std::array<Json,12> props; };
using Objs=std::vector<Obj>;
using Extracted=std::shared_ptr<const Objs>;
using Labels=std::vector<std::vector<int>>; // -1: don't care; 0: negative; 1: positive
using Selector=std::pair<std::string,Json>;
int attr_index(const std::string& attr);
Component hole_cells(const Component& cells);
Extracted extract(const Grid& grid,const std::string& conn);
bool validate_predicate(const Json& body);
bool evaluate_predicate(const Json& body,const Obj& obj,const Objs& group);
std::vector<size_t> selected(const Objs& objs,const std::string& attr,const Json& value,const Spec& spec);
std::vector<Selector> separate(const std::vector<Extracted>& groups,const Labels& labels);
std::vector<std::string> pred_selectors(const std::vector<Extracted>& groups,const Labels& labels,const Spec& spec);
std::vector<Selector> wide_selectors(const std::vector<Extracted>& groups);
Grid apply_objects(const Step& step,const Grid& grid,const Spec& spec);
std::vector<Step> narrow_objects(const std::string& name,const Grids& states,const Grids& targets,const Spec& spec);
std::vector<Step> object_candidates(const std::string& name,const Grids& states,const Grids& targets,const Spec& spec);
bool is_object_primitive(const std::string& name);
bool changed(const Obj& obj,const Grid& target);
std::optional<int> uniform(const Obj& obj,const Grid& target);
Grid apply_object_colormap(const Grid& grid,const Json& table);
std::optional<Json> fit_object_colormap(const Grids& states,const Grids& targets,const Grids& tests);
}
