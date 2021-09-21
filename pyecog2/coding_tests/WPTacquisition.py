#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Apr  2 16:33:07 2020

@author: mfpleite
"""
import queue
import subprocess
import time
import threading
import string
import os
from collections import OrderedDict
import json


# import urllib.request

class Wait_str():
    def __init__(self, s, n=1):
        self.str0 = s
        self.n = n
        self.str = ' '
        self.counter = 0

    def blink(self):
        self.counter += 1
        if self.counter >= self.n:
            self.counter = 0
            if self.str == ' ':
                self.str = self.str0
            else:
                self.str = ' '
            print(self.str, end='\r')


class WPTInterface():
    def __init__(self,
                 device_path='/dev/serial/by-id/usb-Nordic_Semiconductor_nRF52_Connectivity_E584C0E0113D-if01',
                 prog_path='/home/mfpleite/Documents/pc-ble-driver/build/examples/wpt_collector_sd_api_v6'):
        self.prog_path = [prog_path]
        data_dir = '/home/mfpleite/Documents/WPTPythonWrappers/test_data/'
        if not os.path.exists(data_dir):
            os.mkdir(data_dir)
        self.prog_args = [device_path, data_dir]

        self.outq = queue.Queue()  # Thread safe queue to comunicate with process
        self.proc = None

        self.ready_to_acquire_data = False
        self.is_acquiring = False

    def output_reader(self, proc):
        for line in iter(proc.stdout.readline, b''):
            self.outq.put(line.decode('utf-8'))
        self.outq.put('Terminating output_reader...\n')
        self.outq.put(b''.decode('utf-8'))

    def launch(self):
        if self.proc is not None:
            print('Process already running...')
            return

        self.proc = subprocess.Popen(self.prog_path + self.prog_args,
                                     stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT)
        self.output_reader_t = threading.Thread(target=self.output_reader, args=(self.proc,))
        self.output_reader_t.start()
        print('Process initiated')

    def print_output(self):
        output = []
        try:
            while not self.outq.empty():
                line = self.outq.get(block=False)
                print(' - outq: {0}'.format(line), end='\r')
                if line[:5] == 'Input':
                    self.ready_to_acquire_data = True
                if line[:7] == 'NEWFILE':
                    fname = ':'.join(line.split(':')[1:])
                    self.generate_metafile(fname.strip(' \n'))

                output.append(line)

        except Exception as e:
            print('ERROR printing output:')
            print(e)
        finally:
            return output

    def terminate(self):
        if self.proc is None:
            print('Nothing to terminate')
            return
        try:
            self.proc.stdin.write(b'0xff\n')  # send exit command 0xff
            self.proc.stdin.flush()
            time.sleep(.1)
            self.proc.terminate()
        except:
            print('error terminating subprocess')
        # This should terminate the output_reader_t as well
        time.sleep(.1)
        self.print_output()
        time.sleep(.1)
        print('All terminated')
        self.proc = None

    def send_command(self, s):
        # check if string is an acceptable input:
        check = (len(string) <= 6)
        check *= all(c in string.hexdigits for c in s)
        self.proc.stdin.write(bytes('0x' + s + '00', encoding='utf-8'))  # 00 is the code for write command
        self.proc.stdin.flush()

    def toggle_acquisition(self):
        if self.ready_to_acquire_data:
            self.proc.stdin.write(b'0x01\n')
            self.proc.stdin.flush()
            if self.is_acquiring:
                print('Stopping acquisition...')
            else:
                print('Acquiring data...')
            self.is_acquiring = not self.is_acquiring
        else:
            print('Connection is not ready for acquisition...')

    def generate_metafile(self, fname):
        bin_fname = fname.split(os.path.sep)[-1]
        meta_fname = fname[:-3] + 'meta'
        unix_ts = int(bin_fname[1:-4])
        if bin_fname[0] == 'E':
            metadata = OrderedDict(binaryfilename=bin_fname,
                                   fs=256,
                                   no_channels=8,
                                   duration=3600,
                                   data_format='>i4',
                                   volts_per_bit=2.5 / 6 / 2 ** 31,
                                   transmitter_id='001',
                                   start_timestamp_unix=unix_ts,
                                   channel_labels=['channel_' + str(i) for i in range(8)],
                                   experiment_metadata_str='Untitled Experiment')
        elif bin_fname[0] == 'M':
            metadata = OrderedDict(binaryfilename=bin_fname,
                                   fs=20,
                                   no_channels=9,
                                   duration=3600,
                                   data_format='>i1',
                                   volts_per_bit=1,
                                   transmitter_id='001',
                                   start_timestamp_unix=unix_ts,
                                   channel_labels=['ACC_X', 'ACC_Y', 'ACC_Z', 'GYR_X', 'GYR_Y', 'GYR_Z', 'MAG_X',
                                                   'MAG_Y', 'MAG_Z', ],
                                   experiment_metadata_str='Untitled Experiment')
        else:
            print('Unrecognized bin filename format')
            return

        print('Generating metafile:', meta_fname)
        with open(meta_fname, 'w+') as json_file:
            json.dump(metadata, json_file, indent=2, sort_keys=True)

    # These DELETE functions are not always being called correctly:
    # Some processes might get lost running in the background!
    def __del__(self):
        print('Trying to clean up gracefully')
        self.terminate()

    def __delete__(self):
        print('Trying to clean up gracefully')
        self.terminate()



