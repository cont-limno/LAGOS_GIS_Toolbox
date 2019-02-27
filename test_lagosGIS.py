import os
import sys
import arcpy
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import lagosGIS

os.chdir(os.path.dirname(os.path.abspath(__file__)))
TEST_DATA_GDB = os.path.abspath(os.path.join(os.curdir, 'TestData_0411.gdb'))

arcpy.env.overwriteOutput = True

__all__ = ["lake_connectivity_classification",
           "zonal_attribution_of_raster_data",
           "polygons_in_zones",
           "lakes_in_zones",
           "interlake_watersheds_old",
           "interlake_watersheds_new"]

def lake_connectivity_classification(out_feature_class, debug_mode = True):
    lagosGIS.lake_connectivity_classification(TEST_DATA_GDB, out_feature_class, debug_mode)

def zonal_attribution_of_raster_data(out_table, is_thematic = False, debug_mode = True):
    zone_fc = os.path.join(TEST_DATA_GDB, 'HU12_raster')
    if is_thematic:
        in_value_raster = os.path.join(TEST_DATA_GDB, 'NLCD_LandCover_2006')
    else:
        in_value_raster = os.path.join(TEST_DATA_GDB, 'Total_Nitrogen_Deposition_2006')
    zone_field = arcpy.ListFields(zone_fc, '*zoneid')[0].name
    lagosGIS.zonal_attribution_of_raster_data(zone_fc, zone_field, in_value_raster,
                                              out_table, is_thematic = is_thematic, debug_mode =  debug_mode)
# hand-verified to be correct
# update 2018-05-29, these numbers rely on the old method of using the source raster data grid instead of the
# common_grid.tif
hu12_7509_totalN_2006 = {"CELL_COUNT": 7, "MIN": 6.749966, "MAX": 7.41714, "MEAN": 7.026327, "STD": 0.226898}
hu12_7454_totalN_2006 = {"CELL_COUNT": None, "MIN": None, "MAX": None, "MEAN": None, "STD": None}


def polygons_in_zones(out_table, selection_expression = ''):
    zone_fc = os.path.join(TEST_DATA_GDB, 'HU12')
    polygons_fc = os.path.join(TEST_DATA_GDB, 'Lakes_1ha')
    lagosGIS.polygons_in_zones(zone_fc, 'ZoneID', polygons_fc, out_table, selection_expression)

def lakes_in_zones(out_table):
    zone_fc = os.path.join(TEST_DATA_GDB, 'HU12')
    polygons_fc = os.path.join(TEST_DATA_GDB, 'Lakes_1ha')
    lagosGIS.lakes_in_zones(zone_fc, 'ZoneID', polygons_fc, out_table)

def interlake_watersheds_NE(out_fc):
    watersheds = os.path.join(TEST_DATA_GDB, 'Local_Catchments_Original_Methods')
    nhd_gdb = TEST_DATA_GDB
    eligible_lakes = os.path.join(TEST_DATA_GDB, 'eligible_lakes')
    lagosGIS.aggregate_watersheds_NE(watersheds, nhd_gdb, eligible_lakes, out_fc, mode = 'interlake')

def interlake_watersheds_US(out_fc):
    nhdplus_gdb = TEST_DATA_GDB
    eligible_lakes = os.path.join(TEST_DATA_GDB, 'eligible_lakes')
    lagosGIS.aggregate_watersheds_US(nhdplus_gdb, eligible_lakes, out_fc, mode = 'interlake')