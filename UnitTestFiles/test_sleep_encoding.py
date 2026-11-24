"""
Unit tests for encoding sleep states in convert_figshare_sleep_data.py

Covers:
Correct uint8 codes for w, n, r
Artefact-flagged characters ('1'/'2'/'3') map to 0 before post-conversion remapping
Unknown characters map to 0
dtype, length, and behaviour on realistic inputs
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import unittest
import numpy as np
from pyecog2.convert_figshare_sleep_data import encode_sleep_states


class TestEncodeSleepStates(unittest.TestCase):
    def test_wake_maps_to_1(self):
        self.assertEqual(encode_sleep_states('w')[0], 1)

    def test_nrem_maps_to_2(self):
        self.assertEqual(encode_sleep_states('n')[0], 2)

    def test_rem_maps_to_3(self):
        self.assertEqual(encode_sleep_states('r')[0], 3)

    def test_artefact_wake_maps_to_zero(self):
        self.assertEqual(encode_sleep_states('1')[0], 0)

    def test_artefact_nrem_maps_to_zero(self):
        self.assertEqual(encode_sleep_states('2')[0], 0)

    def test_artefact_rem_maps_to_zero(self):
        self.assertEqual(encode_sleep_states('3')[0], 0)

    def test_unknown_character_maps_to_zero(self):
        self.assertEqual(encode_sleep_states('x')[0], 0)

    # output properties
    def test_output_dtype_is_uint8(self):
        self.assertEqual(encode_sleep_states('wnr').dtype, np.uint8)

    def test_output_length_matches_input_length(self):
        scores = 'wwnrwwnrww'
        self.assertEqual(len(encode_sleep_states(scores)), len(scores))


    def test_mixed_clean_sequence(self):
        np.testing.assert_array_equal(encode_sleep_states('wnr'), [1, 2, 3])

    def test_sequence_with_artefact_codes(self):
        # Artefact characters alongside clean states
        np.testing.assert_array_equal(encode_sleep_states('w1n2r3'), [1, 0, 2, 0, 3, 0])

    def test_all_wake_recording(self):
        scores = 'w' * 86400 #96 hour recording with 4s epochs
        result = encode_sleep_states(scores)
        self.assertEqual(len(result), 86400)
        self.assertTrue(np.all(result == 1))

    def test_no_silent_zero_bleed_on_long_sequence(self):
        scores = 'wnr' * 1000
        result = encode_sleep_states(scores)
        self.assertFalse(np.any(result == 0))


if __name__ == '__main__':
    unittest.main()
