#include <filesystem>
#include <functional>
#include <vector>

namespace fs = std::filesystem;

namespace utils {
std::vector<fs::path> find_all_files(
        const fs::path& dir, std::function<bool(const std::string&)> pred);


}  // namespace utils
