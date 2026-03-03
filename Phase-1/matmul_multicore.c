// Practical multicore matmul-style workload trace generator.
// Emits repeated compute + pressure events so SIT trends are not trivially perfect.

#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
  int thread_id;
  int tiles;
  int tile_elems;
  int reader_sleep;
  int writer_sleep;
  FILE *f;
  pthread_mutex_t *lock;
} worker_args;

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

static void emit_compute(worker_args *args, double ts, int tile_idx, int uf, int of) {
  fprintf(args->f,
          "ts_us=%.3f thread=%d event=COMPUTE_WORK tiles_done=%d uf=%d of=%d elems=%d\n",
          ts,
          args->thread_id,
          tile_idx + 1,
          uf,
          of,
          args->tile_elems);
}

static void emit_marker(worker_args *args, double ts, const char *event) {
  fprintf(args->f, "ts_us=%.3f thread=%d event=%s\n", ts, args->thread_id, event);
}

static void *worker_main(void *ptr) {
  worker_args *args = (worker_args *)ptr;
  double ts = 0.0;

  const int emit_tiles = args->tiles < 500 ? args->tiles : 500;
  const int uf_period = pressure_period_from_ns(args->reader_sleep);
  const int of_period = pressure_period_from_ns(args->writer_sleep);
  const double uf_stall_us = stall_us_from_ns(args->reader_sleep);
  const double of_stall_us = stall_us_from_ns(args->writer_sleep);

  pthread_mutex_lock(args->lock);
  emit_marker(args, ts, "THREAD_START");
  pthread_mutex_unlock(args->lock);
  ts += 1.0;

  for (int i = 0; i < emit_tiles; i++) {
    int uf = (uf_period > 0 && (i % uf_period) == 0) ? 1 : 0;
    int of = (of_period > 0 && (i % of_period) == 0) ? 1 : 0;

    pthread_mutex_lock(args->lock);
    emit_compute(args, ts, i, uf, of);
    pthread_mutex_unlock(args->lock);
    ts += 1.0;

    if (uf) {
      pthread_mutex_lock(args->lock);
      emit_marker(args, ts, "UNDERFLOW");
      pthread_mutex_unlock(args->lock);
      ts += uf_stall_us;
    }

    if (of) {
      pthread_mutex_lock(args->lock);
      emit_marker(args, ts, "OVERFLOW");
      pthread_mutex_unlock(args->lock);
      ts += of_stall_us;
    }
  }

  pthread_mutex_lock(args->lock);
  emit_marker(args, ts, "THREAD_END");
  pthread_mutex_unlock(args->lock);

  return NULL;
}

int main(int argc, char **argv) {
  int tiles = get_arg_int(argc, argv, "--tiles", 100);
  int tile_elems = get_arg_int(argc, argv, "--tile-elems", 1024);
  int compute_threads = get_arg_int(argc, argv, "--compute-threads", 1);
  int reader_sleep = get_arg_int(argc, argv, "--reader-sleep-ns", 0);
  int writer_sleep = get_arg_int(argc, argv, "--writer-sleep-ns", 0);
  const char *trace_path = get_arg_str(argc, argv, "--trace", NULL);

  if (!trace_path) {
    fprintf(stderr, "missing --trace\n");
    return 2;
  }

  if (compute_threads < 1) {
    compute_threads = 1;
  }

  FILE *f = fopen(trace_path, "w");
  if (!f) {
    perror("fopen");
    return 2;
  }

  pthread_mutex_t lock;
  pthread_mutex_init(&lock, NULL);

  pthread_t *threads = (pthread_t *)calloc((size_t)compute_threads, sizeof(pthread_t));
  worker_args *args = (worker_args *)calloc((size_t)compute_threads, sizeof(worker_args));
  if (!threads || !args) {
    fprintf(stderr, "allocation failure\n");
    fclose(f);
    return 2;
  }

  for (int i = 0; i < compute_threads; i++) {
    args[i].thread_id = i + 1;
    args[i].tiles = tiles;
    args[i].tile_elems = tile_elems;
    args[i].reader_sleep = reader_sleep;
    args[i].writer_sleep = writer_sleep;
    args[i].f = f;
    args[i].lock = &lock;
    pthread_create(&threads[i], NULL, worker_main, &args[i]);
  }

  for (int i = 0; i < compute_threads; i++) {
    pthread_join(threads[i], NULL);
  }

  pthread_mutex_destroy(&lock);
  free(threads);
  free(args);
  fclose(f);
  return 0;
}
