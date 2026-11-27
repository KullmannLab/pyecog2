"""
utility functions for upsampling
"""

import numpy as np
import logging
logger = logging.getLogger(__name__)


def get_modality_info(metadata):
    if 'modality_info' in metadata:
        return metadata['modality_info']

    # old .meta files only have volts_per_bit, so fallback to voltage
    logger.debug("No modality_info found, defaulting to voltage")
    return {
        'modality_type': 'voltage',
        'unit': 'V',
        'scale_factor': metadata.get('volts_per_bit', 1.0)
    }


def upsample_data(data, ratio, method='zero_order_hold'):
    """
    upsample data by zero order hold (repeating samples) or interpolating

    E.g: upsample_data(np.array([1, 2, 3]), ratio=4)
    Output: [1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3]
    """
    if ratio == 1:
        return data

    if method == 'zero_order_hold':
        # np.repeat copies each value `ratio` times
        axis = 0 if data.ndim > 1 else None
        return np.repeat(data, ratio, axis=axis)

    elif method == 'linear':
        old_indices = np.arange(len(data)) * ratio
        new_indices = np.arange(len(data) * ratio)

        if data.ndim == 1:
            return np.interp(new_indices, old_indices, data)
        else:
            # interpolating each channel separately
            upsampled = np.zeros((len(data) * ratio, data.shape[1]))
            for ch in range(data.shape[1]):
                upsampled[:, ch] = np.interp(new_indices, old_indices, data[:, ch])
            return upsampled

    else:
        raise ValueError(f"Unknown method: {method}. Use 'zero_order_hold' or 'linear'")
