# RISCVBench Workbook Reference Metrics

Direct TT SIT vs workbook throughput comparison is intentionally omitted.

- Workbook values are throughput references in `GB/s`, `GFLOPS`, or `TFLOPS`.
- TT `sit_median` in the current TT pipeline is a normalized activity-style metric when `work_done` is absent, not a throughput metric.
- Because the units and semantics differ, no direct validation chart is emitted here.

## Reference Metrics

- `dram_read_peak_gbps`: 2 = 4.865 GB/s (sheet/source: Independent READ Test (DRAM BW))
- `dram_write_peak_gbps`: 2 = 4.536 GB/s (sheet/source: Independent WRITE Test (DRAM BW))
- `loopback_peak_gbps`: 1024000 = 4.584 GB/s (sheet/source: Loopback Test (DRAM BW))
- `teraflops_blockfp8`: TeraFLOPS (BLOCKFP8) = 262.000 TFLOPS (sheet/source: Aggregate Throughput)
- `teraflops_fp16`: TeraFLOPS (FP16) = 131.000 TFLOPS (sheet/source: Aggregate Throughput)
- `teraflops_fp8`: TeraFLOPS (FP8) = 466.000 TFLOPS (sheet/source: Aggregate Throughput)
- `64x64_flops_peak_gflops`: 64x64 FLOPS = 1443.129 GFLOPS (sheet/source: 64x64 FLOPS)
- `128x128_flops_peak_gflops`: 128x128 FLOPS = 748.162 GFLOPS (sheet/source: 128x128 FLOPS)
- `256x256_flops_peak_gflops`: 256x256 FLOPS = 347.237 GFLOPS (sheet/source: 256x256 FLOPS)
- `512x512_flops_peak_gflops`: 512x512 FLOPS = 269.237 GFLOPS (sheet/source: 512x512 FLOPS)
- `640_peak_gflops`: 640 = 268.955 GFLOPS (sheet/source: 640)
- `768_peak_gflops`: 768 = 263.561 GFLOPS (sheet/source: 768)
- `1024_peak_gflops`: 1024 = 266.262 GFLOPS (sheet/source: 1024)
