#pragma once
#include "grid.hpp"

namespace arc {
inline constexpr int OUTSIDE=-1;
inline constexpr int MIN_SUPPORT=1;
Grid apply_colormap(const Grid& g,const Json& table);
Grid apply_local_rule(const Grid& g,const std::string& features,const Json& table);
std::optional<Json> fit_colormap(const Grids& states,const Grids& targets,const Grids& tests);
std::optional<Json> fit_local_rule(const Grids& states,const Grids& targets,const Grids& tests,const std::string& features);
}
