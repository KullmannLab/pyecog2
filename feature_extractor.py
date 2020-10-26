import numpy as np
from ProjectClass import FileBuffer
import os
import numpy as np
import scipy.stats as stats
from collections import OrderedDict
import json


# constructors for functions that grab the power from frequency bands
def rfft_band_power(fdata, fs, band):
    return np.sum(np.abs(fdata[int(len(fdata)*band[0]/fs):int(len(fdata)*band[1]/fs)]))


def powerf(bandi, bandf):
    return lambda fdata, fs: rfft_band_power(fdata, fs, (bandi, bandf))


class FeatureExtractor():
    '''
    ML: I am not sure if using file buffers is the best way of going about it: on the one hand it abstracts away the file
    access, on the other hand it will probably always be relatively slow... maybe not a major issue since it will only be
    ran once (or a small number of times) for each project.

    Preliminarily just thinking about single channel data. Include multichannel features later
    '''
    def __init__(self, settings_dict = None):
        self.settings = settings_dict
        if self.settings is None:
            self.settings = OrderedDict(
                window_length = 5,  # length in seconds for the segments on which to compute features
                overlap = .5,        # overlap ratio between windows
                window = 'rectangular',
                power_bands = [(1, 4), (4, 8), (8, 12), (12, 30), (30, 50), (50, 70), (70, 120)],
                number_of_features = 14,
                feature_labels = ['min','max','mean','std','kurtosis','skewness','coastline (sum of abs diff)',
                                  'powerf(1, 4)',
                                  'powerf(4, 8)',
                                  'powerf(8, 12)',
                                  'powerf(12, 30)',
                                  'powerf(30, 50)',
                                  'powerf(50, 70)',
                                  'powerf(70, 120)',
                                  ],
                feature_time_functions = [np.min,np.max,np.mean,np.std,stats.kurtosis,stats.skew,
                                          lambda d:np.sum(np.abs(np.diff(d)))],
                feature_freq_functions=[powerf(1, 4),
                                        powerf(4, 8),
                                        powerf(8, 12),
                                        powerf(12, 30),
                                        powerf(30, 50),
                                        powerf(50, 70),
                                        powerf(70, 120)]
            )

    def extract_features_from_animal(self,animal):
        # Create feature files for each eeg file
        file_buffer = FileBuffer(animal)
        # Identify the time intervals and filenames to extract features
        for i,eeg_fname in enumerate(animal.eeg_files):
            feature_fname = '.'.join(eeg_fname.split('.')[:-1] + ['features'])
            feature_metafname = '.'.join(eeg_fname.split('.')[:-1] + ['fmeta'])
            time_range = [animal.eeg_init_time[i], animal.eeg_init_time[i]+animal.eeg_duration[i]]
            self.extract_features_from_time_range(file_buffer, time_range, feature_fname, feature_metafname)

    def extract_features_from_time_range(self, file_buffer, time_range, feature_fname, feature_metafname):
        window_step = self.settings['window_length']*(1-self.settings['overlap'])
        window_starts = np.arange(time_range[0], time_range[1], window_step)
        features = np.zeros(len(window_starts), self.settings['number_of_features'])
        for i, window_init in enumerate(window_starts):
            data, time = file_buffer.get_data_from_range([window_init, window_init + self.settings['window_length']]) # get all data from time window
            fs = 1/(time[1]-time[0])
            dataf = np.fft.rfft(data,axis=1)
            for j,func in enumerate(self.settings['feature_time_functions']):
                features[i,j] = func(data)
            n = j
            for j,func in enumerate(self.settings['feature_freq_functions']):
                features[i, j+n+1] = func(dataf, fs)

        metadata = OrderedDict(fs=1/window_step,
                               no_channels=self.settings['number_of_features'],
                               data_format=features.dtype,
                               volts_per_bit=0,
                               transmitter_id=str(file_buffer.animal.id),
                               start_timestamp_unix=time_range[0],
                               duration=time_range[1]-time_range[0],  # assume all h5 files have 1hr duration
                               channel_labels=self.settings['feature_labels'])

        with open(feature_metafname, 'w') as json_file:
            json.dump(metadata, json_file, indent=2, sort_keys=True)
        features.tofile(feature_fname)
