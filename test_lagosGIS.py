import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import lagosGIS

__all__ = ["test_lake_connectivity_classification"]

def lake_connectivity_classification(out_feature_class, debug_mode = True):
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    test_data_gdb = os.path.abspath(os.path.join(os.curdir, 'TestData_0411.gdb'))
    lagosGIS.lake_connectivity_classification(test_data_gdb, out_feature_class, debug_mode)

def zonal_attribution_of_raster_data(out_table, debug_mode = True):
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    test_data_gdb = os.path.abspath(os.path.join(os.curdir, 'TestData_0411.gdb'))
    zone_fc = os.path.join(test_data_gdb, 'HU12')
    in_value_raster = os.path.join('Total_Nitrogen_Deposition_2006')
    lagosGIS.zonal_attribution_of_raster_data(zone_fc, 'ZoneID', in_value_raster,
                                              out_table, is_thematic = False, debug_mode =  debug_mode)