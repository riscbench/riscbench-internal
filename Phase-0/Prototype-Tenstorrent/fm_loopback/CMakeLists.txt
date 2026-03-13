cmake_minimum_required(VERSION 3.22...3.30)
project(fm_loopback)

add_executable(fm_loopback)
target_sources(fm_loopback PRIVATE loopback.cpp)

if(NOT TARGET TT::Metalium)
    find_package(TT-Metalium REQUIRED)
endif()
target_link_libraries(fm_loopback PUBLIC TT::Metalium)
