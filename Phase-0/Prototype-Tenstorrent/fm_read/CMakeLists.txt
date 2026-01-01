cmake_minimum_required(VERSION 3.22...3.30)
project(fm_read)

add_executable(fm_read)
target_sources(fm_read PRIVATE read.cpp)

if(NOT TARGET TT::Metalium)
    find_package(TT-Metalium REQUIRED)
endif()
target_link_libraries(fm_read PUBLIC TT::Metalium)
