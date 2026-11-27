"""
Unit tests for modality_utils.py

Covers:
get_modality_info: both code paths (modality_info present / absent)
upsample_data: ZOH and linear, 1-D and 2-D, and edge cases
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import unittest
import numpy as np
from pyecog2.modality_utils import get_modality_info, upsample_data


class TestGetModalityInfo(unittest.TestCase):

    def test_returns_modality_info_block_when_present(self):
        block = {'modality_type': 'voltage', 'unit': 'V', 'scale_factor': 1.0}
        metadata = {'modality_info': block}
        self.assertEqual(get_modality_info(metadata), block)

    def test_modality_info_takes_precedence_over_volts_per_bit(self):
        # New-format files may still carry volts_per_bit for compat; modality_info wins.
        metadata = {
            'modality_info': {'modality_type': 'temperature', 'unit': '°C', 'scale_factor': 1.0},
            'volts_per_bit': 0.001,
        }
        result = get_modality_info(metadata)
        self.assertEqual(result['modality_type'], 'temperature')

    def test_fallback_returns_voltage_type_when_no_modality_info(self):
        metadata = {'volts_per_bit': 0.001}
        result = get_modality_info(metadata)
        self.assertEqual(result['modality_type'], 'voltage')
        self.assertEqual(result['unit'], 'V')

    def test_fallback_reads_volts_per_bit_as_scale_factor(self):
        metadata = {'volts_per_bit': 0.001}
        result = get_modality_info(metadata)
        self.assertAlmostEqual(result['scale_factor'], 0.001)

    def test_fallback_defaults_scale_factor_to_1_when_neither_field_present(self):
        # for bare metadata dict
        result = get_modality_info({})
        self.assertEqual(result['modality_type'], 'voltage')
        self.assertAlmostEqual(result['scale_factor'], 1.0)


class TestUpsampleData(unittest.TestCase):
    def test_ratio_one_returns_input_unchanged(self):
        data = np.array([1.0, 2.0, 3.0])
        np.testing.assert_array_equal(upsample_data(data, ratio=1), data)

    # zero order hold

    def test_zoh_output_length(self):
        data = np.array([1.0, 2.0, 3.0])
        self.assertEqual(len(upsample_data(data, ratio=4)), 12)

    def test_zoh_each_value_repeated_ratio_times(self):
        data = np.array([1.0, 2.0, 3.0])
        expected = np.array([1., 1., 1., 1., 2., 2., 2., 2., 3., 3., 3., 3.])
        np.testing.assert_array_equal(upsample_data(data, ratio=4), expected)

    # linear interpolation

    def test_linear_output_length(self):
        data = np.array([0.0, 1.0, 2.0])
        self.assertEqual(len(upsample_data(data, ratio=4, method='linear')), 12)

    def test_linear_preserves_first_value(self):
        data = np.array([5.0, 10.0, 15.0])
        result = upsample_data(data, ratio=4, method='linear')
        self.assertAlmostEqual(result[0], 5.0)

    def test_linear_preserves_last_value(self):
        data = np.array([5.0, 10.0, 15.0])
        result = upsample_data(data, ratio=4, method='linear')
        self.assertAlmostEqual(result[-1], 15.0)

    def test_linear_monotone_input_produces_monotone_output(self):
        data = np.arange(10, dtype=float)
        result = upsample_data(data, ratio=8, method='linear')
        self.assertTrue(np.all(np.diff(result) >= 0))

    def test_linear_ratio_800_output_length(self):
        # same as linear interpolation used implemented
        n_epochs = 100
        data = np.ones(n_epochs, dtype=np.float32)
        result = upsample_data(data, ratio=800, method='linear')
        self.assertEqual(len(result), n_epochs * 800)

    #multichannel
    def test_zoh_multichannel_shape(self):
        data = np.array([[1.0, 2.0], [3.0, 4.0]]) #2 epochs, 2 channels
        result = upsample_data(data, ratio=3)
        self.assertEqual(result.shape, (6, 2))

    def test_zoh_multichannel_values(self):
        data = np.array([[1.0, 2.0], [3.0, 4.0]])
        result = upsample_data(data, ratio=3)
        np.testing.assert_array_equal(result[:3], [[1., 2.]] * 3)
        np.testing.assert_array_equal(result[3:], [[3., 4.]] * 3)

    def test_linear_multichannel_shape(self):
        data = np.array([[0.0, 10.0], [2.0, 20.0]])
        result = upsample_data(data, ratio=2, method='linear')
        self.assertEqual(result.shape, (4, 2))

    def test_linear_multichannel_endpoints(self):
        data = np.array([[0.0, 10.0], [4.0, 40.0]])
        result = upsample_data(data, ratio=2, method='linear')
        self.assertAlmostEqual(result[0, 0], 0.0)
        self.assertAlmostEqual(result[0, 1], 10.0)

    # error handling

    def test_invalid_method_raises_value_error(self):
        data = np.array([1.0, 2.0, 3.0])
        with self.assertRaises(ValueError):
            upsample_data(data, ratio=4, method='nearest')


if __name__ == '__main__':
    unittest.main()
