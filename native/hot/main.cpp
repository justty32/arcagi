// Batch entry point for the isolated CPU hot-path builds.
#include <cstring>
#include <vector>

int arcsearch_main(int argc, char** argv);

int main(int argc, char** argv) {
    std::vector<char*> args{argv[0]};
    static char batch[] = "--batch";
    if (argc < 2 || std::strcmp(argv[1], "--batch") != 0) args.push_back(batch);
    for (int i = 1; i < argc; ++i) args.push_back(argv[i]);
    args.push_back(nullptr);
    return arcsearch_main(int(args.size()) - 1, args.data());
}
