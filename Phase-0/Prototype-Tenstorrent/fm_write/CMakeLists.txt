cmake_minimum_required(VERSION 3.22...3.30)
project(fm_write)

add_executable(fm_write)
target_sources(fm_write PRIVATE write.cpp)

if(NOT TARGET TT::Metalium)
    find_package(TT-Metalium REQUIRED)
endif()
target_link_libraries(fm_write PUBLIC TT::Metalium)
