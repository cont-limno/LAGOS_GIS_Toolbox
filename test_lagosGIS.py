# filename: test_lagosGIS.py
# author: Nicole J Smith
# version: 2.0
# LAGOS module(s): all
# tool type: re-usable (NOT in ArcGIS Toolbox)

import os
import sys
from datetime import datetime
import arcpy
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import lagosGIS

os.chdir(os.path.dirname(os.path.abspath(__file__)))
TEST_DATA_GDB = os.path.abspath(os.path.join(os.curdir, 'TestData_0411.gdb'))
hu12 = os.path.join(TEST_DATA_GDB, 'hu12')

arcpy.env.overwriteOutput = True

__all__ = ["lake_connectivity_classification",
            "upstream_lakes",
            "locate_lake_outlets",
            "locate_lake_inlets",
            "aggregate_watersheds",
            "calc_watershed_subtype",

            "point_density_in_zones",
            "line_density_in_zones",
            "polygon_density_in_zones",
            "stream_density",
            "lake_density",

            "flatten_overlaps",
            "rasterize_zones",
            "zonal_summary_of_raster_data",
            "zonal_summary_of_classed_polygons",
            "point_attribution_of_raster_data",
            "summarize_raster_for_all_zones",
            "preprocess_padus",

            "export_to_csv"]


def lake_connectivity_classification(out_fc):
    lagosGIS.lake_connectivity_classification(TEST_DATA_GDB, out_fc)


def upstream_lakes(out_table):
    lagosGIS.upstream_lakes(TEST_DATA_GDB, out_table)


def locate_lake_outlets(out_fc):
    lagosGIS.locate_lake_outlets(TEST_DATA_GDB, out_fc)


def locate_lake_inlets(out_fc):
    lagosGIS.locate_lake_inlets(TEST_DATA_GDB, out_fc)


def aggregate_watersheds(out_fc):
    catchments_fc = os.path.join(TEST_DATA_GDB, 'catchments')
    lakes_fc = os.path.join(TEST_DATA_GDB, 'Lakes_1ha')
    lagosGIS.aggregate_watersheds(catchments_fc, TEST_DATA_GDB, lakes_fc, out_fc, mode='interlake')


def calc_watershed_subtype(out_fc):
    interlake_fc_orig = os.path.join(TEST_DATA_GDB, 'ws')
    interlake_fc = arcpy.CopyFeatures_management(interlake_fc_orig, out_fc)
    lagosGIS.calc_watershed_subtype(TEST_DATA_GDB, interlake_fc, fits_naming_standard=True)


def point_density_in_zones(out_table, selection_expression=''):
    points_fc = os.path.join(TEST_DATA_GDB, 'Dams')
    lagosGIS.point_density_in_zones(hu12, 'hu12_zoneid', points_fc, out_table, selection_expression)


def line_density_in_zones(out_table, selection_expression=''):
    lines_fc = os.path.join(TEST_DATA_GDB, 'lagos_streams')
    lagosGIS.point_density_in_zones(hu12, 'hu12_zoneid', lines_fc, out_table, selection_expression)


def polygon_density_in_zones(out_table, selection_expression=''):
    polygons_fc = os.path.join(TEST_DATA_GDB, 'Lakes_1ha')
    lagosGIS.polygon_density_in_zones(hu12, 'hu12_zoneid', polygons_fc, out_table, selection_expression)


def stream_density(out_table):
    lines_fc = os.path.join(TEST_DATA_GDB, 'lagos_streams')
    lagosGIS.stream_density(hu12, 'hu12_zoneid', lines_fc, out_table, zone_prefix='hu12')


def lake_density(out_table):
    polygons_fc = os.path.join(TEST_DATA_GDB, 'Lakes_1ha')
    lagosGIS.lake_density(hu12, 'hu12_zoneid', polygons_fc, out_table)


def flatten_overlaps(out_fc, out_table=''):
    if not out_table:
        out_table = out_fc + '_unflat'
    zones_fc = os.path.join(TEST_DATA_GDB, 'buff500')
    lagosGIS.flatten_overlaps(zones_fc, 'buff500_zoneid', out_fc, out_table)


def rasterize_zones(out_gdb):
    lagosGIS.rasterize_zones([hu12], out_gdb)


def zonal_summary_of_raster_data(out_table, overlaps=False, is_thematic=False):
    if overlaps:
        zone_fc = os.path.join(TEST_DATA_GDB, 'flatbuff500_raster')
        zone_field = 'flatbuff500_zoneid'
        unflat_table = os.path.join(TEST_DATA_GDB, 'buff500_unflat')
    else:
        zone_fc = os.path.join(TEST_DATA_GDB, 'hu12_raster')
        zone_field = 'hu12_zoneid'
        unflat_table = ''
    if is_thematic:
        in_value_raster = os.path.join(TEST_DATA_GDB, 'NLCD_LandCover_2006')
        rename_tag = 'nlcd2006'
        units=''
    else:
        in_value_raster = os.path.join(TEST_DATA_GDB, 'Total_Nitrogen_Deposition_2006')
        rename_tag = 'wetdepno3_2006'
        units = 'kgperha'
    lagosGIS.zonal_summary_of_raster_data(zone_fc, zone_field, in_value_raster, out_table, is_thematic=is_thematic,
                                        unflat_table=unflat_table, rename_tag=rename_tag, units=units)


def zonal_summary_of_classed_polygons(out_table):
    class_fc = os.path.join(TEST_DATA_GDB, 'padus_processed')
    lagosGIS.zonal_summary_of_classed_polygons(hu12, 'hu12_zoneid', class_fc, out_table, 'agency', 'agency')


def point_attribution_of_raster_data(out_table):
    zone_points = os.path.join(TEST_DATA_GDB, 'Lakes_1ha_Point')
    in_value_raster = os.path.join(TEST_DATA_GDB, 'Total_Nitrogen_Deposition_2006')
    lagosGIS.point_attribution_of_raster_data(zone_points, 'Permanent_Identifier', in_value_raster, out_table,
                                              'lake_wetdepinorgnitrogen', 'kgperha')


def summarize_raster_for_all_zones():
    pass


def preprocess_padus(out_fc):
    padus_original = os.path.join(TEST_DATA_GDB, 'padus_original')
    lagosGIS.preprocess_padus(padus_original, out_fc)


def export_to_csv(out_folder):
    in_table = os.path.join(TEST_DATA_GDB, 'buff500_unflat')
    lagosGIS.export_to_csv(in_table, out_folder)


def test_all(out_gdb):
    """
    Sets up tests for many tests in LAGOS GIS Toolbox using the test data included and saves the outputs to a common
    file geodatabase. Takes about 5 minutes to run.
    :param out_gdb: A file geodatabase to save the test outputs to.
    :return: None
    """

    if not arcpy.Exists(out_gdb):
        arcpy.CreateFileGDB_management(os.path.dirname(out_gdb), os.path.basename(out_gdb))
    dt_prefix = datetime.now().strftime("%b%d_%H%M")
    arcpy.AddMessage("All test files will start with date-time prefix {}".format(dt_prefix))
    for method in __all__:
        if method == 'rasterize_zones':
            eval_str = '''{}('{}')'''.format(method, out_gdb)
            arcpy.AddMessage('\n' + 'TESTING: ' + eval_str)
            eval(eval_str)
            old_name = os.path.join(out_gdb, 'hu12_raster')
            new_name = os.path.join(out_gdb, '{}_rasterize_zones'.format(dt_prefix))
            arcpy.Rename_management(old_name, new_name)
        elif method in ('summarize_raster_for_all_zones', 'export_to_csv'):
            continue # skip
        else:
            eval_str = '''{}(os.path.join('{}', '{}_{}'))'''.format(method, out_gdb, dt_prefix, method)
            arcpy.AddMessage('\n' + 'TESTING: ' + eval_str)
            eval(eval_str)


def main():
    out_gdb = arcpy.GetParameterAsText(0)
    test_all(out_gdb)


if __name__ == '__main__':
    main()