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

def stats_area_table(zone_fc, zone_field, in_value_raster, out_table, is_thematic, warn_at_end = False):
    orig_env = arcpy.env.workspace
    arcpy.env.workspace = 'in_memory'
    arcpy.CheckOutExtension("Spatial")
    arcpy.AddMessage("Calculating zonal statistics...")

    # Set up environments for alignment between zone raster and theme raster
    env.snapRaster = in_value_raster
    env.cellSize = in_value_raster
    env.extent = zone_fc

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
        arcpy.sa.TabulateArea('convert_raster', zone_field, in_value_raster, 'Value', 'temp_area_table', cell_size)

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

    # final table gets a record even for no-data zones
    keep_fields = [f.name for f in arcpy.ListFields('zones_VAT')]
    if zone_field.upper() in keep_fields:
        keep_fields.remove(zone_field.upper())
    if zone_field in keep_fields:
        keep_fields.remove(zone_field)
    cu.one_in_one_out('zones_VAT', keep_fields, zone_fc, zone_field, out_table)

    # Convert missing "Pct_NoData" values to 100
    codeblock = """def convert_pct(arg1):
        if arg1 is None:
            return float(100)
        else:
            return arg1"""
    arcpy.CalculateField_management(out_table, 'Pct_NoData', 'convert_pct(!Pct_NoData!)', 'PYTHON_9.3', codeblock)

    # count whether all zones got an output record or not)
    out_count = int(arcpy.GetCount_management('temp_entire_table').getOutput(0))
    in_count = int(arcpy.GetCount_management(zone_fc).getOutput(0))
    count_diff = in_count - out_count

    # cleanup
    for item in ['temp_zonal_table', 'temp_entire_table', 'convert_raster', 'zones_VAT']:
        arcpy.Delete_management(item)
    arcpy.ResetEnvironments()
    arcpy.env.workspace = orig_env # hope this prevents problems using list of FCs from workspace as batch
    arcpy.CheckInExtension("Spatial")

    return [out_table, count_diff]

def handle_overlaps(zone_fc, zone_field, in_value_raster, out_table, is_thematic):
    overlap_grp_field = arcpy.ListFields(zone_fc, 'OVERLAP_GROUP*')
    total_count_diff = 0
    if overlap_grp_field:
        arcpy.AddMessage("Calculating zonal stats by overlap avoidance group. Expect repeated messages...")
        groups = list(set([row[0] for row in arcpy.da.SearchCursor(zone_fc, ['OVERLAP_GROUP'])]))
        i_out_tables = []
        for group in groups:
            i_zone_fc = 'in_memory/zones{}'.format(group)
            arcpy.Select_analysis(zone_fc, i_zone_fc, '"OVERLAP_GROUP" = {}'.format(group))
            i_out_table = 'in_memory/stats{}'.format(group)
            i_out_tables.append(i_out_table)
            result = stats_area_table(i_zone_fc, zone_field, in_value_raster, i_out_table, is_thematic, warn_at_end = True)
            total_count_diff += result[1]
        arcpy.Merge_management(i_out_tables, out_table)

    else:
        result = stats_area_table(zone_fc, zone_field, in_value_raster, out_table, is_thematic)
        total_count_diff = result[1]

    if total_count_diff > 0:
        warn_msg = ("WARNING: {0} zones have null zonal statistics. There are 3 possible reasons:\n"
                    "1) Presence of zones that are fully outside the extent of the raster summarized.\n"
                    "2) Overlapping zones in the input. Use Subset Overlapping Zones tool, then run again.\n"
                    "3) Zones are too small relative to the raster resolution.".format(total_count_diff))
        arcpy.AddWarning(warn_msg)

def main():
    zone_fc = arcpy.GetParameterAsText(0)
    zone_field = arcpy.GetParameterAsText(1)
    in_value_raster = arcpy.GetParameterAsText(2)
    out_table = arcpy.GetParameterAsText(4)
    is_thematic = arcpy.GetParameter(3) #boolean
    handle_overlaps(zone_fc, zone_field, in_value_raster, out_table, is_thematic)


def test(out_table, is_thematic = False):
    arcpy.env.overwriteOutput = True
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    test_data_gdb = os.path.abspath(os.path.join(os.pardir, 'TestData_0411.gdb'))
    zone_fc = os.path.join(test_data_gdb, 'HU12')
    zone_field = 'ZoneID'
    if is_thematic:
        in_value_raster = os.path.join(test_data_gdb, 'NLCD_LandCover_2006')
    else:
        in_value_raster = os.path.join(test_data_gdb, 'Total_Nitrogen_Deposition_2006')
    handle_overlaps(zone_fc, zone_field, in_value_raster, out_table, is_thematic)
    arcpy.env.overwriteOutput = False

if __name__ == '__main__':
    main()

