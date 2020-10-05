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
        assert fs == int(fs_dict[tid])  # Check all tids have the same sampling rate
    metadata = OrderedDict(fs=fs,
                           no_channels=len(h5_file.attributes['t_ids']),
                           data_format='h5',
                           volts_per_bit=0,
                           transmitter_id=str(h5_file.attributes['t_ids']),
                           start_timestamp_unix=int(file.split('/')[-1].split('_')[0][1:]),
                           duration=3600,  # assume all h5 files have 1hr duration
                           channel_labels=[str(label) for label in h5_file.attributes['t_ids']],
                           experiment_metadata_str='')
    metafile = file[:-2] + 'meta'
    with open(metafile, 'w') as json_file:
        json.dump(metadata, json_file, indent=2, sort_keys=True)


class Animal():
    def __init__(self, id=None, eeg_folder=None, video_folder=None, dict={}):
        if dict != {}:
            self.__dict__ = dict
            return

        if eeg_folder is not None:
            for file in glob.glob(eeg_folder + '/*.h5'):
                if os.path.isfile(file[:-2] + 'meta'):
                    print(file[:-2] + 'meta already exists')
                    continue
                create_metafile_from_h5(file)
            self.eeg_files = glob.glob(eeg_folder + '/*.meta')
            self.annotation_files = glob.glob(eeg_folder + '/*.anno')
            self.eeg_init_time = [json.load(file)['start_timestamp_unix'] for file in map(open, self.eeg_files)]
            self.eeg_duration = [json.load(file)['duration'] for file in map(open, self.eeg_files)]
        else:
            self.eeg_files = []
            self.annotation_files = []
            self.eeg_init_time = []
            self.eeg_duration = []

        if video_folder is not None:
            self.video_files = glob.glob(video_folder + '/*.mp4')
            self.video_init_time = [
                datetime(*map(int, [fname[-18:-14], fname[-14:-12], fname[-12:-10], fname[-10:-8], fname[-8:-6],
                                    fname[-6:-4]])).timestamp()
                for fname in self.video_files]
            self.video_duration = [15 * 60 for file in
                                   self.video_files]  # this should be replaced in the future to account flexible video durations
        else:
            self.video_files = []
            self.video_init_time = []
            self.video_duration = []

        if id is None and self.eeg_files:
            metadata = json.load(open(self.eeg_files[0]))
            self.id = metadata['transmitter_id']
        else:
            self.id = id


class file_buffer():  # Consider translating this to cython
    def __init__(self):
        self.files = []
        self.range = [np.Inf, -np.Inf]
        self.data = []
        self.data_ranges = []
        self.metadata = []

    def add_file_to_buffer(self, fname):
        if fname in self.files:  # skip if file is already buffered
            return
        else:
            self.files.append(fname)

        with open(fname, 'r') as json_file:
            metadata = json.load(json_file)
        self.metadata.append(metadata)

        if metadata['data_format'] == 'h5':
            h5file = H5File(fname[:-4] + 'h5')
            channels = []
            for tid in h5file.attributes['t_ids']:
                channels.append(h5file[tid]['data'])
            arr = np.vstack(channels).T
            self.data.append(arr)

        else:  # it is a bin file and can be mememaped
            m = np.memmap(fname[:4] + 'bin', mode='r+', shape=(-1, metadata['no_channels']))
            self.data.append(m)

        trange = [metadata['start_timestamp_unix'], metadata['start_timestamp_unix'] + metadata['duration']]
        self.data_ranges.append(trange)

        if self.range[0] > trange[0]:  # buffering earlier file
            self.range[0] = trange[0]
            if len(self.data) > 3:  # buffer 3 files - consider having this as a variable...
                i = max(range(len(self.data)),
                        key=lambda j: self.data_ranges[j][0])  # get the index of the latest starting buffered file
                del(self.files[i])
                del(self.data[i])
                del(self.data_ranges[i])
                del(self.metadata[i])
                self.range = [min([r[0] for r in self.data_ranges]), max([r[1] for r in self.data_ranges])]

        if self.range[1] < trange[1]:  # buffering later file
            self.range[1] = trange[1]
            if len(self.data) > 3:  # buffer 3 files - consider having this as a variable...
                i = min(range(len(self.data)),
                        key=lambda j: self.data_ranges[j][0])  # get the index of the earliest starting buffered file
                del(self.files[i])
                del(self.data[i])
                del(self.data_ranges[i])
                del(self.metadata[i])
                self.range = [min([r[0] for r in self.data_ranges]), max([r[1] for r in self.data_ranges])]

    def get_data_from_range(self, trange, channel=None, n_envelope=None):
        def clip(x, a, b):
            return min(max(int(x), a), b)

        #  Find sample ranges from data_ranges:
        sample_ranges = []
        print('range:',self.range)
        print('data ranges:',self.data_ranges)
        for i, ranges in enumerate(self.data_ranges):
            print('metadata',i,':',self.metadata[i])
            fs = self.metadata[i]['fs']
            print(((trange[0] - ranges[0]) * fs, 0, len(self.data[i])))
            sample_ranges.append([clip((trange[0] - ranges[0]) * fs, 0, len(self.data[i])),
                                  clip((trange[1] - ranges[0]) * fs, 0, len(self.data[i]))])

        total_sample_range = max(sum([s[1] - s[0] for s in sample_ranges]),1)
        if n_envelope is None:
            n_envelope = total_sample_range
        file_envlopes = [int(n_envelope * (s[1] - s[0]) / total_sample_range) +1  for s in
                             sample_ranges]  # distribute samples between files

        enveloped_data = []
        enveloped_time = []
        # print('sample ranges: ', sample_ranges)
        # print('data ranges: ', self.data_ranges)
        # print('data: ', len(self.data))
        for i, data in enumerate(self.data):
            start = sample_ranges[i][0]
            stop = sample_ranges[i][1]
            fs = self.metadata[i]['fs']

            # Decide by how much we should downsample
            ds = int((stop - start) / file_envlopes[i]) + 1
            if ds == 1:
                # Small enough to display with no intervention.
                if channel is None:
                    enveloped_data.append(data[start:stop, :])
                else:
                    enveloped_data.append(data[start:stop, channel].reshape(-1,1))

            else:
                # Here convert data into a down-sampled array suitable for visualizing.
                # Must do this piecewise to limit memory usage.
                samples = (1 + (stop - start) // ds)
                # print('grabbing',samples,'samples from buffred file',i)
                visible_data = np.zeros((samples * 2,1), dtype=data.dtype)
                sourcePtr = start
                targetPtr = 0
                try:
                    # read data in chunks of ~1M samples
                    chunkSize = int((1e6 // ds) * ds)
                    while sourcePtr < stop - 1:
                        chunk_data = data[sourcePtr:min(stop, sourcePtr + chunkSize), channel]
                        sourcePtr += chunkSize
                        # reshape chunk to be integer multiple of ds
                        chunk_data = chunk_data[:(len(chunk_data) // ds) * ds].reshape(len(chunk_data) // ds, ds)
                        mx_inds = np.argmax(chunk_data, axis=1)
                        mi_inds = np.argmin(chunk_data, axis=1)
                        row_inds = np.arange(chunk_data.shape[0])
                        chunkMax_x = chunk_data[row_inds, mx_inds].reshape(len(chunk_data),1)
                        chunkMin_x = chunk_data[row_inds, mi_inds].reshape(len(chunk_data),1)
                        visible_data[targetPtr:targetPtr + chunk_data.shape[0] * 2:2] = chunkMin_x
                        visible_data[1 + targetPtr:1 + targetPtr + chunk_data.shape[0] * 2:2] = chunkMax_x
                        targetPtr += chunk_data.shape[0] * 2

                    enveloped_data.append(visible_data[:targetPtr,:].reshape((-1,1)))

                except:
                    print('ERROR in downsampling')
                    raise
                    # throw_error()
                    # return 0

            enveloped_time.append(np.linspace(start/fs + self.data_ranges[i][0], stop/fs + self.data_ranges[i][0],
                                               len(enveloped_data[-1])).reshape(-1,1))
            if len(enveloped_time[-1])==0:
                del(enveloped_time[-1])
                del(enveloped_data[-1])
            # print('env data shapes')
            # print([data.shape for data in enveloped_data])
            # print([data.shape for data in enveloped_time])
        # sort vectors with enveloped_time:
        start_times = [(t[0], enveloped_data[i], t) for (i, t) in enumerate(enveloped_time)]
        start_times.sort()
        enveloped_data = [d[1] for d in start_times]
        enveloped_time = [d[2] for d in start_times]

        print('env data shapes')
        print([data.shape for data in enveloped_data])
        print([data.shape for data in enveloped_time])
        data = np.vstack(enveloped_data)
        time = np.vstack(enveloped_time)
        return data, time

class Project():
    def __init__(self, eeg_data_folder=None, video_data_folder=None, title='New Project', dict=None):
        if dict is not None:
            self.__dict__ = dict
            return
        self.animal_list = []
        self.eeg_root_folder = eeg_data_folder
        self.video_root_folder = video_data_folder
        self.title = title
        self.current_animal = Animal()  # start with empty animal
        self.file_buffer = file_buffer()

    def save_to_json(self, fname):
        dict = self.__dict__.copy()
        dict['animal_list'] = [animal.__dict__ for animal in self.animal_list]  # make animals into dicts
        dict['current_animal'] = self.current_animal.__dict__
        dict['file_buffer'] = None
        json.dump(dict, open(fname, 'w'), indent=4)

    def load_from_json(self, fname):
        dict = json.load(open(fname))
        dict['animal_list'] = [Animal(dict=animal) for animal in dict['animal_list']]  # make dicts into animals
        dict['animal_list'].sort(key=lambda animal: animal.id)
        dict['current_animal'] = Animal(dict = dict['current_animal'])
        dict['file_buffer'] = file_buffer()
        self.__dict__ = dict

    def get_animal(self, animal_id):
        for animal in self.animal_list:
            if animal.id == animal_id:
                return animal
        return None  # return if animal not found

    def get_data_from_range(self, trange, channel=None, animal=None, n_envelope=None):
        '''
        :param trange: list of length 2 - [init_time, end_time] for the data to get
        :param channel: channel from wich to grab the data
        :param animal: animal object from which to get the data
        :param n_envelope: int - compute envelope in n_envelope number of points, if none, return all data
        :return:
        '''
        print('Project() get_data_from_range called for chanbel',channel,'; time range:', trange)
        if (animal is not None) and (animal is not self.current_animal):  # reset file buffer if animal has changed
            print('Clearing File Buffer')
            self.current_animal = animal
            self.file_buffer = file_buffer()

        # First check if data is already buffered, most of the time this will be the case:
        if trange[0] >= self.file_buffer.range[0] and trange[1] <= self.file_buffer.range[1]:
            print('Data already in buffer')
            return self.file_buffer.get_data_from_range(trange,channel,n_envelope)

        # Now clear buffer if range is not contiguous to previous range
        if trange[1] <= self.file_buffer.range[0] or trange[0] >= self.file_buffer.range[1]:
            print('Non-contiguous data: restarting buffer...')
            self.file_buffer = file_buffer()

        for i, file in enumerate(self.current_animal.eeg_files):
            arange = [self.current_animal.eeg_init_time[i], self.current_animal.eeg_init_time[i] + self.current_animal.eeg_duration[i]]
            if (trange[0] <= arange[0] <= trange[1]) or (trange[0] <= arange[1] <= trange[1]):
                print('Adding file to buffer: ', file)
                self.file_buffer.add_file_to_buffer(file)
        print('files in buffer: ' , self.file_buffer.files)
        return self.file_buffer.get_data_from_range(trange, channel, n_envelope)

