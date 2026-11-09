// The normal hot batch wrapper plus a profiler report after workers join.
#include <cstring>
#include "prof.hpp"
#include <vector>

int arcsearch_main(int argc, char** argv);
int main(int argc, char** argv) {
    std::vector<char*> args{argv[0]};
    static char batch[] = "--batch";
    if (argc < 2 || std::strcmp(argv[1], "--batch") != 0) args.push_back(batch);
    for (int i = 1; i < argc; ++i) args.push_back(argv[i]);
    args.push_back(nullptr);
    auto start = std::chrono::steady_clock::now();
    uint64_t t0 = hotprof::enabled ? __rdtsc() : 0;
    int rc = arcsearch_main(int(args.size()) - 1, args.data());
    double wall = std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count();
    hotprof::report(wall, hotprof::enabled ? double(__rdtsc() - t0) / wall : 1.0);
    return rc;
}
