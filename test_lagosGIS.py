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
            "calc_watershed_equality",

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

            "spatialize_lakes",
            "georeference_lakes",

            "export_to_csv"]


def lake_connectivity_classification(out_feature_class):
    lagosGIS.lake_connectivity_classification(TEST_DATA_GDB, out_feature_class)


def upstream_lakes(out_table):
    lagosGIS.upstream_lakes(TEST_DATA_GDB, out_table)


def locate_lake_outlets(out_fc):
    lagosGIS.locate_lake_outlets(TEST_DATA_GDB, out_fc)


def locate_lake_inlets(out_fc):
    lagosGIS.locate_lake_inlets(TEST_DATA_GDB, out_fc)


def aggregate_watersheds(out_fc):
    pass


def calc_watershed_subtype():
    pass


def calc_watershed_equality():
    pass


def point_density_in_zones(out_table, selection_expression=''):
    points_fc = os.path.join(TEST_DATA_GDB, 'Dams')
    lagosGIS.point_density_in_zones(hu12, 'hu12_zoneid', points_fc, out_table, selection_expression)


def line_density_in_zone(out_table, selection_expression=''):
    lines_fc = os.path.join(TEST_DATA_GDB, 'Streams')
    lagosGIS.point_density_in_zones(hu12, 'hu12_zoneid', lines_fc, out_table, selection_expression)


def polygon_density_in_zones(out_table, selection_expression=''):
    polygons_fc = os.path.join(TEST_DATA_GDB, 'Lakes_1ha')
    lagosGIS.polygon_density_in_zones(hu12, 'ZoneID', polygons_fc, out_table, selection_expression)


def stream_density(out_table):
    lines_fc = os.path.join(TEST_DATA_GDB, 'Streams')
    lagosGIS.stream_density(hu12, 'hu12_zoneid', lines_fc, out_table, zone_prefix='hu12')


def lake_density(out_table):
    polygons_fc = os.path.join(TEST_DATA_GDB, 'Lakes_1ha')
    lagosGIS.lake_density(hu12, 'hu12_zoneid', polygons_fc, out_table)


def flatten_overlaps(out_fc, out_table):
    zones_fc = os.path.join(TEST_DATA_GDB, 'buff500')
    lagosGIS.flatten_overlaps(zones_fc, 'buff500_zoneid', out_fc, out_table)


def rasterize_zones():
    lagosGIS.rasterize_zones([hu12], TEST_DATA_GDB)


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


def zonal_summary_of_classed_polygons():
    pass


def point_attribution_of_raster_data(out_table):
    zone_points = os.path.join(TEST_DATA_GDB, 'Lakes_1ha_Point')
    in_value_raster = os.path.join(TEST_DATA_GDB, 'Total_Nitrogen_Deposition_2006')
    lagosGIS.attribution(zone_points, 'Permanent_Identifier', in_value_raster, out_table,
                                              'lake_wetdepinorgnitrogen', 'kgperha')


def summarize_raster_for_all_zones():
    pass


def preprocess_padus():
    pass


def spatialize_lakes():
    pass


def georeference_lakes():
    pass


def export_to_csv():
    pass


def test_all(out_gdb):
    if not arcpy.Exists(out_gdb):
        arcpy.CreateFileGDB_management(os.path.dirname(out_gdb), os.path.basename(out_gdb))
    dt_prefix = datetime.now().strftime("%b%d_%H%M")
    print("All test files will start with date-time prefix {}".format(dt_prefix))
    lake_connectivity_classification()
    upstream_lakes()
    locate_lake_outlets()
    locate_lake_inlets()
    aggregate_watersheds()
    calc_watershed_subtype()
    calc_watershed_equality()

    point_density_in_zones()
    line_density_in_zone()
    polygon_density_in_zones()
    stream_density()
    lake_density()

    flatten_overlaps()
    rasterize_zones()
    zonal_summary_of_raster_data()
    zonal_summary_of_classed_polygons()
    point_attribution_of_raster_data()
    summarize_raster_for_all_zones()
    preprocess_padus()

    spatialize_lakes()
    georeference_lakes()

    export_to_csv()