#pragma once
#include "prims.hpp"

namespace arc {
struct Options {
    double budget=19.0;
    int max_depth=5;
    uint64_t max_nodes=20000000;
    size_t max_solutions=200;
};
Json search(const Json& request,const Spec& spec,const Options& options);
}
