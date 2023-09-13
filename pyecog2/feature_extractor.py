import numpy as np
import os
import numpy as np
import scipy.stats as stats
from collections import OrderedDict
import json
from numba import jit
from pyecog2.ProjectClass import FileBuffer
from scipy.signal import get_window
from importlib import import_module
import multiprocessing
import logging
logger = logging.getLogger(__name__)
# constructors for functions that grab the power from frequency bands

# @jit(nopython=True)
def rfft_band_power(fdata, fs, band):
    return np.log(np.mean(np.abs(fdata[int(len(fdata)*band[0]/fs):int(len(fdata)*band[1]/fs)]))) # todo consider making this with proper units

def powerf(bandi, bandf, ch=0):
    return lambda fdata, fs: rfft_band_power(fdata[ch,:], fs, (bandi, bandf))



def rfft_band_corr(fdata_a,fdata_b,fs,band): # Correlation of the spectra within a frequency band
    bi = int(len(fdata_a)*band[0]/fs)
    bf = int(len(fdata_a)*band[1]/fs)
    cross = np.mean(np.abs((fdata_a[bi:bf] * fdata_b[bi:bf])))**2
    auto = np.mean(np.abs(fdata_a[bi:bf])**2) * np.mean(np.abs(fdata_b[bi:bf])**2)
    return np.log10(cross/auto)  # todo consider making this with proper units

def rfft_band_icorr(fdata_a,fdata_b,fs,band): # Correlation of the spectral imaginary part within a frequency band
    bi = int(len(fdata_a)*band[0]/fs)
    bf = int(len(fdata_a)*band[1]/fs)
    cross = np.mean(np.abs(np.imag((np.conj(fdata_a[bi:bf]) * fdata_b[bi:bf]))))**2
    auto = np.mean(np.abs(fdata_a[bi:bf])**2) * np.mean(np.abs(fdata_b[bi:bf])**2)
    return np.log10(cross/auto)  # todo consider making this with proper units


def fband_corr(bandi, bandf, cha, chb): # computes log
    return lambda fdata, fs: rfft_band_corr(fdata[cha,:],fdata[chb,:], fs, (bandi, bandf))


@jit(nopython=True)
def reg_entropy(fdata,fs):
    # regularized entropy of spectral data
    # fdata comes from rfft
    fdata_x_f = np.abs(fdata.ravel())*np.arange(1,len(fdata)+1)
    # print('fdata shape:',fdata_x_f.shape)
    fdata_x_f = fdata_x_f+1e-9*np.max(fdata_x_f)
    fdata_x_f = fdata_x_f**2/np.sum(fdata_x_f**2)
    return -np.sum(fdata_x_f*np.log(fdata_x_f))

# Worker funcitons to workaround the fact that lambda funcitons are not picklable for multiprocess
# The use of global variables means that only one feature extractor can be active at a time
def my_worker_flist_init(time_flist,freq_flist):
    global _time_flist, _freq_flist
    _freq_flist = [eval(f,module_dict) for f,module_dict in freq_flist]
    _time_flist = [eval(f,module_dict) for f,module_dict in time_flist]

# def my_worker_flist(x):
#     return [f(x) for f in _flist]


class FeatureExtractor():
    '''
    ML: I am not sure if using file buffers is the best way of going about it: on the one hand it abstracts away the file
    access, on the other hand it will probably always be relatively slow... maybe not a major issue since it will only be
    ran once (or a small number of times) for each project.
    '''
    def __init__(self, settings_dict = None):
        self.settings = settings_dict
        if self.settings is None:
            self.multichannel_auto_settings()
        self.update_from_settings()

    def multichannel_auto_settings(self,n_channels=1):
        if n_channels == 1:
            self.settings = OrderedDict(
                window_length = 5,  # length in seconds for the segments on which to compute features
                overlap = .5,        # overlap ratio between windows
                window = 'rectangular',
                # power_bands = [(1, 4), (4, 8), (8, 12), (12, 30), (30, 50), (50, 70), (70, 120)],
                # number_of_features = 15,
                feature_labels = ['min','max','mean','log std','kurtosis','skewness','log coastline (log sum of abs diff)',
                                  'log power in band (1, 4) Hz',
                                  'log power in band (4, 8) Hz',
                                  'log power in band (8, 12) Hz',
                                  'log power in band (12, 30) Hz',
                                  'log power in band (30, 50) Hz',
                                  'log power in band (50, 70) Hz',
                                  'log power in band (70, 120) Hz',
                                  'Spectrum entropy'
                                  ],
                feature_time_functions = ['np.min',
                                          'np.max',
                                          'np.mean',
                                          'lambda x:np.log(np.std(x))',
                                          'stats.kurtosis',
                                          'stats.skew',
                                          'lambda d:np.log(np.mean(np.abs(np.diff(d,axis=0))))'],
                feature_freq_functions=['fe.powerf(1, 4)',
                                        'fe.powerf(4, 8)',
                                        'fe.powerf(8, 12)',
                                        'fe.powerf(12, 30)',
                                        'fe.powerf(30, 50)',
                                        'fe.powerf(50, 70)',
                                        'fe.powerf(70, 120)',
                                        'fe.reg_entropy'],
                function_module_dependencies = [('numpy','np'),
                                                ('pyecog2.feature_extractor','fe'),
                                                ('scipy.stats','stats')]
             )
        else:
            self.settings = OrderedDict(
                window_length=5,  # length in seconds for the segments on which to compute features
                overlap=.5,  # overlap ratio between windows
                window='rectangular',
                # power_bands = [(1, 4), (4, 8), (8, 12), (12, 30), (30, 50), (50, 70), (70, 120)],
                # number_of_features = 15,
                feature_labels=sum([[f'ch{ch} log std', f'ch{ch} kurtosis', f'ch{ch} skewness',
                                    f'ch{ch} log coastline (log sum of abs diff)',
                                    f'ch{ch} log power in band (1, 4) Hz',
                                    f'ch{ch} log power in band (4, 8) Hz',
                                    f'ch{ch} log power in band (8, 12) Hz',
                                    f'ch{ch} log power in band (12, 30) Hz',
                                    f'ch{ch} log power in band (30, 50) Hz',
                                    f'ch{ch} log power in band (50, 120) Hz',
                                    f'ch{ch} Spectrum entropy']
                                    for ch in range(n_channels)], []) +
                                sum([[f'Spectral correlation (1Hz to 120Hz) between channels {cha} and {chb}):'
                                     for chb in range(cha+1, n_channels)]
                                     for cha in range(n_channels)], []),
                feature_time_functions=sum([[f'lambda x:np.log(np.std(x[{ch},:]))',
                                             f'lambda x:stats.kurtosis(x[{ch},:])',
                                             f'lambda x:stats.skew(x[{ch},:])',
                                             f'lambda x:np.log(np.mean(np.abs(np.diff(x[{ch},:],axis=0))))']
                                             for ch in range(n_channels)], []),
                feature_freq_functions=sum([[f'lambda x: fe.powerf(1, 4, ch={ch})',
                                             f'lambda x: fe.powerf(4, 8, ch={ch})',
                                             f'lambda x: fe.powerf(8, 12, ch={ch})',
                                             f'lambda x: fe.powerf(12, 30, ch={ch})',
                                             f'lambda x: fe.powerf(30, 50, ch={ch})',
                                             f'lambda x: fe.powerf(50, 120, ch={ch})',
                                             f'lambda x: fe.reg_entropy(x[{ch},:])']
                                            for ch in range(n_channels)], []) +
                                        sum([[f'fe.fband_corr(1, 120, {cha}, {chb})'
                                                  for chb in range(cha+1,n_channels)]
                                            for cha in range(n_channels)], []),
                function_module_dependencies=[('numpy', 'np'),
                                              ('pyecog2.feature_extractor', 'fe'),
                                              ('scipy.stats', 'stats')]
            )
        self.update_from_settings()

    def update_from_settings(self,settings = None):
        if settings is not None:
            self.settings = settings
        module_dict = {}
        for module,alias in self.settings['function_module_dependencies']:
            if alias is None or alias == '':
                alias = module
            module_dict[alias] = import_module(module)
        # self.feature_time_functions = [eval(f,module_dict) for f in self.settings['feature_time_functions']]
        # self.feature_freq_functions = [eval(f,module_dict) for f in self.settings['feature_freq_functions']]
        feature_time_functions = [(f,module_dict) for f in self.settings['feature_time_functions']]
        feature_freq_functions = [(f,module_dict) for f in self.settings['feature_freq_functions']]
        my_worker_flist_init(feature_time_functions, feature_freq_functions) # Workaround for multiprocessing

    def load_settings(self,fname):
        with open(fname) as f:
            settings = json.load(f)
        self.update_from_settings(settings)

    def save_settings(self,fname):
        with open(fname, 'w') as json_file:
            json.dump(self.settings, json_file, indent=2, sort_keys=True)

    @property
    def number_of_features(self):
        return len(self.settings['feature_time_functions']) + len(self.settings['feature_freq_functions'])

    def extract_features_from_animal(self, animal, re_write = False, n_cores = -1, progress_bar = None):
        # Create feature files for each eeg file
        if n_cores == -1:
            n_cores = multiprocessing.cpu_count()
        Nfiles = len(animal.eeg_files)
        eeg_files = animal.eeg_files
        eeg_init_time = animal.eeg_init_time
        eeg_duration = animal.eeg_duration
        animal_id = animal.id
        logger.info(f'Extracting features for animal {animal_id}')
        print(f'Extracting features for animal {animal_id}')
        tuples = [(eeg_files,eeg_init_time,eeg_duration, animal_id, i,re_write) for i in range(Nfiles)]
        # The following is not working yet...
        # with multiprocessing.Pool(processes=n_cores,initializer=my_worker_flist_init,
        #                           initargs = (_time_flist,_freq_flist)) as pool:
        with multiprocessing.Pool(processes=n_cores) as pool:
            for i, _ in enumerate(pool.imap(self.extract_features_from_file, tuples)):
                if progress_bar is not None:
                    progress_bar.setValue(100*(i+1)//Nfiles)

        # # Single core version
        # for i, _ in enumerate(map(self.extract_features_from_file, tuples)):
        #     if progress_bar is not None:
        #         progress_bar.setValue((100*(i+1))//Nfiles)

    def extract_features_from_file(self,animal_fileIndex_rewrite_tuple):
        if '_freq_flist' not in locals(): # initialize lambda functions in sub process
            self.update_from_settings()
        eeg_files, eeg_init_time, eeg_duration, animal_id, i, re_write = animal_fileIndex_rewrite_tuple
        eeg_fname = eeg_files[i]
        feature_fname = '.'.join(eeg_fname.split('.')[:-1] + ['features'])
        feature_metafname = '.'.join(eeg_fname.split('.')[:-1] + ['fmeta'])
        time_range = [eeg_init_time[i], eeg_init_time[i] + eeg_duration[i]]
        if re_write or not os.path.isfile(feature_fname):
            print('Extracting features for file', i + 1, 'of', len(eeg_files), ':', eeg_fname, end='\r')
            file_buffer = FileBuffer(None,False,[eeg_fname],[eeg_init_time[i]],[eeg_duration[i]])
            self.extract_features_from_time_range(file_buffer, time_range, feature_fname, feature_metafname,animal_id)
        else:
            # print(feature_fname,'already exists')
            pass

    def extract_features_from_time_range(self, file_buffer, time_range, feature_fname, feature_metafname, animal_id):
        # print('time_range:',time_range,feature_fname,feature_metafname)
        window_step = self.settings['window_length']*(1-self.settings['overlap'])
        window_starts = np.arange(time_range[0], time_range[1], window_step)
        # print('window_starts:',window_starts)
        features = np.zeros((len(window_starts), self.number_of_features),dtype='double')
        window = get_window(self.settings['window'],1)
        for i, window_init in enumerate(window_starts):
            data, time = file_buffer.get_data_from_range([window_init, window_init + self.settings['window_length']]) # get all data from time window
            data += np.random.randn(*data.shape).astype(data.dtype)*2**(-16) # add a bit of regularizing noise, bellow 24 bit noise floors
            if len(data) != len(window):
                window = get_window(self.settings['window'],len(data))
            window.shape = (data.shape[0],1)
            # data *= window
            fs = 1/(time[1]-time[0])
            dataf = np.fft.rfft(data*window,axis=0)/len(data)
            # for j,func in enumerate(self.feature_time_functions):
            for j,func in enumerate(_time_flist):
                features[i,j] = func(data)
            n = j
            # for j,func in enumerate(self.feature_freq_functions):
            for j,func in enumerate(_freq_flist):
                features[i, j+n+1] = func(dataf, fs)

        metadata = OrderedDict(fs=1/window_step,
                               no_channels=int(self.number_of_features),
                               data_format=str(features.dtype),
                               volts_per_bit=0,
                               transmitter_id=str(animal_id),
                               start_timestamp_unix=(time_range[0]),
                               duration=(time_range[1]-time_range[0]),
                               channel_labels=self.settings['feature_labels'])

        # print(metadata)
        with open(feature_metafname, 'w') as json_file:
            json.dump(metadata, json_file, indent=2, sort_keys=True)
        features.tofile(feature_fname)

    def __repr__(self):
        return 'FeatureExtractor with settings: ' + self.settings.__repr__()
