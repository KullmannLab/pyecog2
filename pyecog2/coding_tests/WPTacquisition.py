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


class Wait_str():
    def __init__(self,s,n=1):
        self.str0 = s
        self.n = n
        self.str = ' '
        self.counter = 0
        
    def blink(self):
        self.counter += 1
        if self.counter>= self.n:
            self.counter = 0
            if self.str ==' ':
                self.str = self.str0
            else:
                self.str = ' '
            print(self.str, end='\r')


class WPTInterface():
    def __init__(self,
                 device_path = '/dev/serial/by-id/usb-Nordic_Semiconductor_nRF52_Connectivity_E584C0E0113D-if01',
                 prog_path   = '/home/mfpleite/Documents/pc-ble-driver/build/examples/wpt_collector_sd_api_v5'):
        self.prog_path   = [prog_path]
        self.prog_args   = [device_path, 'NRF52']
        
        self.outq        = queue.Queue() # Thread safe queue to comunicate with process
        self.proc = None
        
        self.ready_to_acquire_data = False
        self.is_acquiring          = False
        
    def output_reader(self,proc):
        for line in iter(proc.stdout.readline, b''):
            self.outq.put(line.decode('utf-8'))
        self.outq.put('Terminating output_reader...')
        self.outq.put(b''.decode('utf-8'))
        
    def launch(self):
        if self.proc is not None:
            print('Process already ongoing...')
            return
        
        self.proc = subprocess.Popen(self.prog_path + self.prog_args,
                                     stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT)
        self.output_reader_t = threading.Thread(target = self.output_reader, args=(self.proc,))
        self.output_reader_t.start()
        print('Process initiated')
    
    def print_output(self):
        output = []
        try:
            while not self.outq.empty():
                line = self.outq.get(block=False)
                print(' - outq: {0}'.format(line), end='\r')
                if line[:5]=='Input':
                    self.ready_to_acquire_data = True
                output.append(line)

        except Exception:
            print('ERROR printing output')
        finally:
            return output
    
    def terminate(self):
        if self.proc is None:
            print('Nothing to terminate')
            return
        try:
            self.proc.stdin.write(b'0xff\n') # send exit command 0xff
            self.proc.stdin.flush()
            self.proc.terminate()
        except Exception:
            print('error terminating subprocess')
        # This should terminate the output_reader_t as well
        print('Almost done...')
        time.sleep(.1)
        self.print_output()
        print('All terminated')
        self.proc = None

    def send_command(self, s):
        # check if string is an acceptable input:
        check = (len(string)<=6)
        check *= all(c in string.hexdigits for c in s)
        self.proc.stdin.write(bytes('0x'+s+'00',encoding='utf-8')) # 00 is the code for write command
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
            
    # These DELETE functions are not always being called correctly:
    # Some processes might get lost running in the background!
    def __del__(self):
        print('Trying to clean up gracefully')
        self.terminate()
            
    def __delete__(self):
        print('Trying to clean up gracefully')
        self.terminate()

