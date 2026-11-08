#include "search.hpp"
#include "background.hpp"
#include <cmath>
#include <filesystem>
#include <iostream>

int main(int argc,char** argv) {
    using namespace arc;
    try {
        Options options;
        bool run_mode=false,list_ported=false;
        std::string request_path,out_path,spec_path,seeds_path;
        for (int i=1;i<argc;++i) {
            std::string arg=argv[i];
            if (arg=="--run") { run_mode=true; continue; }
            if (arg=="--list-ported") { list_ported=true; continue; }
            if (arg=="--help") {
                std::cout<<"arcsearch --run [--spec PATH]\narcsearch --list-ported [--spec PATH]\narcsearch --request PATH [--budget SECONDS] [--max-depth D] [--max-nodes N] [--max-solutions N] [--seeds PATH] [--dump-prefixes K --prefix-out PATH] [--spec PATH] [--out PATH]\n";
                return 0;
            }
            if (i+1>=argc) fail();
            std::string value=argv[++i];
            if (arg=="--request") request_path=value;
            else if (arg=="--out") out_path=value;
            else if (arg=="--spec") spec_path=value;
            else if (arg=="--seeds") seeds_path=value;
            else if (arg=="--dump-prefixes") options.dump_prefixes=std::stoull(value);
            else if (arg=="--prefix-out") options.prefix_out=value;
            else if (arg=="--budget") options.budget=std::stod(value);
            else if (arg=="--max-depth") options.max_depth=std::stoi(value);
            else if (arg=="--max-nodes") options.max_nodes=std::stoull(value);
            else if (arg=="--max-solutions") options.max_solutions=std::stoull(value);
            else fail();
        }
        if (!std::isfinite(options.budget) || options.budget<=0 || options.max_depth<=0 || !options.max_nodes || !options.max_solutions) fail();
        if (spec_path.empty()) {
            auto binary=std::filesystem::canonical("/proc/self/exe");
            spec_path=(binary.parent_path()/"../spec.json").lexically_normal().string();
        }
        Spec spec(read_json(spec_path));
        if (list_ported) {
            Json::Array names;
            for (const auto& name:spec.names) names.emplace_back(name);
            std::cout<<Json(names).dump()<<'\n';
        } else if (run_mode) {
            std::string line;
            while (std::getline(std::cin,line)) {
                try {
                    Json request=Json::parse(line);
                    std::optional<int> bg;
                    if (request.fields().contains("bg") && request["bg"].value!=Json().value) bg=request["bg"].integer();
                    set_task_background(bg);
                    Grid out=run(request["program"].items(),from_json(request["grid"]),spec);
                    std::cout<<Json(Json::Object{{"out",to_json(out)}}).dump()<<'\n';
                } catch (const std::exception&) { std::cout<<"{\"error\":true}\n"; }
            }
        } else {
            if (request_path.empty()) fail();
            if (!seeds_path.empty()) options.seeds=read_json(seeds_path).items();
            Json result=search(read_json(request_path),spec,options);
            if (out_path.empty()) std::cout<<result.dump()<<'\n';
            else write_json(out_path,result);
        }
        return 0;
    } catch (const std::exception& e) {
        std::cerr<<"arcsearch: "<<e.what()<<'\n';
        return 1;
    }
}
