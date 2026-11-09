// E11 semantic check (reports/gpusynth-1110/): re-evaluate gpusynth samples with the CPU seed
// interpreter (native/src/seed_value.cpp, seed::compile + seed::eval) and compare with the GPU output.
// Reservoir-samples --n rows from the jsonl; prints per-primitive coverage and every mismatch (first 20 shown).
// usage: gpusynth_verify --jsonl f.jsonl --data data/ARC-AGI/data/training --n 10000 [--seed 1] [--only and,or,if]
#include <cstdio>
#include <fstream>
#include <map>
#include <random>
#include <set>
#include <string>
#include <vector>
#include "../../src/json.hpp"
#include "../../src/seed.hpp"
#include "../../src/seed_value.hpp"
using arc::Json;
static void prims(const Json& j, std::set<std::string>& out) {
    if (!j.array() || j.items().empty()) return;
    const Json& h = j[0];
    if (std::holds_alternative<std::string>(h.value)) out.insert(h.str());
    for (size_t i = 1; i < j.items().size(); ++i) prims(j[i], out);
}
int main(int argc, char** argv) {
    std::string path, data, only; long n = 10000; unsigned seed = 1;
    for (int i = 1; i + 1 < argc; i += 2) {
        std::string a = argv[i];
        if (a == "--jsonl") path = argv[i + 1]; else if (a == "--data") data = argv[i + 1];
        else if (a == "--only") only = argv[i + 1];
        else if (a == "--n") n = atol(argv[i + 1]); else if (a == "--seed") seed = unsigned(atol(argv[i + 1]));
    }
    std::ifstream in(path); std::string line; std::vector<std::string> res; std::mt19937_64 R(seed); long seen = 0;
    while (std::getline(in, line)) {
        if (line.empty()) continue;
        if (!only.empty()) {  // --only and,or,...: keep rows whose program uses one of these primitives
            bool hit = false; size_t p0 = 0;
            while (!hit && p0 <= only.size()) { size_t q = only.find(',', p0); if (q == std::string::npos) q = only.size();
                hit = line.find("[\"" + only.substr(p0, q - p0) + "\"") != std::string::npos; p0 = q + 1; }
            if (!hit) continue;
        }
        if (long(res.size()) < n) res.push_back(line);
        else { long k = long(R() % uint64_t(seen + 1)); if (k < n) res[size_t(k)] = line; }
        ++seen;
    }
    std::map<std::string, Json> tasks; std::map<std::string, long> cover, bad; long nbad = 0, nerr = 0;
    for (const auto& l : res) {
        Json j = Json::parse(l);
        const std::string& tn = j["task"].str(); int ex = j["ex"].integer();
        if (!tasks.count(tn)) tasks[tn] = arc::read_json(data + "/" + tn + ".json");
        const Json& t = tasks[tn]; size_t ntr = t["train"].items().size();
        const Json& g = ex < int(ntr) ? t["train"][size_t(ex)]["input"] : t["test"][size_t(ex) - ntr]["input"];
        std::set<std::string> ps; prims(j["prog"], ps);
        for (auto& p : ps) cover[p]++;
        seed::arena().reset();
        int root = seed::compile(seed::from_json(j["prog"]));
        bool ok = false; std::string why = "compile";
        if (root >= 0) {
            seed::Ctx c{seed::from_data(g), seed::MAX_STEPS};
            seed::V v = seed::eval(root, nullptr, 0, c);
            if (v == seed::ERR) { why = "eval-error"; ++nerr; }
            else { ok = seed::to_data(v) == j["out"]; why = "output-differs"; }
        }
        if (!ok) {
            ++nbad; for (auto& p : ps) bad[p]++;
            if (nbad <= 20) fprintf(stderr, "MISMATCH (%s): %s\n", why.c_str(), l.substr(0, 400).c_str());
        }
    }
    printf("{\"rows_in_file\": %ld, \"checked\": %zu, \"mismatch\": %ld, \"cpu_eval_error\": %ld, \"per_prim\": {", seen, res.size(), nbad, nerr);
    bool first = true;
    for (auto& [p, c] : cover) { printf("%s\"%s\": [%ld, %ld]", first ? "" : ", ", p.c_str(), c, bad.count(p) ? bad[p] : 0L); first = false; }
    printf("}}\n");
    return nbad ? 2 : 0;
}
