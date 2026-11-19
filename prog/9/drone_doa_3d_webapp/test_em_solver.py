import unittest
import numpy as np
from em_solver import fdtd_tmz, trace_geometry, segment_triangle_intersection, trace_reflected_scattered_paths

class GeometryTests(unittest.TestCase):
    def test_circle_proxy_blocks_segment(self):
        r=trace_geometry([0,0,0],[10,0,0],[{'id':'tree','kind':'tree','x':5,'z':0,'radius':1}])
        self.assertTrue(r['blocked']); self.assertEqual(r['hits'][0]['object'],'tree')
    def test_triangle_facet_intersection(self):
        tri=[[5,-1,-1],[5,1,-1],[5,0,1]]
        t=segment_triangle_intersection([0,0,0],[10,0,0],tri)
        self.assertIsNotNone(t); self.assertAlmostEqual(t,.5,places=5)
    def test_clear_segment(self):
        r=trace_geometry([0,0,0],[10,0,0],[{'id':'tree','x':5,'z':5,'radius':1}])
        self.assertFalse(r['blocked'])
    def test_scatter_candidate_is_returned(self):
        tri=[[[5,-1,-1],[5,1,-1],[5,0,1]]]
        r=trace_reflected_scattered_paths([0,0,0],[10,0,0],[{'id':'panel','triangles':tri}])
        self.assertGreater(len(r['scattered_paths']),0)
        self.assertEqual(len(r['scattered_paths'][0]['path']),3)

class FDTDTests(unittest.TestCase):
    def test_tmz_field_is_finite_and_bounded(self):
        r=fdtd_tmz(2.4e9,1.5,10,180,[{'id':'rock','kind':'rock','x':0,'z':0,'radius':.08,'material':{'epsilon_r':7,'conductivity_s_m':.008}}])
        a=np.asarray(r['field_normalized'])
        self.assertEqual(r['solver'],'2D TMz Yee-grid FDTD')
        self.assertTrue(np.isfinite(a).all()); self.assertGreater(a.max(),0); self.assertLessEqual(a.max(),1.0001)
        self.assertGreaterEqual(r['dt_s'],0); self.assertGreaterEqual(r['grid_nx'],64)

if __name__=='__main__': unittest.main()
