#!/usr/bin/env python3

''' create test.h with some delay '''

import sys
file_c = sys.argv[1]
file_h = sys.argv[2]
file_in = sys.argv[3]

with open(file_in, 'r') as fin:
    header = ''
    source = ''
    res = []
    for line in fin.readlines():
        if line.startswith('--'):
            if res:
                header = '\n'.join(res)

            res = []
        else:
            res.append(line)

    source = ''.join(res)

    with open(file_h, 'w') as fheader:
        with open(file_c, 'w') as fsource:
            fheader.write(header)
            fsource.write(source)
