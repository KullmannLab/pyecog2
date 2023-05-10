import json
import numpy as np
from collections import OrderedDict
from pyecog2.h5loader import H5File
import glob, os
from datetime import datetime
from pyecog2.annotations_module import AnnotationPage
from scipy import signal
from PySide2 import QtCore
import pyqtgraph as pg
from timeit import default_timer as timer

import logging
logger = logging.getLogger(__name__)

def clip(x, a, b):  # utility funciton for file buffer
    return min(max(int(x), a), b)

def intervals_overlap(a,b):
    # return (a[0] <= b[0] < a[1]) or (a[0] <= b[1] < a[1]) or (b[0] <= a[0] < b[1]) or (b[0] <= a[1] < b[1])
    return (a[0] <= b[0] < a[1]) or (a[0] < b[1] <= a[1]) or (b[0] <= a[0] < b[1]) or (b[0] < a[1] <= b[1])

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
                           volts_per_bit=4e-7,
                           transmitter_id=str(h5_file.attributes['t_ids']),
                           start_timestamp_unix=int(os.path.split(file)[-1].split('_')[0][1:]),
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
         'binaryfilename':fname[:-4] + 'bin',
         'fs':float(d['imSampRate']),
         'start_timestamp_unix': datetime.timestamp(datetime.strptime(d['fileCreateTime'],'%Y-%m-%dT%H:%M:%S')),
         'duration':float(d['fileTimeSecs']),
         'data_format':'int16',
         'volts_per_bit': 1.170e-3/float(eval('[' + (d['~imroTbl'].replace('(', ',(').replace(' ', ',')[1:] + ']') )[1][3])}
    return m


def load_metadata_file(fname):
    try:  # most common scenario
        with open(fname, 'r') as json_file:
            metadata = json.load(json_file)
    except Exception:
        try: # in case of neuropixels data
            metadata = read_neuropixels_metadata(fname)
        except Exception:
            metadata = None
            try:
                if not os.path.isfile(fname):  # in case of h5 files never seen beforehand
                    if os.path.isfile(fname[:-4] + 'h5'):
                        create_metafile_from_h5(fname[:-4] + 'h5')  # create metafiles for h5 files if they do not exist
                        with open(fname, 'r') as json_file:
                            metadata = json.load(json_file)
                    else:
                        logger.info(f'Non-existent file:{fname}')
            except Exception:
                logger.info('Unrecognized metafile format')
    return metadata

class Animal():
    def __init__(self, id=None, eeg_folder=None, video_folder=None, dict={}):
        if dict != {}:
            self.__dict__ = dict
            self.annotations = AnnotationPage(dic=dict['annotations'])
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
        self.eeg_folder = os.path.normpath(eeg_folder)
        logger.info(f'Looking for files:{eeg_folder}{os.path.sep}*.h5')
        h5files = glob.glob(eeg_folder + os.path.sep + '*.h5')
        h5files.sort()
        for i,file in enumerate(h5files):
            if os.path.isfile(file[:-2] + 'meta'):
                continue
            start = int(os.path.split(file)[-1].split('_')[0][1:])
            try:
                next_start = int(os.path.split(h5files[i+1])[-1].split('_')[0][1:])
                duration = min(next_start-start,3600)
            except Exception:
                duration = 3600
            create_metafile_from_h5(file,duration)
        self.eeg_files = glob.glob(eeg_folder + os.path.sep + '*.meta')
        self.eeg_files.sort()
        self.eeg_init_time = []
        self.eeg_duration  = []
        for fname in self.eeg_files:
            metadata = load_metadata_file(fname)
            self.eeg_init_time.append(metadata['start_timestamp_unix'])
            self.eeg_duration.append(metadata['duration'])

    def update_video_folder(self,video_folder):
        self.video_folder = os.path.normpath(video_folder)
        self.video_files = glob.glob(video_folder + os.path.sep + '*.mp4')
        self.video_init_time = [float(os.path.split(fname)[-1][1:-4]) if os.path.split(fname)[-1].startswith('V') else
                                datetime(*map(int, [fname[-18:-14], fname[-14:-12], fname[-12:-10], fname[-10:-8],
                                                    fname[-8:-6], fname[-6:-4]])).timestamp()
                                for fname in self.video_files]
        self.video_duration = [15 * 60 for file in
                               self.video_files]  # this should be replaced in the future to account flexible video duration or remove this field completely

    def substitute_eeg_folder_prefix(self,old_prefix,new_prefix):
        f = self.eeg_folder
        f = f.replace('\\', '/')
        if f.startswith(old_prefix):
            f = os.path.normpath(f'{new_prefix}{f[len(old_prefix):]}')
        self.eeg_folder = f
        already_warned = False
        for i,f in enumerate(self.eeg_files):
            # replace backslashes from windows to more flexible forward dashes (if someone uses backslashes in UNIX... they deserve the ensuing bug)
            f = f.replace('\\', '/')
            if f.startswith(old_prefix):
                f = os.path.normpath(f'{new_prefix}{f[len(old_prefix):]}')
                self.eeg_files[i] = f
            else:
                if not already_warned:
                    logger.warning('EEG file name does not start with given prefix')
                    already_warned = True

    def substitute_video_folder_prefix(self,old_prefix,new_prefix):
        f = self.video_folder
        f = f.replace('\\', '/')
        if f.startswith(old_prefix):
            f = os.path.normpath(f'{new_prefix}{f[len(old_prefix):]}')
        self.video_folder = f
        already_warned = False
        for i,f in enumerate(self.video_files):
            # replace backslashes from windows to more flexible forward dashes (if someone uses backslashes in UNIX... they deserve the ensuing bug)
            f = f.replace('\\','/')
            if f.startswith(old_prefix):
                f = os.path.normpath(f'{new_prefix}{f[len(old_prefix):]}')
                self.video_files[i] = f
            else:
                if not already_warned:
                    logger.warning('Video file name does not start with given prefix')
                    already_warned = True

    def dict(self):
        dict = self.__dict__.copy()
        dict['annotations'] = self.annotations.dict()
        return dict

    def get_animal_time_range(self):
        try:
            i = min(self.eeg_init_time)
            e = max(np.array(self.eeg_init_time) + np.array(self.eeg_duration))
        except ValueError:
            i = 0
            e = 0
        return np.array([i, e])


class FileBuffer():  # Consider translating this to cython
    def __init__(self, animal=None, verbose=True, eeg_files=None, eeg_init_time=None, eeg_duration=None):
        self.files = []
        self.range = [np.Inf, -np.Inf]
        self.data = []
        self.data_ranges = []
        self.metadata = []
        if animal is not None:  # avoid saving animal for uses in multiprocessing
            eeg_files = animal.eeg_files
            eeg_init_time = animal.eeg_init_time
            eeg_duration = animal.eeg_duration

        self.eeg_files = eeg_files
        self.eeg_init_time = eeg_init_time
        self.eeg_duration = eeg_duration
        self.verbose = verbose

    def add_file_to_buffer(self, fname):
        if fname in self.files:  # skip if file is already buffered
            return
        else:
            metadata = load_metadata_file(fname)
            if metadata is None: # file probably does not exist, error in project file settings
                return
            self.metadata.append(metadata)
            self.files.append(fname)

        if metadata['data_format'] == 'h5':
            try:
                h5file = H5File(fname[:-4] + 'h5')
            except:
                logger.warning(f'error trying to open {fname[:-4]} h5')
                raise
            channels = []
            duration = metadata['duration']
            for tid in h5file.attributes['t_ids']:
                if duration < 3600: # H5 file is screwed u, so will only grab the start of the data points
                    channels.append(h5file[tid]['data'][:int(duration*metadata['fs'])])
                else:
                    channels.append(h5file[tid]['data'])
            arr = np.vstack(channels).T
            self.data.append(arr)
        else:  # it is a bin file and can be mememaped
            try:
                if self.verbose: logger.info(f'opening binary file: {metadata["binaryfilename"]}')
                m = np.memmap(metadata['binaryfilename'], mode='r', dtype =metadata['data_format'] )
            except ValueError:
                m = np.zeros(0)  # binary file is empty so just create empty array
            m = m.reshape((-1, metadata['no_channels']))
            self.data.append(m)

        trange = [metadata['start_timestamp_unix'], metadata['start_timestamp_unix'] + 1/metadata['fs']*self.data[-1].shape[0]]
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

    def clear_buffer(self):
        self.files = []
        self.range = [np.Inf, -np.Inf]
        self.data = []
        self.data_ranges = []
        self.metadata = []

    def get_t_max_for_live_plot(self):
        return max([r[1] for r in self.data_ranges])


    def get_data_from_range(self, trange, channel=None, n_envelope=None, for_plot=False, filter_settings=(False,0,0)):
        # First check if data is already buffered, most of the time this will be the case:
        if trange[0] >= self.range[0] and trange[1] <= self.range[1]:
            # if self.verbose: print('Data already in buffer')
            pass
        else:
            # Now clear buffer if range is not contiguous to previous range
            if trange[1] < self.range[0] or trange[0] > self.range[1]:
                if self.verbose: logger.info('Non-contiguous data: restarting buffer...')
                self.clear_buffer()
            # fill buffer with the necessary files:
            for i, file in enumerate(self.eeg_files):
                frange = [self.eeg_init_time[i], self.eeg_init_time[i] + self.eeg_duration[i]]
                # if (frange[0] <= trange[0] < frange[1]) or (frange[0] <= trange[1] < frange[1]) or \
                #         (trange[0] <= frange[0] < trange[1]) or (trange[0] <= frange[1] < trange[1]):
                if intervals_overlap(frange,trange):
                    if self.verbose: logger.info(f'Adding file to buffer: {file}')
                    self.add_file_to_buffer(file)
            if self.verbose: logger.info(f'files in buffer: {self.files}')

        #  Find sample ranges from time data_ranges:
        sample_ranges = []
        # if self.verbose: print('range:', self.range)
        # if self.verbose: print('data ranges:', self.data_ranges)
        for i, ranges in enumerate(self.data_ranges):
            # if self.verbose: print('metadata', i, ':', self.metadata[i])
            fs = self.metadata[i]['fs']
            # if self.verbose: print(((trange[0] - ranges[0]) * fs, 0, len(self.data[i])))
            # sample_ranges.append([clip((trange[0] - ranges[0]) * fs, 0, len(self.data[i])),
            #                       clip((trange[1] - ranges[0]) * fs, 0, len(self.data[i]))])  # this does not work because len of data might be larger than falid h5durations

            sample_ranges.append([int(clip((trange[0] - ranges[0]) * fs, 0, (ranges[1] - ranges[0]) * fs)),
                                  int(clip((trange[1] - ranges[0]) * fs, 0,  (ranges[1] - ranges[0]) * fs))])

        total_sample_range = max(sum([s[1] - s[0] for s in sample_ranges]), 1)
        if n_envelope is None:
            n_envelope = total_sample_range
        if n_envelope>2**(28): # data is larger than 1 GByte and could bust available RAM 4bytes*2**28 = 1GB
            if self.verbose: logger.warning('Too much data to keep in memory (>1GB)')
            return [],[]

        file_envlopes = [int(n_envelope * (s[1] - s[0]) / total_sample_range) + 1 for s in
                         sample_ranges]  # distribute samples between files

        enveloped_data = []
        enveloped_time = []
        no_downsampling = True
        for i, data in enumerate(self.data):

            if channel is not None and channel>=data.shape[1]:
                continue # skip this file becuase it does not have channel with required index
            start = sample_ranges[i][0]
            stop = sample_ranges[i][1]
            fs = self.metadata[i]['fs']
            no_channels = self.metadata[i]['no_channels']
            dV = self.metadata[i]['volts_per_bit'] if self.metadata[i]['volts_per_bit'] != 0 else 1
            # Decide by how much we should downsample
            ds = int((stop - start) / file_envlopes[i]) + 1
            # print('Downsampling ratio:', ds,file_envlopes,sample_ranges)
            if channel is None:
                # poor coding here, we are not computing proper envelopes, but it'll do for now because this is only
                # used for coputing channel scallings so far
                enveloped_data.append(dV*data[start:stop:ds, :])
                if ds != 0:
                    no_downsampling = False
            elif ds == 1:
                # Small enough to display with no intervention.
                enveloped_data.append(dV*data[start:stop, channel].reshape(-1, 1))
            else:
                no_downsampling = False
                # Here convert data into a down-sampled array suitable for visualizing.
                # Must do this piecewise to limit memory usage.
                dss = 1
                originalds = ds
                if ds > 10 and no_channels > 10: # so much downsampling that we might as well skip some samples if lots of channels
                    dss = ds//10  # we will only grab about 10 samples to compute min and max for envelope
                    originalds = ds
                    ds = 10
                # print('Decimating data in filebuffer by', dss, 'x factor. (original ds:', originalds, ')')

                samples = (1 + (stop - start) // ds)
                visible_data = np.zeros((samples * 2, 1), dtype=data.dtype)
                sourcePtr = start
                targetPtr = 0
                try:
                    # read data in chunks of ~1M samples
                    chunkSize = int((1e6 // ds) * ds)
                    while sourcePtr < stop - 1:
                        chunk_data = data[sourcePtr:min(stop, sourcePtr + chunkSize):dss, channel]
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

                    enveloped_data.append(dV*visible_data[:targetPtr, :].reshape((-1, 1)))
                except Exception:
                    logger.error('ERROR in downsampling')
                    raise
                    # throw_error()
                    # return 0

            enveloped_time.append(np.linspace(start / fs + self.data_ranges[i][0], (stop-1) / fs + self.data_ranges[i][0],
                                              len(enveloped_data[-1])).reshape(-1, 1))
            # enveloped_time.append(np.linspace(start / fs + self.data_ranges[i][0], (stop-1) / fs + self.data_ranges[i][0],
            #                                   len(enveloped_data[-1])).reshape(-1, 1))
            if len(enveloped_time[-1]) == 0:
                del (enveloped_time[-1])
                del (enveloped_data[-1])
            # if self.verbose: print('env data shapes')
            # if self.verbose: print([data.shape for data in enveloped_data])
            # if self.verbose: print([data.shape for data in enveloped_time])
        # sort vectors with enveloped_time:
        start_times = [(t[0], enveloped_data[i], t) for (i, t) in enumerate(enveloped_time)]
        # if self.verbose: print('***debug***',len(start_times))
        # if len(start_times) ==2:
        #     if self.verbose: print('***debug***',start_times[0][0][0],start_times[1][0][0])
        #     if self.verbose: print('***debug***',self.data_ranges)
        #     if self.verbose: print('***debug***', self.files)
        start_times.sort(key=lambda s:s[0])
        enveloped_data = [d[1] for d in start_times]
        enveloped_time = [d[2] for d in start_times]

        # if self.verbose: print('env data shapes')
        # if self.verbose: print([data.shape for data in enveloped_data])
        # if self.verbose: print([data.shape for data in enveloped_time])
        if len(enveloped_data) > 0:
            data = np.vstack(enveloped_data)
            time = np.vstack(enveloped_time)
            # if for_plot and filter_settings[0]: # apply LP filter only for plots
            #     fs = 2/(time[2]-time[0])
            #     nyq = 0.5 * fs[0]
            #     hpcutoff = min(max(filter_settings[1] / nyq, 0.001), .5)
            #     data = data - np.mean(data)
            #     lpcutoff = min(max(filter_settings[2] / nyq, 0.001), 1)
            #     # for some reason the bandpass butterworth filter is very unstable
            #     if lpcutoff<.99:  # don't apply filter if LP cutoff freqquency is above nyquist freq.
            #         # if self.verbose: print('applying LP filter to display data:', filter_settings, fs, nyq, lpcutoff)
            #         b, a = signal.butter(2, lpcutoff, 'lowpass', analog=False)
            #         data = signal.filtfilt(b, a, data,axis =0,method='gust')
            #     if hpcutoff > .001: # don't apply filter if HP cutoff frequency too low.
            #         # if self.verbose: print('applying HP filter to display data:', filter_settings, fs, nyq, hpcutoff)
            #         b, a = signal.butter(2, hpcutoff, 'highpass', analog=False)
            #         data = signal.filtfilt(b, a, data,axis =0,method='gust')
        else:
            data = np.zeros((0,1))
            time = np.zeros((0,1))
            # data = np.array([0, 0])
            # time = np.array(trange)

        return data, time


class Project():
    def __init__(self, main_model=None, eeg_data_folder=None, video_data_folder=None, title='New Project', project_file='',
                 dict=None):
        if dict is not None:
            self.__dict__ = dict
            self.filter_settings = (False, 0, 1e6)
            self.animal_list = [Animal(dict=animal) for animal in dict['animal_list']]
            self.current_animal = Animal(dict=dict['current_animal'])
            self.main_model = main_model
            return
        if main_model is None:
            main_model = MainModel()
        self.main_model = main_model
        self.animal_list = []
        self.eeg_root_folder = eeg_data_folder
        self.video_root_folder = video_data_folder
        self.project_file = project_file
        self.title = title
        self.current_animal = Animal()
        self.set_current_animal(Animal())  # start with empty animal
        self.filter_settings = (False,0,1e6) # initialize filter settings
        self.file_buffer = FileBuffer(self.current_animal)
        self.ndf_converter_settings = None
        self.main_model.sigProjectChanged.emit()

    def setTitle(self,title):
        self.title = title
        self.main_model.sigProjectChanged.emit()

    def set_current_animal(self, animal):  # copy alterations made to annotations
        start_t = timer()
        logger.info('ProjectClass set_current_animal start')
        if animal is None or animal is self.current_animal:
            return
        self.current_animal.annotations.copy_from(self.main_model.annotations,connect_history=False,quiet=True)
        self.main_model.annotations.copy_from(animal.annotations,quiet=True)
        self.current_animal = animal
        self.file_buffer = FileBuffer(self.current_animal)
        self.main_model.annotations.sigLabelsChanged.emit('')
        logger.info(f'ProjectClass set_current_animal ran in {timer()-start_t} seconds')

    def save_to_json(self, fname):
        try:
            # save alterations made to the current animal annotations
            # self.main_model.annotations.copy_to(self.current_animal.annotations)
            self.current_animal.annotations.copy_from(self.main_model.annotations, connect_history=False, quiet=True)
        except Exception:
            logger.error('no main model defined')

        dict = self.__dict__.copy()
        # print(dict.keys())
        del (dict['main_model'])
        dict['animal_list'] = [animal.dict() for animal in self.animal_list]  # make animals into dicts
        if self.current_animal is not None:
            dict['current_animal'] = self.current_animal.id  # Animal().dict() # self.current_animal.dict() # Otherwise when loading the current animal would not be in the animal_list
        else:
            dict['current_animal'] = None
        dict['file_buffer'] = None
        # print(dict)
        json.dump(dict, open(fname, 'w'), indent=2)

    def load_from_json(self, fname):
        with open(fname) as f:
            dict = json.load(f)
        dict['animal_list'] = [Animal(dict=animal) for animal in dict['animal_list']]  # make dicts into animals
        dict['animal_list'].sort(key=lambda animal: animal.id)
        current_animal_id = dict['current_animal']  # save id
        dict['current_animal'] = Animal()  # pre-initialize with empty animal
        main_model = self.main_model
        self.__dict__ = dict
        self.main_model = main_model
        logger.info(f'looking for animal: {current_animal_id}')
        self.set_current_animal(self.get_animal(current_animal_id))
        logger.info(f'current animal:{self.current_animal.id}')
        self.file_buffer = FileBuffer(self.current_animal)
        orig_dirname, org_fname = os.path.split(self.project_file)
        new_dirname, new_fname = os.path.split(fname.strip('_autosave'))
        if self.project_file != fname.strip('_autosave'):
            logger.info('Project file changed since last opening')
            if orig_dirname == new_dirname:
                logger.info('Only file name changed')
                self.project_file = fname.strip('_autosave') # when recovering autosaves, make the project file the original project file
            else:
                logger.info('Project file changed directories - asking if user wants to update EEG and/or Video directories as well')

        if not hasattr(self,'filter_settings'):  #Backwards compatibility
            self.filter_settings = (False, 0, 1e6)
        self.main_model.sigProjectChanged.emit()
        return (new_dirname, orig_dirname)

    def update_folder_structure_from_new_project_location(self, new_project_path,
                                                          old_project_path, update_eeg=True, update_video=True):
        logger.info(f'Updating project folders, from: {old_project_path}, to:{new_project_path}')
        old_project_path_n = old_project_path.replace('\\', '/')
        new_project_path_n = new_project_path.replace('\\', '/')
        commonsuffix =  os.path.commonprefix([old_project_path_n[::-1],new_project_path_n[::-1]])[::-1]
        new_prefix = new_project_path_n[:-len(commonsuffix)+1]
        old_prefix = old_project_path_n[:-len(commonsuffix)+1]
        for a in self.animal_list:
            logger.info(f'Updating project folders for animal {a.id}')
            if update_eeg:
                a.substitute_eeg_folder_prefix(old_prefix,new_prefix)
            if update_video:
                a.substitute_video_folder_prefix(old_prefix,new_prefix)
        self.main_model.sigProjectChanged.emit()

    def export_annotations(self, fname):
        with open(fname, 'w') as f:
            f.write('Animal ID,label,start,stop,confidence,notes\n')
            for animal in self.animal_list:
                for a in animal.annotations.annotations_list:
                    f.write(animal.id + ',' + a.getLabel() + ',' + str(a.getStart()) + ',' + str(a.getEnd()) +
                            ',' + str(a.getConfidence()) +  ',' + str(a.getNotes()) + '\n')
        return

    def get_animal(self, animal_id):
        for animal in self.animal_list:
            if animal.id == animal_id:
                return animal
        return None  # return if animal not found

    def add_animal(self, animal):
        if self.get_animal(animal.id) is None:
            logger.info(f'Added animal {animal.id} to project')
            self.animal_list.append(animal)
            self.main_model.sigProjectChanged.emit()
        else:
            logger.info(f'Animal with id: {animal.id} already exists in project: nothing added')

    def delete_animal(self,animal_id):
        for animal in self.animal_list:
            if animal.id == animal_id:
                self.animal_list.remove(animal)
                self.main_model.sigProjectChanged.emit()

    def update_files_from_animal_directories(self):
        for animal in self.animal_list:
            logger.info(f'Updating directories for animal {animal}') # give progress feedback for project editor
            animal.update_eeg_folder(os.path.normpath(animal.eeg_folder))
            animal.update_video_folder(os.path.normpath(animal.video_folder))
        self.main_model.sigProjectChanged.emit()

    def update_project_from_root_directories(self):
        self.eeg_root_folder = os.path.normpath(self.eeg_root_folder)
        self.video_root_folder = os.path.normpath(self.video_root_folder)
        self.update_files_from_animal_directories()  # first update already existing animals
        existing_eeg_dir = [animal.eeg_folder for animal in self.animal_list]
        eeg_dir_list = glob.glob(self.eeg_root_folder + os.path.sep + '*' + os.path.sep)  # then check for new animals
        video_dir_list = glob.glob(self.video_root_folder + os.path.sep + '*' + os.path.sep)
        for directory in eeg_dir_list:
            if directory not in existing_eeg_dir:
                id = directory.split(os.path.sep)[-2]
                logger.info(f'Creating animal from directory:{directory}')
                logger.info(f'Adding animal with id: {id}')
                video_dir = self.video_root_folder + os.path.sep + id + os.path.sep
                if video_dir not in video_dir_list:
                    video_dir = None  # check if compatible video dir exists
                self.add_animal(Animal(id=id,eeg_folder=directory,video_folder=video_dir))
        self.main_model.sigProjectChanged.emit()

    def get_data_from_range(self, trange, channel=None, animal=None, n_envelope=None, for_plot=False):
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
            logger.info('Clearing File Buffer')
            self.set_current_animal(animal)
            # self.current_animal = animal
            self.file_buffer = FileBuffer(self.current_animal)

        return self.file_buffer.get_data_from_range(trange, channel, n_envelope,for_plot,self.filter_settings)

    def updateFilterSettings(self, settings=(False,0,1e6)):
        self.filter_settings = settings

    def get_project_time_range(self):
        if not self.animal_list:
            return np.array([0,0])
        i = np.Inf
        e = -np.Inf
        for animal in self.animal_list:
            if animal.eeg_init_time: # only consider animals with files
                ai, ae = animal.get_animal_time_range()
                i = min(ai,i)
                e = max(ae,e)
        return np.array([i,e])

    def get_all_labels(self):
        return set([l for a in self.animal_list for l in a.annotations.labels if not l.startswith('(auto)')])

    def get_all_animal_ids(self):
        return [a.id for a in self.animal_list]

    def set_temp_project_from_folder(self,eeg_folder):
        eeg_folder = os.path.normpath(eeg_folder)
        logger.info(f'Looking for files: {eeg_folder}{os.path.sep}*.h5')
        h5files = glob.glob(eeg_folder + os.path.sep + '*.h5')
        h5files.sort()
        for i, file in enumerate(h5files):
            if os.path.isfile(file[:-2] + 'meta'):
                # print(file[:-2] + 'meta already exists')
                continue
            start = int(os.path.split(file)[-1].split('_')[0][1:])
            try:
                next_start = int(os.path.split(h5files[i + 1])[-1].split('_')[0][1:])
                duration = min(next_start - start, 3600)
            except Exception:
                duration = 3600
            create_metafile_from_h5(file, duration)
        eeg_files = glob.glob(eeg_folder + os.path.sep + '*.meta')
        eeg_files.sort()
        for fname in eeg_files:
            animal = Animal(id=os.path.split(fname)[-1], eeg_folder='')
            metadata = load_metadata_file(fname)
            animal.eeg_files.append(fname)
            animal.eeg_init_time.append(metadata['start_timestamp_unix'])
            animal.eeg_duration.append(metadata['duration'])
            self.add_animal(animal)

class MainModel(QtCore.QObject):
    sigTimeChanged      = QtCore.Signal(object)
    sigWindowChanged    = QtCore.Signal(object)
    sigProjectChanged   = QtCore.Signal()

    def __init__(self):
        super().__init__()
        self.data_eeg = np.array([])
        self.time_range = np.array([0,0])
        self.data_acc = np.array([])
        self.time_position = 0
        self.time_position_emited = self.time_position
        self.window = [0, 0]
        self.filenames_dict = {'eeg': '', 'meta' : '', 'anno': '', 'acc': ''}
        self.file_meta_dict = {}
        self.annotations = AnnotationPage()
        self.project = Project(self)
        self.annotations_history = []
        self.annotations_history_backcounter = 0

        pen = pg.mkPen((0, 0, 0, 100))  # (1, 1, 1, 100)
        brush = pg.mkBrush((255, 255, 255, 255))  # (1, 1, 1, 100)
        self.color_settings = {'pen':pen,'brush':brush}


    def set_time_position(self, pos):
        self.time_position = pos
        # print('Current Time:', pos)
        if abs(pos - self.time_position_emited) > .01: # only emit signal if time_position actually changed
            self.time_position_emited = pos
            self.sigTimeChanged.emit(pos)
            # print('Current Time emited:', pos)

    def set_window_pos(self, pos):
        pos = [min(pos),max(pos)]
        if pos != self.window:
            self.window = pos
            self.sigWindowChanged.emit(pos)
            logger.info(f'Window changed to:{pos}')
