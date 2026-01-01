Steps to compile and run the programs

1. Clone TT-Metalium and install it into your system
Link: https://github.com/tenstorrent/tt-metal
Install Guide: https://docs.tenstorrent.com/tt-metal/latest/tt-metalium/installing.html

2. Copy all the "fm_" folders into "tt-metal/tt_metal/programming_examples"

3. Copy the CMakeLists.txt file into "tt-metal/tt_metal/programming_examples". We recommend renaming the existing CMakeLists.txt in that folder to CMakeLists_BACKUP.txt to keep a backup of the original version.

4. Navigate out to tt-metal and set the TT_METAL_HOME with following command: (export TT_METAL_HOME=</path/to/tt-metal>)

5. Compile the programs using following command: (./build_metal.sh --build-programming-examples)

6. The compiled program executable should be in build/programming_examples folder. Run the programs using ./build/programming_examples/<exec_name>
NOTE: if you want to profile application then run the program with the the following environment variable: TT_METAL_DEVICE_PROFILER=1

7. The profiler outcome will be saved in ${TT_METAL_HOME}/generated/profiler/.logs/ folder

8. Use looper.py to loop over multiple input data sizes (customizable in python file)



Steps to interpret data

1. Navigate to the folder containing all the profiled outputs generated using looper.py
2. For DRAM related programs, you can extract data by runnning analysis.py (inside fm_loopback, fm_read, fm_write). This will generate a summary_results.csv which can be used to plot performance

3. For MM program, you can extract data by running "Bucketized performance generator.py" which generates a csv file with the bucketized performance.