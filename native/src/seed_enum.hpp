// Seed enumerator internals (mirrors seed/enum.py, lam.py, cond.py, decomp.py).
#pragma once
#include "seed_value.hpp"
#include <unordered_map>

namespace seed {

struct BlockInfo {
    const Block* b;
    int sig = -1;           // type id
    int holes = 0;
    std::vector<int> hole_types;
    int ret = -1;
    bool free = false;      // free $0/$1 outside its own lambdas
    bool sig_fn = false;
};
struct LibView {
    std::vector<BlockInfo> blocks;
    std::unordered_map<int, size_t> by_name;  // symbol -> index
    const BlockInfo* find(int s) const {
        auto it = by_name.find(s);
        return it == by_name.end() ? nullptr : &blocks[it->second];
    }
};
LibView make_view(const Lib& lib, Types& T);
LibView sub_library(const LibView& lib);

int hole_count(const PP& p);
bool free_vars(const PP& p, int depth = 0);

// Subproblem: one _direct call of seed.decomp (or the whole task).
struct SubProblem {
    std::vector<V> xs, outs;
    int in_type, out_type;
    std::vector<std::tuple<PP, int, std::vector<V>>> extra;  // (prog, type, vals)
    bool sub = false;
    std::vector<int64_t> consts;
    int lam_body_max = 4;  // seed.lam.LAM_BODY_MAX unless a split asks for more
};
struct EnumResult {
    PP found;
    long nodes = 0;
    long nodes_to_first = -1;
    std::vector<std::pair<PP, double>> near;  // sorted best first
    long eval_steps = 0;
};


// Runs the Enumerator; with use_cond, the conditional witness after a failed
// search exactly as seed.decomp._Solver._direct does (cond_nodes = nodes it used).
struct Enumerator;
struct DirectOut { PP prog; long nodes = 0; long first = -1; long cond_used = 0; bool cond_hit = false;
                   std::vector<std::pair<PP, double>> near; long eval_steps = 0; };
DirectOut run_enum(Types& T, const LibView& lib, const SubProblem& sp, long budget,
                   int lam_depth, const std::vector<std::pair<int, double>>& order,
                   bool use_cond, long cond_budget, bool keep_near, bool cond_absolute = false);

std::vector<int64_t> task_consts(const std::vector<V>& values);
}  // namespace seed
