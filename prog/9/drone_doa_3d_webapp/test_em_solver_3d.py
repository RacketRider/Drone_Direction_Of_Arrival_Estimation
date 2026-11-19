import unittest
import numpy as np
from em_solver_3d import fdtd_3d

class TestFDTD3D(unittest.TestCase):
    def test_small_3d_grid_finite_and_courant(self):
        r=fdtd_3d(frequency_hz=2.4e9,size_m=0.30,steps=25,shape=(16,16,16))
        self.assertEqual(r['dimensions'],[16,16,16])
        self.assertTrue(r['finite_field'])
        self.assertTrue(np.isfinite(np.asarray(r['field_normalized'])).all())
        self.assertLessEqual(r['courant_number'],1.0)
        self.assertEqual(len(r['field_normalized']),16)
        self.assertEqual(len(r['field_normalized'][0]),16)
    def test_bounds_reject_oversized_grid(self):
        with self.assertRaises(ValueError): fdtd_3d(shape=(64,64,64))
if __name__=='__main__': unittest.main()
