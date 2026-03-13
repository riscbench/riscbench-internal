# All programming example targets should link tt_stl
link_libraries(TT::STL)

add_compile_definitions(OVERRIDE_KERNEL_PREFIX="tt_metal/programming_examples/")
include(${PROJECT_SOURCE_DIR}/cmake/helper_functions.cmake)

set(CMAKE_RUNTIME_OUTPUT_DIRECTORY "${PROJECT_BINARY_DIR}/programming_examples")
add_subdirectory(${CMAKE_CURRENT_SOURCE_DIR}/fm_loopback)
add_subdirectory(${CMAKE_CURRENT_SOURCE_DIR}/fm_mm)
add_subdirectory(${CMAKE_CURRENT_SOURCE_DIR}/fm_read)
add_subdirectory(${CMAKE_CURRENT_SOURCE_DIR}/fm_write)

add_custom_target(
    programming_examples
    DEPENDS
        profiler_examples
        ${PROGRAMMING_EXAMPLES_TEST_TARGETS}
)

install(
    DIRECTORY
        fm_loopback
        fm_write
	fm_read
        fm_mm
    # DESTINATION ${CMAKE_INSTALL_DOCDIR}/examples
    # FIXME(afuller): Something funky is happening when installing files into
    # /usr/share/doc on a default Docker image. Speculation: some dependency for
    # magic doc handling is missing. For now keep it out of 'doc'.
    DESTINATION "${CMAKE_INSTALL_DATADIR}/tt-metalium/examples"
    COMPONENT metalium-examples
    REGEX
    "/kernels/"
        EXCLUDE
)

install(
    DIRECTORY
        fm_loopback
        fm_write
	fm_read
        fm_mm
    DESTINATION "${CMAKE_INSTALL_DATADIR}/tenstorrent/kernels"
    COMPONENT metalium-examples
    FILES_MATCHING
    REGEX
    "/kernels/"
)
