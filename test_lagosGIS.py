import os
import sys
import arcpy
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import lagosGIS

arcpy.env.overwriteOutput = True

__all__ = ["lake_connectivity_classification", "zonal_attribution_of_raster_data"]

def lake_connectivity_classification(out_feature_class, debug_mode = True):
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    test_data_gdb = os.path.abspath(os.path.join(os.curdir, 'TestData_0411.gdb'))
    lagosGIS.lake_connectivity_classification(test_data_gdb, out_feature_class, debug_mode)

def zonal_attribution_of_raster_data(out_table, is_thematic = False, debug_mode = True):
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    test_data_gdb = os.path.abspath(os.path.join(os.curdir, 'TestData_0411.gdb'))
    zone_fc = os.path.join(test_data_gdb, 'HU12_raster')
    if is_thematic:
        in_value_raster = os.path.join(test_data_gdb, 'NLCD_LandCover_2006')
    else:
        in_value_raster = os.path.join(test_data_gdb, 'Total_Nitrogen_Deposition_2006')
    lagosGIS.zonal_attribution_of_raster_data(zone_fc, 'ZoneID', in_value_raster,
                                              out_table, is_thematic = is_thematic, debug_mode =  debug_mode)
# hand-verified to be correct
# update 2018-05-29, these numbers rely on the old method of using the source raster data grid instead of the
# common_grid.tif
hu12_7509_totalN_2006 = {"CELL_COUNT": 7, "MIN": 6.749966, "MAX": 7.41714, "MEAN": 7.026327, "STD": 0.226898}
hu12_7454_totalN_2006 = {"CELL_COUNT": None, "MIN": None, "MAX": None, "MEAN": None, "STD": None}

