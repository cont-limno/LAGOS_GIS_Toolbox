import datetime
import os
import tempfile
import xml.etree.ElementTree as ET
import arcpy
from arcpy import env
import csiutils as cu

def refine_zonal_output(t, zone_field, is_thematic):
    """Makes a nicer output for this tool. Rename some fields, drop unwanted
        ones, calculate percentages using raster AREA before deleting that
        field."""

    drop_fields = ['VALUE', 'COUNT', '{}_1'.format(zone_field), 'COUNT_1', 'AREA', 'RANGE', 'SUM', 'ZONE_CODE']
    if is_thematic:
        fields = arcpy.ListFields(t, "VALUE*")
        for f  in fields:
            # convert area to hectares in a new field
            ha_field = f.name.replace("VALUE", "Ha")
            arcpy.AddField_management(t, ha_field, f.type)
            expr = "!%s!/10000" % f.name
            arcpy.CalculateField_management(t, ha_field, expr, "PYTHON")

            # find percent of total area in a new field
            pct_field = f.name.replace("VALUE", "Pct")
            arcpy.AddField_management(t, pct_field, f.type)
            expr = "100 * !%s!/!AREA!" % f.name
            arcpy.CalculateField_management(t, pct_field, expr, "PYTHON")

            #Delete the old field
            arcpy.DeleteField_management(t, f.name)

    else:
        # continuous variables don't have these in the output
        drop_fields = drop_fields + ['VARIETY', 'MAJORITY', 'MINORITY', 'MEDIAN']

    for df in drop_fields:
        try:
            arcpy.DeleteField_management(t, df)
        except:
            continue

def stats_area_table(zone_fc, zone_field, in_value_raster, out_table, is_thematic):
    orig_env = arcpy.env.workspace
    arcpy.env.workspace = 'in_memory'
    arcpy.CheckOutExtension("Spatial")
    arcpy.AddMessage("Calculating zonal statistics...")

    # Set up environments for alignment between zone raster and theme raster
    env.snapRaster = in_value_raster
    env.cellSize = in_value_raster
    env.extent = zone_fc


    # Convert polygons to raster in memory

    # TODO: If we experience errors again, add a try/except where the except writes the
    # conversion raster to a scratch workspace instead, that eliminated the errors we
    # we getting several years ago with 10.1, not sure if they will happen still.

    arcpy.PolygonToRaster_conversion(zone_fc, zone_field, 'convert_raster', 'MAXIMUM_AREA')
    env.extent = "MINOF"
    arcpy.sa.ZonalStatisticsAsTable('convert_raster', zone_field, in_value_raster, 'temp_zonal_table', 'DATA', 'ALL')

    if is_thematic:
        #for some reason env.cellSize doesn't work
        desc = arcpy.Describe(in_value_raster)
        cell_size = desc.meanCelLHeight

        # calculate/doit
        arcpy.AddMessage("Tabulating areas...")
        arcpy.sa.TabulateArea('convert_raster', zone_field, in_value_raster,
                                'Value', 'temp_area_table', cell_size)

        # making the output table
        arcpy.CopyRows_management('temp_area_table', 'temp_entire_table')
        zonal_stats_fields = ['COUNT', 'AREA']
        arcpy.JoinField_management('temp_entire_table', zone_field, 'temp_zonal_table', zone_field, zonal_stats_fields)

        # cleanup
        arcpy.Delete_management('temp_area_table')

    if not is_thematic:
        # making the output table
        arcpy.CopyRows_management('temp_zonal_table', 'temp_entire_table')

    arcpy.AddMessage("Refining output table...")

    # Join to the input zones raster
    arcpy.AddField_management('convert_raster', 'Pct_NoData', 'DOUBLE')
    arcpy.CopyRows_management('convert_raster', 'zones_VAT')
    arcpy.JoinField_management('zones_VAT', zone_field, 'temp_entire_table', zone_field)
    calculate_expr = '100*(1-(float(!COUNT_1!)/!Count!))'
    arcpy.CalculateField_management('zones_VAT', 'Pct_NoData', calculate_expr, "PYTHON")
    refine_zonal_output('zones_VAT', zone_field, is_thematic)

    # count whether all zones got an output record or not)
    out_count = int(arcpy.GetCount_management('temp_entire_table').getOutput(0))
    in_count = int(arcpy.GetCount_management(zone_fc).getOutput(0))
    count_diff = in_count - out_count
    if count_diff > 0:
        warn_msg = ("WARNING: {0} zones have null zonal statistics. This can be because the zones are too small"
                    "relative to the raster resolution. It can also be due to overlapping input zones (use the Subset"
                    "Overlapping Zones tool to fix).").format(count_diff)

        arcpy.AddWarning(warn_msg)
        print(warn_msg)

    # cleanup
    arcpy.ResetEnvironments()
    arcpy.env.workspace = orig_env # hope this prevents problems using list of FCs from workspace as batch
    for item in ['temp_zonal_table', 'temp_entire_table', 'convert_raster', 'zones_VAT']:
        arcpy.Delete_management(item)
    arcpy.CheckInExtension("Spatial")

    return [out_table, count_diff]

def handle_overlaps(zone_fc, zone_field, in_value_raster, out_table, is_thematic):
    overlap_grp_field = arcpy.ListFields(zone_fc, 'OVERLAP_GROUP*')
    if overlap_grp_field:
        groups = list(set([row[0] for row in arcpy.da.SearchCursor(zone_fc, ['OVERLAP_GROUP'])]))
        i_out_tables = []
        for group in groups:
            i_zone_fc = arcpy.Select_analysis(zone_fc, '"OVERLAP_GROUP" = {}'.format(group))
            i_out_table = 'in_memory/stats{}'.format(group)
            i_out_tables.append(i_out_table)
            stats_area_table(i_zone_fc, zone_field, in_value_raster, i_out_table, is_thematic)
        arcpy.Merge_management(i_out_tables, out_table)

    else:
        stats_area_table(zone_fc, zone_field, in_value_raster, out_table, is_thematic)


def main():
    zone_fc = arcpy.GetParameterAsText(0)
    zone_field = arcpy.GetParameterAsText(1)
    in_value_raster = arcpy.GetParameterAsText(2)
    out_table = arcpy.GetParameterAsText(4)
    is_thematic = arcpy.GetParameter(3) #boolean
    stats_area_table(zone_fc, zone_field, in_value_raster, out_table, is_thematic)


def test():
    test_gdb = r'C:\Users\smithn78\PycharmProjects\LAGOS_GIS_Toolbox\TestData_0411.gdb'
    zone_fc = r'C:\Users\smithn78\PycharmProjects\LAGOS_GIS_Toolbox\TestData_0411.gdb\HU12'
    zone_field = 'ZoneID'
    in_value_raster = r'C:\Users\smithn78\PycharmProjects\LAGOS_GIS_Toolbox\TestData_0411.gdb\Total_Nitrogen_Deposition_2006'
    out_table =  r'C:\Users\smithn78\Documents\ArcGIS\Default.gdb\test_zonal_stats_metadata'
    is_thematic = False
    stats_area_table(zone_fc, zone_field, in_value_raster, out_table, is_thematic)

if __name__ == '__main__':
    main()
