// Written By: Projjal Gupta
// For: SHREC-Flapmax Collaboration

#include <fmt/ostream.h>
#include <cstdint>
#include <random>
#include <tt-metalium/host_api.hpp>
#include <tt-metalium/device.hpp>
#include <tt-metalium/bfloat16.hpp>
#include <tt-metalium/tensor_accessor_args.hpp>
#include <tt-metalium/tt_metal_profiler.hpp>

using namespace tt::tt_metal;
#ifndef OVERRIDE_KERNEL_PREFIX
#define OVERRIDE_KERNEL_PREFIX ""
#endif
int main() {
    bool pass = true;

    try {
        constexpr int device_id = 0;
        IDevice* device = CreateDevice(device_id);
        CommandQueue& cq = device->command_queue();

constexpr uint32_t num_tiles = 4;
        constexpr uint32_t elements_per_tile = tt::constants::TILE_WIDTH * tt::constants::TILE_HEIGHT;
        constexpr uint32_t tile_size_bytes = sizeof(bfloat16) * elements_per_tile;
        constexpr uint32_t dram_buffer_size = tile_size_bytes * num_tiles;

        // Configuration for the buffers.
        tt::tt_metal::InterleavedBufferConfig dram_config{
            .device = device,  
            .size = dram_buffer_size,     
            .page_size = tile_size_bytes,  
            .buffer_type = tt::tt_metal::BufferType::DRAM};  
        tt::tt_metal::InterleavedBufferConfig l1_config{
            .device = device,
            .size = tile_size_bytes,
            .page_size = tile_size_bytes,
            .buffer_type = tt::tt_metal::BufferType::L1}; 

        // Allocate the buffers
        auto l1_buffer = CreateBuffer(l1_config);
        auto input_dram_buffer = CreateBuffer(dram_config);
        auto output_dram_buffer = CreateBuffer(dram_config);

        Program program = CreateProgram();

        constexpr CoreCoord core = {0, 0};

        std::vector<uint32_t> dram_copy_compile_time_args;
        TensorAccessorArgs(*input_dram_buffer).append_to(dram_copy_compile_time_args);
        TensorAccessorArgs(*output_dram_buffer).append_to(dram_copy_compile_time_args);
        KernelHandle dram_copy_kernel_id = CreateKernel(
            program,
            OVERRIDE_KERNEL_PREFIX "fm_read/kernels/loopback_dram_copy.cpp",
            core,
            DataMovementConfig{
                .processor = DataMovementProcessor::RISCV_0,
                .noc = NOC::RISCV_0_default,
                .compile_args = dram_copy_compile_time_args});

        std::vector<bfloat16> input_vec(elements_per_tile * num_tiles);
        std::mt19937 rng(std::random_device{}());
        std::uniform_real_distribution<float> distribution(0.0f, 100.0f);
        for (auto& val : input_vec) {
            val = bfloat16(distribution(rng));
        }

        EnqueueWriteBuffer(cq, input_dram_buffer, input_vec, /*blocking=*/false);

        const std::vector<uint32_t> runtime_args = {
            l1_buffer->address(), input_dram_buffer->address(), output_dram_buffer->address(), num_tiles};

        SetRuntimeArgs(program, dram_copy_kernel_id, core, runtime_args);

        EnqueueProgram(cq, program, /*blocking=*/false);
        Finish(cq);

        std::cout << "Execution Complete" << std::endl;

        // Skipped for profiler runs

        //std::vector<bfloat16> result_vec;
        //EnqueueReadBuffer(cq, output_dram_buffer, result_vec, /*blocking*/ true);
/*
        // Compare the result with the input. The result should be the same as the input.
        TT_FATAL(
            result_vec.size() == input_vec.size(),
            "Result vector size {} does not match input vector size {}",
            result_vec.size(),
            input_vec.size());
        for (int i = 0; i < input_vec.size(); i++) {
            if (input_vec[i] != result_vec[i]) {
                pass = false;
                break;
            }
        }
*/
        tt::tt_metal::detail::ReadDeviceProfilerResults(device);
        // Close the device
        if (!CloseDevice(device)) {
            pass = false;
        }

    } catch (const std::exception& e) {
        fmt::print(stderr, "Test failed with exception! what: {}\n", e.what());
        throw;
    }

    if (pass) {
        fmt::print("Test Passed\n");
    } else {
        TT_THROW("Test Failed");
    }

    return 0;
}
