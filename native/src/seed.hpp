// Seed (empty-tree) language: a C++ port of src/arcagi/seed/ (Python is the
// reference). Values, types, interpreter, enumerator, deductive splits.
// Every routine mirrors the Python one it names so results agree exactly:
// programs, node counts, nodes_to_first and the near list.
#pragma once
#include "json.hpp"
#include <cstdint>
#include <memory>
#include <string>
#include <vector>

namespace seed {

// ---- symbols (global, interned before worker threads start) -------------
int sym(const std::string& s);
const std::string& sym_name(int id);

// ---- program trees: Python tuples of ints, strings and tuples -----------
struct PN;
using PP = std::shared_ptr<const PN>;
struct PN {
    enum Kind : uint8_t { INT, STR, TUP, BAD } kind;
    int64_t i = 0;   // INT
    int s = -1;      // STR: symbol
    std::vector<PP> kids;  // TUP
};
PP p_int(int64_t v);
PP p_str(int s);
PP p_tup(std::vector<PP> kids);
PP p_leaf(int s);  // ("name",)
PP from_json(const arc::Json& j);
arc::Json to_json(const PP& p);
bool p_eq(const PP& a, const PP& b);

// ---- library -------------------------------------------------------------
struct Block {
    std::string name;
    int name_sym;
    PP body;
    std::string sig;  // type string
};
struct Lib {
    std::vector<Block> blocks;
};
Lib load_lib(const std::string& path);  // empty path or missing file -> empty

// ---- solve ---------------------------------------------------------------
using Grid = std::vector<std::vector<int>>;
struct Example { arc::Json input, output; bool has_output = true; };
struct Settings {
    long budget = 100000;
    bool decompose = true;
    std::vector<std::string> splits;  // with decompose: subset of the r07 splits (empty = all)
    int lam_depth = 2;
    std::vector<std::string> exclude;
    std::vector<std::pair<std::string, double>> order;
};
struct SolveOut {
    PP program;  // null if none
    long nodes = 0;
    long nodes_to_first = -1;  // -1 = None
    double seconds = 0;
    std::vector<std::pair<PP, double>> near;
    long eval_steps = 0;  // primitive applications actually executed (extra, not in Python)
    bool train_ok = false, test_ok = false;
    std::string error;  // Python would have raised (see README)
};
SolveOut solve_task(const std::vector<Example>& train, const std::vector<Example>& test,
                    const Lib& lib, const Settings& st);

// Evaluate one program on one input; returns the value as JSON, or the
// string "ERR". ``exclude`` removes primitives as seed.prims.without does.
arc::Json run_json(const PP& prog, const arc::Json& input, const Lib& lib,
                   const std::vector<std::string>& exclude);

int seed_main(int argc, char** argv);
}  // namespace seed
