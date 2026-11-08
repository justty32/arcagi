#pragma once
#include "grid.hpp"

namespace arc {
std::optional<int> task_background(const Grids& grids);
void set_task_background(std::optional<int> color);
int object_background(const Grid& grid);
}
