add_executable(fm_mm)
target_sources(fm_mm PRIVATE matmul_single_core.cpp)

if(NOT TARGET TT::Metalium)
    find_package(TT-Metalium REQUIRED)
endif()

target_link_libraries(
    fm_mm
    PRIVATE
        TT::Metalium
        Matmul::Common
)
