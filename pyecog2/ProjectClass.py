import json
import numpy as np
from collections import OrderedDict
from pyecog2.h5loader import H5File
import glob, os
from datetime import datetime
from pyecog2.annotations_module import AnnotationPage


def clip(x, a, b):  # utility funciton for file buffer
    return min(max(int(x), a), b)

def create_metafile_from_h5(file,duration = 3600):
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
                           duration=duration,  # assume all h5 files have 1hr duration
                           channel_labels=[str(label) for label in h5_file.attributes['t_ids']],
                           experiment_metadata_str='')
    metafile = file[:-2] + 'meta'
    with open(metafile, 'w') as json_file:
        json.dump(metadata, json_file, indent=2, sort_keys=True)


def read_neuropixels_metadata(fname):
    d = {}
    with open(fname) as f:
        while True:
            line =f.readline()
            if line == '':
                break
            linesplit = line.split('=')
            d[linesplit[0]]=linesplit[1][:-1]

    m = {'no_channels':int(d['nSavedChans']),
         'fs':float(d['imSampRate']),
         'start_timestamp_unix': datetime.timestamp(datetime.strptime(d['fileCreateTime'],'%Y-%m-%dT%H:%M:%S')),
         'duration':float(d['fileTimeSecs']),
         'data_format':'int16',
         'volts_per_bit': 0}
    return m


def load_metadata_file(fname):
    try:
        with open(fname, 'r') as json_file:
            metadata = json.load(json_file)
    except:
        try:
            metadata = read_neuropixels_metadata(fname)
        except:
            metadata = None
            print('Unrecognized metafile format')
    return metadata


class Animal():
    def __init__(self, id=None, eeg_folder=None, video_folder=None, dict={}):
        if dict != {}:
            self.__dict__ = dict
            self.annotations = AnnotationPage(dict=dict['annotations'])
            return

        if eeg_folder is not None:
            self.update_eeg_folder(eeg_folder)
            self.annotations = AnnotationPage()
        else:
            self.eeg_folder = ''
            self.eeg_files = []
            self.annotations = AnnotationPage()
            self.eeg_init_time = []
            self.eeg_duration = []

        if video_folder is not None:
            self.update_video_folder(video_folder)
        else:
            self.video_folder = ''
            self.video_files = []
            self.video_init_time = []
            self.video_duration = []

        if id is None and self.eeg_files:
            metadata = json.load(open(self.eeg_files[0]))
            self.id = metadata['transmitter_id']
        else:
            self.id = id

    def update_eeg_folder(self,eeg_folder):
        self.eeg_folder = eeg_folder
        h5files = glob.glob(eeg_folder + '/*.h5')
        h5files.sort()
        for i,file in enumerate(h5files):
            if os.path.isfile(file[:-2] + 'meta'):
                # print(file[:-2] + 'meta already exists')
                continue
            start = int(file.split('/')[-1].split('_')[0][1:])
            try:
                next_start = int(h5files[i+1].split('/')[-1].split('_')[0][1:])
                duration = min(next_start-start,3600)
            except:
                duration = 3600
            create_metafile_from_h5(file,duration)
        self.eeg_files = glob.glob(eeg_folder + '/*.meta')
        self.eeg_files.sort()
        self.eeg_init_time = []
        self.eeg_duration  = []
        for fname in self.eeg_files:
            metadata = load_metadata_file(fname)
            self.eeg_init_time.append(metadata['start_timestamp_unix'])
            self.eeg_duration.append(metadata['duration'])

    def update_video_folder(self,video_folder):
        self.video_folder = video_folder
        self.video_files = glob.glob(video_folder + '/*.mp4')
        self.video_init_time = [
            datetime(*map(int, [fname[-18:-14], fname[-14:-12], fname[-12:-10], fname[-10:-8], fname[-8:-6],
                                fname[-6:-4]])).timestamp()+3600
            for fname in self.video_files]
        self.video_duration = [15 * 60 for file in
                               self.video_files]  # this should be replaced in the future to account flexible video durations

    def dict(self):
        dict = self.__dict__.copy()
        dict['annotations'] = self.annotations.dict()
        return dict


class FileBuffer():  # Consider translating this to cython
    def __init__(self, animal=None):
        self.files = []
        self.range = [np.Inf, -np.Inf]
        self.data = []
        self.data_ranges = []
        self.metadata = []
        self.animal = animal

    def add_file_to_buffer(self, fname):
        if fname in self.files:  # skip if file is already buffered
            return
        else:
            self.files.append(fname)

        metadata = load_metadata_file(fname)
        self.metadata.append(metadata)
        if metadata['data_format'] == 'h5':
            h5file = H5File(fname[:-4] + 'h5')
            channels = []
            for tid in h5file.attributes['t_ids']:
                channels.append(h5file[tid]['data'])
            arr = np.vstack(channels).T
            self.data.append(arr)

        else:  # it is a bin file and can be mememaped
            m = np.memmap(fname[:-4] + 'bin', mode='r+', dtype =metadata['data_format'] )
            m = m.reshape((-1, metadata['no_channels']))
            self.data.append(m)

        trange = [metadata['start_timestamp_unix'], metadata['start_timestamp_unix'] + metadata['duration']]
        self.data_ranges.append(trange)

        if self.range[0] > trange[0]:  # buffering earlier file
            self.range[0] = trange[0]
            if len(self.data) > 3:  # buffer 3 files - consider having this as a variable...
                i = max(range(len(self.data)),
                        key=lambda j: self.data_ranges[j][0])  # get the index of the latest starting buffered file
                del (self.files[i])
                del (self.data[i])
                del (self.data_ranges[i])
                del (self.metadata[i])
                self.range = [min([r[0] for r in self.data_ranges]), max([r[1] for r in self.data_ranges])]

        if self.range[1] < trange[1]:  # buffering later file
            self.range[1] = trange[1]
            if len(self.data) > 3:  # buffer 3 files - consider having this as a variable...
                i = min(range(len(self.data)),
                        key=lambda j: self.data_ranges[j][0])  # get the index of the earliest starting buffered file
                del (self.files[i])
                del (self.data[i])
                del (self.data_ranges[i])
                del (self.metadata[i])
                self.range = [min([r[0] for r in self.data_ranges]), max([r[1] for r in self.data_ranges])]

    def get_nchannels(self):
        if self.data:
            return max([data.shape[1] for data in self.data])
        else:
            return 0

    def get_data_from_range(self, trange, channel=None, n_envelope=None):
        # First check if data is already buffered, most of the time this will be the case:
        if trange[0] >= self.range[0] and trange[1] <= self.range[1]:
            # print('Data already in buffer')
            pass
        else:
            # Now clear buffer if range is not contiguous to previous range
            if trange[1] <= self.range[0] or trange[0] >= self.range[1]:
                print('Non-contiguous data: restarting buffer...')
                self.files = []
                self.range = [np.Inf, -np.Inf]
                self.data = []
                self.data_ranges = []
                self.metadata = []
            # fill buffer with the necessary files:
            for i, file in enumerate(self.animal.eeg_files):
                arange = [self.animal.eeg_init_time[i], self.animal.eeg_init_time[i] + self.animal.eeg_duration[i]]
                if (arange[0] <= trange[0] <= arange[1]) or (arange[0] <= trange[1] <= arange[1]) or \
                        (trange[0] <= arange[0] <= trange[1]) or (trange[0] <= arange[1] <= trange[1]):
                    print('Adding file to buffer: ', file)
                    self.add_file_to_buffer(file)
            print('files in buffer: ', self.files)

        #  Find sample ranges from time data_ranges:
        sample_ranges = []
        # print('range:', self.range)
        # print('data ranges:', self.data_ranges)
        for i, ranges in enumerate(self.data_ranges):
            # print('metadata', i, ':', self.metadata[i])
            fs = self.metadata[i]['fs']
            # print(((trange[0] - ranges[0]) * fs, 0, len(self.data[i])))
            # sample_ranges.append([clip((trange[0] - ranges[0]) * fs, 0, len(self.data[i])),
            #                       clip((trange[1] - ranges[0]) * fs, 0, len(self.data[i]))])  # this does not work because len of data might be larger than falid h5durations

            sample_ranges.append([int(clip((trange[0] - ranges[0]) * fs, 0, (ranges[1] - ranges[0]) * fs)),
                                  int(clip((trange[1] - ranges[0]) * fs, 0,  (ranges[1] - ranges[0]) * fs))])

        total_sample_range = max(sum([s[1] - s[0] for s in sample_ranges]), 1)
        if n_envelope is None:
            n_envelope = total_sample_range
        file_envlopes = [int(n_envelope * (s[1] - s[0]) / total_sample_range) + 1 for s in
                         sample_ranges]  # distribute samples between files

        enveloped_data = []
        enveloped_time = []
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
                    enveloped_data.append(data[start:stop, channel].reshape(-1, 1))

            else:
                # Here convert data into a down-sampled array suitable for visualizing.
                # Must do this piecewise to limit memory usage.
                samples = (1 + (stop - start) // ds)
                visible_data = np.zeros((samples * 2, 1), dtype=data.dtype)
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
                        chunkMax_x = chunk_data[row_inds, mx_inds].reshape(len(chunk_data), 1)
                        chunkMin_x = chunk_data[row_inds, mi_inds].reshape(len(chunk_data), 1)
                        visible_data[targetPtr:targetPtr + chunk_data.shape[0] * 2:2] = chunkMin_x
                        visible_data[1 + targetPtr:1 + targetPtr + chunk_data.shape[0] * 2:2] = chunkMax_x
                        targetPtr += chunk_data.shape[0] * 2

                    enveloped_data.append(visible_data[:targetPtr, :].reshape((-1, 1)))
                except:
                    print('ERROR in downsampling')
                    raise
                    # throw_error()
                    # return 0

            enveloped_time.append(np.linspace(start / fs + self.data_ranges[i][0], (stop-1) / fs + self.data_ranges[i][0],
                                              len(enveloped_data[-1])).reshape(-1, 1))
            if len(enveloped_time[-1]) == 0:
                del (enveloped_time[-1])
                del (enveloped_data[-1])
            # print('env data shapes')
            # print([data.shape for data in enveloped_data])
            # print([data.shape for data in enveloped_time])
        # sort vectors with enveloped_time:
        start_times = [(t[0], enveloped_data[i], t) for (i, t) in enumerate(enveloped_time)]
        # print('***debug***',len(start_times))
        # if len(start_times) ==2:
        #     print('***debug***',start_times[0][0][0],start_times[1][0][0])
        #     print('***debug***',self.data_ranges)
        #     print('***debug***', self.files)
        start_times.sort()
        enveloped_data = [d[1] for d in start_times]
        enveloped_time = [d[2] for d in start_times]

        # print('env data shapes')
        # print([data.shape for data in enveloped_data])
        # print([data.shape for data in enveloped_time])
        if len(enveloped_data) > 0:
            data = np.vstack(enveloped_data)
            time = np.vstack(enveloped_time)
        else:
            data = np.array([0, 0])
            time = np.array(trange)
        return data, time


class Project():
    def __init__(self, main_model, eeg_data_folder=None, video_data_folder=None, title='New Project', project_file='',
                 dict=None):
        if dict is not None:
            self.__dict__ = dict
            self.animal_list = [Animal(dict=animal) for animal in dict['animal_list']]
            self.current_animal = Animal(dict=dict['current_animal'])
            self.main_model = main_model
            return
        self.main_model = main_model
        self.animal_list = []
        self.eeg_root_folder = eeg_data_folder
        self.video_root_folder = video_data_folder
        self.project_file = project_file
        self.title = title
        self.current_animal = Animal()
        self.set_current_animal(Animal())  # start with empty animal
        self.file_buffer = FileBuffer(self.current_animal)

    def set_current_animal(self, animal):  # copy alterations made to annotations
        if animal is None:
            return
        self.current_animal.annotations.copy_from(self.main_model.annotations)
        self.main_model.annotations.copy_from(animal.annotations)
        self.current_animal = animal
        self.file_buffer = FileBuffer(self.current_animal)
        self.main_model.annotations.sigLabelsChanged.emit('')

    def save_to_json(self, fname):
        try:
            self.current_animal.annotations.copy_from(
                self.main_model.annotations)  # save alterations made to the current animal annotations
        except:
            print('no main model defined')

        dict = self.__dict__.copy()
        del (dict['main_model'])
        dict['animal_list'] = [animal.dict() for animal in self.animal_list]  # make animals into dicts
        dict[
            'current_animal'] = self.current_animal.id  # Animal().dict() # self.current_animal.dict() # Otherwise when loading the current animal would not be in the animal_list
        dict['file_buffer'] = None
        print(dict)
        json.dump(dict, open(fname, 'w'), indent=4)

    def load_from_json(self, fname):
        dict = json.load(open(fname))
        dict['animal_list'] = [Animal(dict=animal) for animal in dict['animal_list']]  # make dicts into animals
        dict['animal_list'].sort(key=lambda animal: animal.id)
        current_animal_id = dict['current_animal']  # save id
        dict['current_animal'] = Animal()  # pre-initialize with empty animal
        main_model = self.main_model
        self.__dict__ = dict
        self.main_model = main_model
        print('looking for', current_animal_id)
        self.set_current_animal(self.get_animal(current_animal_id))
        print('current animal:', self.current_animal.id)
        self.file_buffer = FileBuffer(self.current_animal)
        self.project_file = fname

    def export_annotations(self, fname):
        with open(fname, 'w') as f:
            f.write('Animal ID,label,' + 'start,stop\n')
            for animal in self.animal_list:
                for a in animal.annotations.annotations_list:
                    f.write(animal.id + ',' + a.getLabel() + ',' + str(a.getStart()) + ',' + str(a.getEnd()) + '\n')
        return

    def get_animal(self, animal_id):
        for animal in self.animal_list:
            if animal.id == animal_id:
                return animal
        return None  # return if animal not found

    def add_animal(self, animal):
        if self.get_animal(animal.id) is None:
            print('Added animal', animal.id, 'to project')
            self.animal_list.append(animal)
        else:
            print('Animal with id:', animal.id, 'already exists in project: nothing added')

    def delete_animal(self,animal_id):
        for animal in self.animal_list:
            if animal.id == animal_id:
                self.animal_list.remove(animal)

    def update_files_from_animal_directories(self):
        for animal in self.animal_list:
            animal.update_eeg_folder(animal.eeg_folder)
            animal.update_video_folder(animal.video_folder)

    def update_project_from_root_directories(self):
        self.update_files_from_animal_directories()  # first update already existing animals
        existing_eeg_dir = [animal.eeg_folder for animal in self.animal_list]
        eeg_dir_list = glob.glob(self.eeg_root_folder + '/*/')  # then check for new animals
        video_dir_list = glob.glob(self.video_root_folder + '/*/')
        for directory in eeg_dir_list:
            if directory not in existing_eeg_dir:
                id = directory.split('/')[-2]
                print('Creating animal from directory:' ,directory)
                print('Adding animal with id:',id)
                video_dir = self.video_root_folder + '/' + id
                if video_dir not in video_dir_list:
                    video_dir = None  # check if compatible video dir exists
                self.add_animal(Animal(id=id,eeg_folder=directory,video_folder=video_dir))


    def get_data_from_range(self, trange, channel=None, animal=None, n_envelope=None):
        '''
        :param trange: list of length 2 - [init_time, end_time] for the data to get
        :param channel: channel from wich to grab the data
        :param animal: animal object from which to get the data
        :param n_envelope: int - compute envelope in n_envelope number of points, if none, return all data
        :return:
        '''
        # print('Project() get_data_from_range called for chanbel', channel, '; time range:', trange, ', duration:',
        #       trange[1] - trange[0])
        if (animal is not None) and (animal is not self.current_animal):  # reset file buffer if animal has changed
            print('Clearing File Buffer')
            self.set_current_animal(animal)
            # self.current_animal = animal
            self.file_buffer = FileBuffer(self.current_animal)

        return self.file_buffer.get_data_from_range(trange, channel, n_envelope)

    def get_project_time_range(self):
        if not self.animal_list:
            return np.array([0,0])
        i=np.Inf
        e=-np.Inf
        for animal in self.animal_list:
            i = min(min(animal.eeg_init_time),i)
            e = max(max(np.array(animal.eeg_init_time) + np.array(animal.eeg_duration)),e)
        return np.array([i,e])