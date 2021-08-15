#!/bin/python3

import argparse
import pathlib
import subprocess
import time
import random
import pprint
import threading
import csv
from multiprocessing.dummy import Pool

parser = argparse.ArgumentParser('ConfigureTestRun', allow_abbrev=True)
parser.add_argument('--program', type=pathlib.Path, nargs='+', required=True, help='Specify the path to the program[s] to test')
parser.add_argument('--output' , type=pathlib.Path, nargs=1, required=False, default='out.txt', help='Where to write the results')
parser.add_argument('--data-output' , type=pathlib.Path, nargs=1, required=False, default='data-out.txt', help='Where to write the selected test data')

group = parser.add_argument_group('Input data handling')
group.add_argument('--data' , type=pathlib.Path, default='.', help='Where the test data lives')
group.add_argument('--filetype' , type=str, nargs='+', help='What file types to allow for test data')
group.add_argument('--limit-data' , type=int, help='How many files from the data directory to use')
group.add_argument('--data-file', type=pathlib.Path, help='Path to file where each line is a path to an SMT2 file')

group = parser.add_argument_group('Execution options')
group.add_argument('-j', type=int, required=False, default=1, help='how many jobs to execute in parallel')
group.add_argument('-n', type=int, required=False, default=1, help='how many runs to execute')
group.add_argument('--timeout', type=int, required=False, default=600, help='seconds before process is killed')
# group.add_argument('--parallel-repeats', type=bool, required=False, default=600, help='seconds before ')



write_lock = threading.Lock()

def test_program(program, data_path, csv_writer, csv_file, timeout):
    data = data_path.resolve()

    try:
        t1 = time.perf_counter()
        result = subprocess.run([program, data], timeout=timeout, capture_output=True)
        t2 = time.perf_counter()
        with write_lock:
            csv_writer.writerow([program, data, result.stdout.decode('ascii').strip(), t2 - t1])
            csv_file.flush()
    except subprocess.TimeoutExpired as r:
        with write_lock:
            csv_writer.writerow([program, data, "unknown", "timeout"])
            csv_file.flush()


def run_test(program, csv_writer, csv_file, timeout):
    return (lambda data: test_program(program, data, csv_writer, csv_file, timeout))



def main():
    args = parser.parse_args()

    if args.data_file:
        data_file_list = [pathlib.Path(s) for s in args.data_file.open().read().splitlines()]
        data_file_list = [p for p in data_file_list if p.exists()]
    else:
        # Choose Dataset
        data_file_list = [p for p in args.data.rglob('*') if p.is_file()]

    #
    ## Filter by filetype
    #
    if args.filetype:
        data_filetypes = set(args.filetype)
        data_files = [path for path in data_file_list if path.suffix in data_filetypes]
    else:
        data_files = data_file_list

    #
    ## Limit the number of input files
    #
    data_files_sample = data_files[:]
    if args.limit_data and args.limit_data > len(data_files):
        data_files_sample = random.sample(data_files, args.limit_data)

    #
    ## Save the selected data for reproducability
    #
    with open(args.data_output, 'w') as f:
        for file in data_files_sample:
            f.write(str(file.resolve()) + '\n')

    #
    ## run!
    #
    pool = Pool(args.j)
    with open(args.output, 'w') as f:
        csv_writer = csv.writer(f, delimiter=',', quotechar='\'', quoting=csv.QUOTE_MINIMAL);
        for _ in range(args.n):
            for program in args.program:
                command = run_test(program, csv_writer, f, args.timeout)
                pool.map(command, data_files_sample)


if __name__ == '__main__':
    main()
