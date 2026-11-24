"""
conversion script for FigShare sleep dataset to separate files for multi modal support.

Reads original files:
- .dat files: sleep states, power spectra, EEG, EMG, and temperature
- .eeg files: raw 200 Hz EEG data

x_EEG_EMG.bin: EEG with EMG variance upsampled to 200 Hz through linear interpolation
x_Temperature.bin (sample every 4s), temperature (for EXP2 files)
x_SleepScore.bin (sample every 4s), categorical sleep states

Each .bin gets a .meta file with modality info
"""

import numpy as np
import os
import logging
from datetime import datetime
from pyecog2.ProjectClass import create_metafile_for_modality
from pyecog2.modality_utils import upsample_data
logger = logging.getLogger(__name__)

def readbinary_dat(file):
    """
    reads .dat file from the FigShare sleep dataset.

    within figshare dataset each file has 86400 records (one per 4 second epoch, 96 hours total).
    """
    record_dtype = np.dtype([
        ('score', 'S1'), # sleep state (wake, nrem, or rem)
        ('spectra', np.float32, (401,)),  # 401 power spectrum bins (0 to 100Hz at 0.25Hz)
        ('misc', np.float32, (3,)) # EEG, EMG variance and temp
    ])
    records = np.fromfile(file, dtype=record_dtype, count=86400)

    sleep_scores = ''.join(r.decode('utf-8') for r in records['score'])
    power_spectra = records['spectra']
    EEG_variance = records['misc'][:, 0]
    EMG_variance = records['misc'][:, 1]
    Temperature = records['misc'][:, 2].copy()  #only EXP2 files have temp included so copy to replace with empty array

    # assuming temp not recorded when 0 at the start
    if Temperature[0] == 0:
        Temperature = np.array([])

    logger.info(f"Read {file}: {len(sleep_scores)} epochs, temp recorded: {len(Temperature) > 0}")
    return sleep_scores, power_spectra, EEG_variance, EMG_variance, Temperature


def readbinary_EEG(file):
    """Read raw EEG binary file"""
    raw_EEG = np.fromfile(file, dtype=np.float32)
    logger.info(f"Read {file}: {len(raw_EEG)} samples ({len(raw_EEG)/200/3600:.1f} hours)")
    return raw_EEG


def encode_sleep_states(sleep_scores):
    """
    Clean epochs:'w' -> 1, 'n' -> 2, 'r' -> 3
    artefact codes map to 0  (remapped to state in post-conversion notebook)
    unknown characters map to 0
    """
    score_map = np.zeros(256, dtype=np.uint8)
    score_map[ord('w')] = 1
    score_map[ord('n')] = 2
    score_map[ord('r')] = 3
    return score_map[np.frombuffer(sleep_scores.encode(), dtype=np.uint8)]


def convert_animal_to_multimodal(dat_file, eeg_file, output_folder, animal_id=None):
    """
    Convert one animal's data into separate per modality .bin + .meta files.
    Returns dict mapping modality to its .meta file path.
    """
    if animal_id is None:
        animal_id = os.path.splitext(os.path.basename(dat_file))[0]

    logger.info(f"Converting {animal_id}")
    os.makedirs(output_folder, exist_ok=True)

    # power spectra not needed for conversion so discarding with _
    sleep_scores, _, EEG_var, EMG_var, Temperature = readbinary_dat(dat_file)

    # Same start time Marco used in his notebook
    start_timestamp = int(datetime(2023, 1, 1, 7, 0, 0).timestamp())
    duration = 96 * 3600  # seconds

    created_files = {}

    # EEG and EMG combined into single 2 channel .bin file
    # EMG variance upsampled from 0.25 to 200 Hz via linear interpolation
    eeg_data = readbinary_EEG(eeg_file)
    # converting from V^2 to V to be properly plotted alongside EEG
    emg_std = np.sqrt(EMG_var).astype(np.float32)
    emg_upsampled = upsample_data(emg_std, ratio=800, method='linear')

    # trimming to the same length
    n_samples = min(len(eeg_data), len(emg_upsampled))
    combined = np.column_stack([eeg_data[:n_samples],
                                emg_upsampled[:n_samples]]).astype(np.float32)

    combined_path = os.path.join(output_folder, f"{animal_id}_EEG_EMG.bin")
    combined.tofile(combined_path)
    created_files['EEG_EMG'] = create_metafile_for_modality(
        binary_file=combined_path, fs=200, no_channels=2, data_format='float32',
        start_timestamp_unix=start_timestamp, duration=duration,
        modality_type='voltage', unit='V', scale_factor=1.0,
        channel_labels=['EEG', 'EMG_std'], transmitter_id=animal_id
    )

    # temperature
    if len(Temperature) > 0:
        temp_path = os.path.join(output_folder, f"{animal_id}_Temperature.bin")
        Temperature.astype(np.float32).tofile(temp_path)
        created_files['Temperature'] = create_metafile_for_modality(
            binary_file=temp_path, fs=0.25, no_channels=1, data_format='float32',
            start_timestamp_unix=start_timestamp, duration=duration,
            modality_type='temperature', unit='°C', scale_factor=1.0,
            channel_labels=['Temperature'], transmitter_id=animal_id
        )
    else:
        logger.info(f"{animal_id}: temperature not recorded, skipping")

    # Sleep states
    sleep_path = os.path.join(output_folder, f"{animal_id}_SleepScore.bin")

    sleep_numeric = encode_sleep_states(sleep_scores)

    sleep_numeric.tofile(sleep_path)
    created_files['SleepScore'] = create_metafile_for_modality(
        binary_file=sleep_path, fs=0.25, no_channels=1, data_format='uint8',
        start_timestamp_unix=start_timestamp, duration=duration,
        modality_type='categorical', unit='categorical', scale_factor=1.0,
        channel_labels=['SleepScore'], transmitter_id=animal_id,
        categories={'wake': 1, 'NREM': 2, 'REM': 3, 'unknown': 0}
    )

    #logging sleep stage distribution
    for label, code in [('wake', 1), ('NREM', 2), ('REM', 3)]:
        logger.info(f"{label}: {np.sum(sleep_numeric == code)} epochs")

    return created_files


def convert_dataset(source_folder, output_folder):
    """
    Batch convert entire FigShare dataset.
    Scans for .dat/.eeg file pairs in source_folder subfolders and converts each animal.
    """
    import glob

    # trying subfolders first (e.g. data/M1EXP1/M1EXP1.dat)
    dat_files = glob.glob(os.path.join(source_folder, '*', '*.dat'))
    if not dat_files:
        dat_files = glob.glob(os.path.join(source_folder, '*.dat'))

    logger.info(f"found {len(dat_files)} animals to convert")

    converted = {}
    for dat_file in dat_files:
        eeg_file = dat_file.replace('.dat', '.eeg')
        if not os.path.exists(eeg_file):
            logger.warning(f"skipping {dat_file}: no matching .eeg file")
            continue

        animal_id = os.path.splitext(os.path.basename(dat_file))[0]
        try:
            converted[animal_id] = convert_animal_to_multimodal(
                dat_file, eeg_file, os.path.join(output_folder, animal_id), animal_id
            )
        except Exception as e:
            logger.error(f"Error converting {animal_id}: {e}")

    logger.info(f"Done: {len(converted)}/{len(dat_files)} animals converted")
    return converted


if __name__ == '__main__':
    import sys

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    if len(sys.argv) >= 3:
        convert_animal_to_multimodal(
            dat_file=sys.argv[1],
            eeg_file=sys.argv[2],
            output_folder=sys.argv[3] if len(sys.argv) > 3 else './converted'
        )
    else:
        print("Usage: python convert_figshare_sleep_data.py <dat_file> <eeg_file> [output_folder]")
        print("example: python convert_figshare_sleep_data.py M1EXP1.dat M1EXP1.eeg ./converted/M1EXP1")
