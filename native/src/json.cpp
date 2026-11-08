#include "json.hpp"
#include <cmath>
#include <fstream>
#include <iomanip>
#include <limits>
#include <sstream>

namespace arc {
int Json::integer() const {
    if (const auto* b = std::get_if<bool>(&value)) return *b;
    double n = std::get<double>(value);
    if (!std::isfinite(n) || n != std::trunc(n) || n < std::numeric_limits<int>::min()
        || n > std::numeric_limits<int>::max()) fail();
    return static_cast<int>(n);
}
namespace {
struct Parser {
    const std::string& s;
    size_t p = 0;
    void space() { while (p < s.size() && (s[p]==' ' || s[p]=='\n' || s[p]=='\r' || s[p]=='\t')) ++p; }
    char take() { if (p == s.size()) fail(); return s[p++]; }
    void expect(char c) { space(); if (take() != c) fail(); }
    unsigned hex() {
        unsigned n = 0;
        for (int i=0; i<4; ++i) {
            char c = take();
            int d = c>='0' && c<='9' ? c-'0' : c>='a' && c<='f' ? c-'a'+10 : c>='A' && c<='F' ? c-'A'+10 : -1;
            if (d<0) fail();
            n = n*16 + d;
        }
        return n;
    }
    void utf8(std::string& out, unsigned n) {
        if (n<0x80) out += char(n);
        else if (n<0x800) { out += char(0xc0|(n>>6)); out += char(0x80|(n&63)); }
        else if (n<0x10000) { out += char(0xe0|(n>>12)); out += char(0x80|((n>>6)&63)); out += char(0x80|(n&63)); }
        else { out += char(0xf0|(n>>18)); out += char(0x80|((n>>12)&63)); out += char(0x80|((n>>6)&63)); out += char(0x80|(n&63)); }
    }
    std::string string() {
        expect('"');
        std::string out;
        while (true) {
            char c = take();
            if (c=='"') return out;
            if (static_cast<unsigned char>(c)<32) fail();
            if (c!='\\') { out += c; continue; }
            switch (take()) {
            case '"': out += '"'; break;
            case '\\': out += '\\'; break;
            case '/': out += '/'; break;
            case 'b': out += '\b'; break;
            case 'f': out += '\f'; break;
            case 'n': out += '\n'; break;
            case 'r': out += '\r'; break;
            case 't': out += '\t'; break;
            case 'u': {
                unsigned n=hex();
                if (n>=0xd800 && n<=0xdbff) {
                    if (take()!='\\' || take()!='u') fail();
                    unsigned lo=hex();
                    if (lo<0xdc00 || lo>0xdfff) fail();
                    n=0x10000+((n-0xd800)<<10)+(lo-0xdc00);
                }
                utf8(out,n); break;
            }
            default: fail();
            }
        }
    }
    Json parse() {
        space();
        if (p==s.size()) fail();
        char c=s[p];
        if (c=='"') return string();
        if (c=='[') {
            ++p; space(); Json::Array a;
            if (p<s.size() && s[p]==']') { ++p; return a; }
            while (true) { a.push_back(parse()); space(); c=take(); if (c==']') return a; if (c!=',') fail(); }
        }
        if (c=='{') {
            ++p; space(); Json::Object o;
            if (p<s.size() && s[p]=='}') { ++p; return o; }
            while (true) {
                std::string k=string(); expect(':');
                if (!o.emplace(k,parse()).second) fail();
                space(); c=take(); if (c=='}') return o; if (c!=',') fail();
            }
        }
        for (auto [word,j] : {std::pair{"null",Json()}, {"true",Json(true)}, {"false",Json(false)}}) {
            std::string token(word);
            if (s.compare(p,token.size(),token)==0) { p+=token.size(); return j; }
        }
        size_t start=p;
        if (s[p]=='-') ++p;
        if (p==s.size() || s[p]<'0' || s[p]>'9') fail();
        if (s[p]=='0') ++p;
        else while (p<s.size() && s[p]>='0' && s[p]<='9') ++p;
        if (p<s.size() && s[p]=='.') {
            ++p; size_t digits=p;
            while (p<s.size() && s[p]>='0' && s[p]<='9') ++p;
            if (p==digits) fail();
        }
        if (p<s.size() && (s[p]=='e' || s[p]=='E')) {
            ++p; if (p<s.size() && (s[p]=='+' || s[p]=='-')) ++p;
            size_t digits=p;
            while (p<s.size() && s[p]>='0' && s[p]<='9') ++p;
            if (p==digits) fail();
        }
        double n=std::stod(s.substr(start,p-start));
        if (!std::isfinite(n)) fail();
        return n;
    }
};
std::string quote(const std::string& s) {
    std::string out="\"";
    const char* digits="0123456789abcdef";
    for (unsigned char c:s) {
        if (c=='"' || c=='\\') { out+='\\'; out+=char(c); }
        else if (c<32) { out+="\\u00"; out+=digits[c>>4]; out+=digits[c&15]; }
        else out+=char(c);
    }
    return out+'"';
}
}
Json Json::parse(const std::string& text) {
    Parser parser{text};
    Json j=parser.parse(); parser.space();
    if (parser.p!=text.size()) fail();
    return j;
}
std::string Json::dump() const {
    if (std::holds_alternative<std::nullptr_t>(value)) return "null";
    if (auto* b=std::get_if<bool>(&value)) return *b?"true":"false";
    if (auto* n=std::get_if<double>(&value)) { std::ostringstream o; o<<std::setprecision(17)<<*n; return o.str(); }
    if (auto* s=std::get_if<std::string>(&value)) return quote(*s);
    std::string out;
    if (array()) {
        out="[";
        for (const auto& x:items()) { if (out.size()>1) out+=','; out+=x.dump(); }
        return out+']';
    }
    out="{";
    for (const auto& [k,v]:fields()) { if (out.size()>1) out+=','; out+=quote(k)+':'+v.dump(); }
    return out+'}';
}
Json read_json(const std::string& path) {
    std::ifstream f(path); if (!f) fail();
    std::ostringstream s; s<<f.rdbuf(); return Json::parse(s.str());
}
void write_json(const std::string& path, const Json& json) {
    std::ofstream f(path); if (!f) fail(); f<<json.dump()<<'\n'; if (!f) fail();
}
}
