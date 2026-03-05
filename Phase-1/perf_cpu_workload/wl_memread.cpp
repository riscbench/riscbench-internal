// wl_memread.cpp
// Build: g++ -O2 -std=c++17 wl_memread.cpp -o wl_memread
// Run:   ./wl_memread --ms 2000 --size-mb 256 --stride 64

#include <chrono>
#include <cstdint>
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
  long stride  = get_arg(argc, argv, "--stride", 64);

  if (stride <= 0) stride = 64;
  size_t bytes = (size_t)size_mb * 1024ULL * 1024ULL;

  std::vector<uint8_t> buf(bytes, 1);
  auto end_t = Clock::now() + std::chrono::milliseconds(ms);

  volatile uint64_t sink = 0;
  while (Clock::now() < end_t) {
    for (size_t i = 0; i < bytes; i += (size_t)stride) sink += buf[i];
  }

  if (sink == 0xdeadbeefULL) std::cerr << "";
  return 0;
}
