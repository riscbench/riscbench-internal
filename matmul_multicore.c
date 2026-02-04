// Minimal multicore matmul workload that emits CPU adapter trace events.
// This is a lightweight trace generator, not a performance benchmark.

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

static void emit_event(worker_args *args, double ts, const char *event, int tile) {
  if (tile >= 0) {
    fprintf(args->f, "ts_us=%.3f thread=%d event=%s tile=%d elems=%d tiles_done=%d\n",
            ts, args->thread_id, event, tile, args->tile_elems, tile + 1);
  } else {
    fprintf(args->f, "ts_us=%.3f thread=%d event=%s\n", ts, args->thread_id, event);
  }
}

static void *worker_main(void *ptr) {
  worker_args *args = (worker_args *)ptr;
  double ts = 0.0;
  double step_us = (double)args->tile_elems / 64.0;
  if (step_us < 1.0) {
    step_us = 1.0;
  }

  pthread_mutex_lock(args->lock);
  emit_event(args, ts, "THREAD_START", -1);
  pthread_mutex_unlock(args->lock);
  ts += 1.0;

  int tiles_per_thread = args->tiles;
  if (tiles_per_thread < 1) {
    tiles_per_thread = 1;
  }
  int emit_tiles = tiles_per_thread < 500 ? tiles_per_thread : 500;
  for (int i = 0; i < emit_tiles; i++) {
    pthread_mutex_lock(args->lock);
    emit_event(args, ts, "COMPUTE_WORK", i);
    pthread_mutex_unlock(args->lock);
    ts += step_us;
  }

  if (args->reader_sleep > 0) {
    pthread_mutex_lock(args->lock);
    emit_event(args, ts, "UNDERFLOW", -1);
    pthread_mutex_unlock(args->lock);
    ts += 1.0;
  }

  if (args->writer_sleep > 0) {
    pthread_mutex_lock(args->lock);
    emit_event(args, ts, "OVERFLOW", -1);
    pthread_mutex_unlock(args->lock);
    ts += 1.0;
  }

  pthread_mutex_lock(args->lock);
  emit_event(args, ts, "THREAD_END", -1);
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

  int tiles_per_thread = tiles / compute_threads;
  if (tiles_per_thread < 1) {
    tiles_per_thread = 1;
  }

  for (int i = 0; i < compute_threads; i++) {
    args[i].thread_id = i + 1;
    args[i].tiles = tiles_per_thread;
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
