// Practical single-core matmul-style workload trace generator.
// Emits repeated compute + pressure events so SIT reflects queue pressure.

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

static int pressure_period_from_ns(int sleep_ns) {
  if (sleep_ns <= 0) {
    return 0;
  }
  if (sleep_ns >= 20000) {
    return 3;
  }
  if (sleep_ns >= 10000) {
    return 5;
  }
  if (sleep_ns >= 5000) {
    return 7;
  }
  if (sleep_ns >= 2000) {
    return 10;
  }
  return 16;
}

static double stall_us_from_ns(int sleep_ns) {
  if (sleep_ns <= 0) {
    return 0.0;
  }
  double us = ((double)sleep_ns) / 1000.0;
  if (us < 1.0) {
    us = 1.0;
  }
  return us;
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
  int emit_tiles = tiles < 500 ? tiles : 500;
  int uf_period = pressure_period_from_ns(reader_sleep);
  int of_period = pressure_period_from_ns(writer_sleep);
  double uf_stall_us = stall_us_from_ns(reader_sleep);
  double of_stall_us = stall_us_from_ns(writer_sleep);

  fprintf(f, "ts_us=%.3f thread=%d event=THREAD_START\n", ts, thread_id);
  ts += 1.0;

  for (int i = 0; i < emit_tiles; i++) {
    int uf = (uf_period > 0 && (i % uf_period) == 0) ? 1 : 0;
    int of = (of_period > 0 && (i % of_period) == 0) ? 1 : 0;

    fprintf(f,
            "ts_us=%.3f thread=%d event=COMPUTE_WORK tiles_done=%d uf=%d of=%d elems=%d\n",
            ts,
            thread_id,
            i + 1,
            uf,
            of,
            tile_elems);
    ts += 1.0;

    if (uf) {
      fprintf(f, "ts_us=%.3f thread=%d event=UNDERFLOW\n", ts, thread_id);
      ts += uf_stall_us;
    }

    if (of) {
      fprintf(f, "ts_us=%.3f thread=%d event=OVERFLOW\n", ts, thread_id);
      ts += of_stall_us;
    }
  }

  fprintf(f, "ts_us=%.3f thread=%d event=THREAD_END\n", ts, thread_id);

  fclose(f);
  return 0;
}
