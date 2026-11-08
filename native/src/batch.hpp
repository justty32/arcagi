#pragma once
#include "prims.hpp"

namespace arc {
// Precision gate on train-consistent programs; a negative limit is off.
struct Gate {
    int max_len_penalized=4;         // hybrid.py: drop >4 steps ending in local_rule/x_vrule
    int max_steps_before_learner=-1; // drop learner-terminated programs with more steps before it
    int max_table_rows=-1;           // drop learner tables with more rows
    double min_votes=0;              // abstain when top-1 has fewer votes
    // Support gate (hybrid.py SUPPORT_MIN, re-selected on training, D-r7-18):
    // train output cells per row of a terminal colormap / local_rule / x_vrule
    // table; 0 turns it off.
    double support_alone=0,support_after=16;
    static Gate from_json(const Json& j);
    bool rejects(const Program& p,double train_cells) const;
};
struct BatchArgs {
    std::string spec_path,configs_path,out_path,cache_dir;
    std::vector<std::string> task_paths;
    int threads=6;
    bool ext=false,dump=false;
};
int batch_main(const BatchArgs& args);
}
