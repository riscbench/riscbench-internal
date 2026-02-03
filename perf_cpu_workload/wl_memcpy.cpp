// wl_memcpy.cpp
// Build: g++ -O2 -std=c++17 wl_memcpy.cpp -o wl_memcpy
// Run:   ./wl_memcpy --ms 2000 --size-mb 256

#include <chrono>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <string>
#include <vector>

using Clock = std::chrono::steady_clock;

static long get_arg(int argc, char** argv, const std::string& key, long def) {
  for (int i = 1; i + 1 < argc; i++) if (argv[i] == key) return std::stol(argv[i + 1]);
  return def;
}

int main(int argc, char** argv) {
  long ms      = get_arg(argc, argv, "--ms", 2000);
  long size_mb = get_arg(argc, argv, "--size-mb", 256);
  size_t bytes = (size_t)size_mb * 1024ULL * 1024ULL;

  std::vector<uint8_t> src(bytes, 1);
  std::vector<uint8_t> dst(bytes, 0);

  auto end_t = Clock::now() + std::chrono::milliseconds(ms);

  while (Clock::now() < end_t) {
    std::memcpy(dst.data(), src.data(), bytes);
  }

  // keep side-effect
  if (dst[0] == 0x42) std::cerr << "";
  return 0;
}
