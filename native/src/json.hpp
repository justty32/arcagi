#pragma once
#include <map>
#include <stdexcept>
#include <string>
#include <variant>
#include <vector>

namespace arc {
struct Json {
    using Array = std::vector<Json>;
    using Object = std::map<std::string, Json>;
    std::variant<std::nullptr_t, bool, double, std::string, Array, Object> value;
    Json() : value(nullptr) {}
    Json(bool x) : value(x) {}
    Json(int x) : value(double(x)) {}
    Json(double x) : value(x) {}
    Json(const char* x) : value(std::string(x)) {}
    Json(std::string x) : value(std::move(x)) {}
    Json(Array x) : value(std::move(x)) {}
    Json(Object x) : value(std::move(x)) {}
    bool array() const { return std::holds_alternative<Array>(value); }
    bool object() const { return std::holds_alternative<Object>(value); }
    const Array& items() const { return std::get<Array>(value); }
    Array& items() { return std::get<Array>(value); }
    const Object& fields() const { return std::get<Object>(value); }
    const std::string& str() const { return std::get<std::string>(value); }
    int integer() const;
    const Json& operator[](size_t i) const { return items().at(i); }
    const Json& operator[](const std::string& k) const { return fields().at(k); }
    size_t size() const { return items().size(); }
    bool operator==(const Json&) const = default;
    static Json parse(const std::string& text);
    std::string dump() const;
};
using Step = Json::Array;
using Program = Json::Array;
[[noreturn]] inline void fail() { throw std::runtime_error("error"); }
Json read_json(const std::string& path);
void write_json(const std::string& path, const Json& json);
}
