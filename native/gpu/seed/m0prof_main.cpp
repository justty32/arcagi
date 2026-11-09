// M0 wrapper (bin/m0prof): bin/arcbatch (src/main.cpp as arcsearch_main, --batch inserted)
// with the instrumented enumerator m0prof_enum.cpp; prints one JSON line of
// exclusive time buckets to stderr at exit ({"m0prof": true, ...}).
#include "m0prof.hpp"
#include <chrono>
#include <cstring>
#include <vector>

int arcsearch_main(int argc, char** argv);

int main(int argc, char** argv) {
    std::vector<char*> args{argv[0]};
    static char batch[] = "--batch";
    if (argc < 2 || std::strcmp(argv[1], "--batch") != 0) args.push_back(batch);
    for (int i = 1; i < argc; ++i) args.push_back(argv[i]);
    args.push_back(nullptr);
    auto w0 = std::chrono::steady_clock::now(); uint64_t c0 = __rdtsc();
    int rc = arcsearch_main(int(args.size()) - 1, args.data());
    double ws = std::chrono::duration<double>(std::chrono::steady_clock::now() - w0).count();
    double hz = double(__rdtsc() - c0) / ws;
    const m0::Acc& g = m0::g_acc;
    fprintf(stderr, "{\"m0prof\": true, \"wall_s\": %.4f, \"tsc_ghz\": %.4f, \"enums\": %llu, \"nodes\": %llu, \"segs\": %llu",
            ws, hz / 1e9, (unsigned long long)g.enums, (unsigned long long)g.nodes, (unsigned long long)g.segs);
    fprintf(stderr, ", \"sec\": {");
    for (int b = 0; b < m0::NB; ++b) fprintf(stderr, "%s\"%s\": %.4f", b ? ", " : "", m0::NAMES[b], double(g.cyc[b]) / hz);
    fprintf(stderr, "}, \"calls\": {");
    for (int b = 0; b < m0::NB; ++b) fprintf(stderr, "%s\"%s\": %llu", b ? ", " : "", m0::NAMES[b], (unsigned long long)g.cnt[b]);
    fprintf(stderr, "}, \"seg_hist_log2\": [");
    for (int h = 0; h < m0::NH; ++h) fprintf(stderr, "%s%llu", h ? ", " : "", (unsigned long long)g.hist[h]);
    fprintf(stderr, "], \"size_nodes\": [");
    for (int s = 0; s < m0::NS; ++s) fprintf(stderr, "%s%llu", s ? ", " : "", (unsigned long long)g.size_nodes[s]);
    fprintf(stderr, "]}\n");
    return rc;
}
