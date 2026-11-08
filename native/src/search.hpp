#pragma once
#include "prims.hpp"

namespace arc {
struct Options {
    double budget=19.0;
    int max_depth=5;
    uint64_t max_nodes=20000000;
    size_t max_solutions=200;
    Json::Array seeds;
    size_t dump_prefixes=0;
    std::string prefix_out;
    // Learners fitted at every shape-matching state, and the colormap step.
    bool learn_colormap=true,learn_object_colormap=true,learn_local_rule=true,learn_vrule=true,colormap_step=true;
};
Json search(const Json& request,const Spec& spec,const Options& options);
}
