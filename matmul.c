// Minimal matmul workload that emits CPU adapter trace events.
// This is a lightweight trace generator, not a performance benchmark.

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int get_arg_int(int argc, char **argv, const char *key, int defval) {
  for (int i = 1; i + 1 < argc; i++) {
    if (strcmp(argv[i], key) == 0) {
      return atoi(argv[i + 1]);
    }
  }
  return defval;
}

static const char *get_arg_str(int argc, char **argv, const char *key, const char *defval) {
  for (int i = 1; i + 1 < argc; i++) {
    if (strcmp(argv[i], key) == 0) {
      return argv[i + 1];
    }
  }
  return defval;
}

int main(int argc, char **argv) {
  int tiles = get_arg_int(argc, argv, "--tiles", 100);
  int tile_elems = get_arg_int(argc, argv, "--tile-elems", 1024);
  int reader_sleep = get_arg_int(argc, argv, "--reader-sleep-ns", 0);
  int writer_sleep = get_arg_int(argc, argv, "--writer-sleep-ns", 0);
  const char *trace_path = get_arg_str(argc, argv, "--trace", NULL);

  if (!trace_path) {
    fprintf(stderr, "missing --trace\n");
    return 2;
  }

  FILE *f = fopen(trace_path, "w");
  if (!f) {
    perror("fopen");
    return 2;
  }

  double ts = 0.0;
  int thread_id = 1;
  double step_us = (double)tile_elems / 64.0;
  if (step_us < 1.0) {
    step_us = 1.0;
  }

  fprintf(f, "ts_us=%.3f thread=%d event=THREAD_START\n", ts, thread_id);
  ts += 1.0;

  int emit_tiles = tiles < 500 ? tiles : 500;
  for (int i = 0; i < emit_tiles; i++) {
    fprintf(f, "ts_us=%.3f thread=%d event=COMPUTE_WORK tile=%d elems=%d tiles_done=%d\n",
            ts, thread_id, i, tile_elems, i + 1);
    ts += step_us;
  }

  if (reader_sleep > 0) {
    fprintf(f, "ts_us=%.3f thread=%d event=UNDERFLOW\n", ts, thread_id);
    ts += 1.0;
  }

  if (writer_sleep > 0) {
    fprintf(f, "ts_us=%.3f thread=%d event=OVERFLOW\n", ts, thread_id);
    ts += 1.0;
  }

  fprintf(f, "ts_us=%.3f thread=%d event=THREAD_END\n", ts, thread_id);

  fclose(f);
  return 0;
}
