#include "prims.hpp"

namespace arc {
Grid apply_more(const Step& s,const Grid& g) {
    const std::string& name=s.at(0).str();
    const std::string& mode=s.at(1).str();
    if (name=="self_tile") {
        int bg=background(g);
        Grid out(g.h*g.h,g.w*g.w,bg);
        for (int y=0;y<out.h;++y) for (int x=0;x<out.w;++x) {
            bool hit=g.at(y/g.h,x/g.w)!=bg;
            if (mode!="pos") hit=!hit;
            if (hit) out.at(y,x)=g.at(y%g.h,x%g.w);
        }
        return out;
    }
    if (name=="symmetrize") {
        int hole=s.at(2).integer();
        Grids images;
        if (mode=="lr" || mode=="both") images.push_back(transform(g,"flip_lr"));
        if (mode=="ud" || mode=="both") images.push_back(transform(g,"flip_ud"));
        if (mode=="both") images.push_back(transform(g,"rot180"));
        if (mode=="transpose") images.push_back(transform(g,"transpose"));
        if (mode=="rot") for (const auto& n:{"rot90","rot180","rot270"}) images.push_back(transform(g,n));
        if (images.empty()) fail();
        for (const auto& im:images) if (!same_shape(im,g)) fail();
        Grid out=g;
        for (size_t i=0;i<g.data.size();++i) if (g.data[i]==hole) {
            for (const auto& im:images) if (im.data[i]!=hole) { out.data[i]=im.data[i]; break; }
        }
        return out;
    }
    if (name=="gravity") {
        int turn;
        if (mode=="down") turn=0;
        else if (mode=="left") turn=1;
        else if (mode=="up") turn=2;
        else if (mode=="right") turn=3;
        else fail();
        int bg=background(g);
        Grid work=g;
        for (int i=0;i<turn;++i) work=transform(work,"rot90");
        Grid out(work.h,work.w,bg);
        for (int x=0;x<work.w;++x) {
            int dst=work.h-1;
            for (int y=work.h-1;y>=0;--y) if (work.at(y,x)!=bg) out.at(dst--,x)=work.at(y,x);
        }
        for (int i=0;i<turn;++i) out=transform(out,"rot270");
        return out;
    }
    fail();
}
}
