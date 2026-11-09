// N5c wrapper (bin/arcbatch-gpuseed): arcsearch --batch with a GPU seed layer.
// Strips --gpu-seed, --gpu-min N, --seed-prof; inserts --batch; calls the
// unchanged src/main.cpp (compiled with -Dmain=arcsearch_main).
// Env ARC_GPUSEED_VERIFY=1: re-check every GPU SKIP/NODE on CPU (abort on mismatch).
#include "e2e.hpp"
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

int arcsearch_main(int argc, char** argv);

int main(int argc, char** argv) {
    std::vector<char*> args{argv[0]};
    static char batch[] = "--batch";
    if (argc < 2 || std::strcmp(argv[1], "--batch") != 0) args.push_back(batch);
    for (int i = 1; i < argc; ++i) {
        std::string a = argv[i];
        if (a == "--gpu-seed") { gseed::g_e2e.gpu = true; continue; }
        if (a == "--seed-prof") { gseed::g_e2e.prof = true; continue; }
        if (a == "--gpu-min" && i + 1 < argc) { gseed::g_e2e.gpu_min = std::stol(argv[++i]); continue; }
        args.push_back(argv[i]);
    }
    if (const char* v = std::getenv("ARC_GPUSEED_VERIFY")) gseed::g_e2e.verify = v[0] && v[0] != '0';
    args.push_back(nullptr);
    int rc = arcsearch_main(int(args.size()) - 1, args.data());
    if (gseed::g_e2e.prof) gseed::e2e_print_prof();
    return rc;
}
