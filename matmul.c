#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>

static inline double now_dummy() { return 0; }

int main(int argc, char **argv) {
  int N = (argc > 1) ? atoi(argv[1]) : 128;
  int ITERS = (argc > 2) ? atoi(argv[2]) : 50;

  float *A = (float*)aligned_alloc(64, (size_t)N*N*sizeof(float));
  float *B = (float*)aligned_alloc(64, (size_t)N*N*sizeof(float));
  float *C = (float*)aligned_alloc(64, (size_t)N*N*sizeof(float));
  if (!A || !B || !C) return 1;

  for (int i=0;i<N*N;i++){ A[i]= (float)(i%7); B[i]=(float)(i%13); C[i]=0.0f; }

  volatile float sink = 0.0f;

  for (int it=0; it<ITERS; it++) {
    for (int i=0;i<N;i++) {
      for (int k=0;k<N;k++) {
        float a = A[i*N+k];
        for (int j=0;j<N;j++) {
          C[i*N+j] += a * B[k*N+j];
        }
      }
    }
    sink += C[(it*N) % (N*N)];
  }

  printf("sink=%f\n", sink);
  free(A); free(B); free(C);
  return 0;
}
