import json
from PyQt5 import QtCore
from PyQt5.QtCore import QObject
import numpy as np
from collections import OrderedDict
from h5loader import H5File
import glob, os
from datetime import datetime


def create_metafile_from_h5(file):
    assert file.endswith('.h5')
    h5_file = H5File(file)
    fs_dict = eval(h5_file.attributes['fs_dict'])
    fs = fs_dict[int(h5_file.attributes['t_ids'][0])]
    for tid in h5_file.attributes['t_ids']:
        assert fs == int(fs_dict[tid]) # Check all tids have the same sampling rate
    metadata = OrderedDict(fs=fs,
                           no_channels=len(h5_file.attributes['t_ids']),
                           data_format='h5',
                           volts_per_bit=0,
                           transmitter_id=str(h5_file.attributes['t_ids']),
                           start_timestamp_unix=int(file.split('/')[-1].split('_')[0][1:]),
                           duration = 3600, # assume all h5 files have 1hr duration
                           channel_labels= [str(label) for label in h5_file.attributes['t_ids']],
                           experiment_metadata_str='')
    metafile = file[:-2] + 'meta'
    with open(metafile, 'w') as json_file:
        json.dump(metadata, json_file, indent=2, sort_keys=True)


class Animal():
    def __init__(self,id=None,eeg_folder=None, video_folder = None, dict={}):
        if dict != {}:
            self.__dict__ = dict
            return

        for file in glob.glob(eeg_folder + '/*.h5'):
            if os.path.isfile(file[:-2] + 'meta'):
                print(file[:-2] + 'meta already exists')
                continue
            create_metafile_from_h5(file)

        if eeg_folder is not None:
            self.eeg_files = glob.glob(eeg_folder + '/*.meta')
            self.annotation_files = glob.glob(eeg_folder + '/*.anno')
            self.eeg_init_time = [json.load(file)['start_timestamp_unix'] for file in map(open,self.eeg_files)]
            self.eeg_duration  = [json.load(file)['duration'] for file in map(open,self.eeg_files)]
        else:
            self.eeg_files = []
            self.annotation_files = []
            self.eeg_init_time = []
            self.eeg_duration = []

        if video_folder is not None:
            self.video_files     = glob.glob(video_folder + '/*.mp4')
            self.video_init_time = [
                datetime(*map(int,[fname[-18:-14],fname[-14:-12],fname[-12:-10],fname[-10:-8],fname[-8:-6],fname[-6:-4]])).timestamp()
                for fname in self.video_files]
            self.video_duration = [15*60 for file in self.video_files] # this should be replaced in the future to account flexible video durations
        else:
            self.video_files = []
            self.video_init_time = []
            self.video_duration = []

        if id is None and self.eeg_files:
            metadata = json.load(open(self.eeg_files[0]))
            self.id = metadata['transmitter_id']
        else:
            self.id = id


class Project():
    def __init__(self,eeg_data_folder=None,video_data_folder=None,title='New Project', dict={}):

        self.animal_list = []
        self.eeg_root_folder = eeg_data_folder
        self.video_root_folder = video_data_folder
        self.title = title

    def save_to_json(self,fname):
        dict = self.__dict__.copy()
        dict['animal_list'] = [animal.__dict__ for animal in self.animal_list]  # make animals into dicts
        json.dump(dict, open(fname,'w'),indent=4)

    def load_from_json(self, fname):
        dict = json.load(open(fname))
        dict['animal_list'] = [Animal(dict=animal) for animal in dict['animal_list']]  # make dicts into animals
        self.__dict__ = dict

    def get_file(self,animal_id,time):
        for a,animal in enumerate(self.animal_list):
            if animal.id == animal_id:
                for i,file in enumerate(animal.eeg_files):
                    if animal.eeg_init_time[i] >= time and animal.eeg_init_time[i] + animal.eeg_duration[i] <= time:
                        return a, i, file  # return animal and file indices and file path
                return None  # return if found animal but not file
        return None   # return if animal not found