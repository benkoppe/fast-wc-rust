#include "utils.hpp"

#include <list>

std::vector<fs::path> utils::find_all_files(
        const fs::path& dir, std::function<bool(const std::string&)> pred) {
    std::list<fs::path> files_to_sweep;
    // iterate recursively to find all files that satisfy pred
    for(auto& entry : fs::recursive_directory_iterator(dir)) {
        if(entry.is_regular_file()) {
            fs::path cur_file = entry.path();
            std::string type(cur_file.extension());
            if(pred(type)) {
	        files_to_sweep.push_back(std::move(cur_file));
            }
        }
    }
    return std::vector<fs::path>(std::make_move_iterator(files_to_sweep.begin()),
				 std::make_move_iterator(files_to_sweep.end()));
}
