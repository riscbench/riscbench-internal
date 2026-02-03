// wl_matmul.cpp
// Build: g++ -O2 -std=c++17 wl_matmul.cpp -o wl_matmul
// Run:   ./wl_matmul --ms 2000 --matN 128

#include <chrono>
#include <iostream>
#include <random>
#include <string>
#include <vector>

using Clock = std::chrono::steady_clock;

static int get_arg(int argc, char** argv, const std::string& key, int def) {
  for (int i = 1; i + 1 < argc; i++) if (argv[i] == key) return std::stoi(argv[i + 1]);
  return def;
}

int main(int argc, char** argv) {
  int ms = get_arg(argc, argv, "--ms", 2000);
  int N  = get_arg(argc, argv, "--matN", 128);
  if (N <= 0) N = 128;

  std::vector<float> A((size_t)N*N), B((size_t)N*N), C((size_t)N*N, 0.0f);

  std::mt19937 rng(1);
  std::uniform_real_distribution<float> dist(0.0f, 1.0f);
  for (auto& x : A) x = dist(rng);
  for (auto& x : B) x = dist(rng);

  auto end_t = Clock::now() + std::chrono::milliseconds(ms);

  while (Clock::now() < end_t) {
    for (int i = 0; i < N; i++) {
      for (int k = 0; k < N; k++) {
        float aik = A[i*N + k];
        for (int j = 0; j < N; j++) {
          C[i*N + j] += aik * B[k*N + j];
        }
      }
    }
  }

  if (C[0] == 123456.0f) std::cerr << "";
  return 0;
}
