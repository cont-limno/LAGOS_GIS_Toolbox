import datetime
import os
import tempfile
import xml.etree.ElementTree as ET
import arcpy
from arcpy import env
import csiutils as cu

def refine_zonal_output(t, zone_field, is_thematic, debug_mode = False):
    """Makes a nicer output for this tool. Rename some fields, drop unwanted
        ones, calculate percentages using raster AREA before deleting that
        field."""

    drop_fields = ['VALUE', 'COUNT', '{}_1'.format(zone_field), 'AREA', 'RANGE', 'SUM', 'ZONE_CODE', 'STD']
    if is_thematic:
        fields = arcpy.ListFields(t, "VALUE*")
        for f in fields:
            # find percent of total area in a new field
            pct_field = f.name.replace("VALUE", "Pct")
            arcpy.AddField_management(t, pct_field, f.type)
            expr = "100 * !%s!/!AREA!" % f.name
            arcpy.CalculateField_management(t, pct_field, expr, "PYTHON")

            # convert area to hectares in a new field
            # scale to match the area of the original feature!
            ha_field = f.name.replace("VALUE", "Ha")
            arcpy.AddField_management(t, ha_field, f.type)
            expr = "!%s!/10000" % f.name
            arcpy.CalculateField_management(t, ha_field, expr, "PYTHON")

            #Delete the old field
            if not debug_mode:
                arcpy.DeleteField_management(t, f.name)

    else:
        # continuous variables don't have these in the output
        drop_fields = drop_fields + ['VARIETY', 'MAJORITY', 'MINORITY', 'MEDIAN']

    arcpy.AlterField_management(t, 'COUNT_1', 'CELL_COUNT', 'CELL_COUNT')
    if not debug_mode:
        for df in drop_fields:
            try:
                arcpy.DeleteField_management(t, df)
            except:
                continue

def stats_area_table(zone_fc, zone_field, in_value_raster, out_table, is_thematic, debug_mode = False):
    orig_env = arcpy.env.workspace
    if debug_mode:
        arcpy.env.overwriteOutput = True
        temp_gdb = cu.create_temp_GDB('zonal_tabarea')
        arcpy.env.workspace = temp_gdb
        arcpy.AddMessage('Debugging workspace located at {}'.format(temp_gdb))
    else:
        arcpy.env.workspace = 'in_memory'
    arcpy.CheckOutExtension("Spatial")
    arcpy.AddMessage("Calculating zonal statistics...")

    # Set up environments for alignment between zone raster and theme raster
    env.snapRaster = '../common_grid.tif'
    env.cellSize = '../common_grid.tif'
    CELL_SIZE = 30
    env.extent = zone_fc

    zone_desc = arcpy.Describe(zone_fc)
    zone_raster = 'convertraster'
    if zone_desc.dataType != 'RasterDataset':
        arcpy.PolygonToRaster_conversion(zone_fc, zone_field, zone_raster, 'CELL_CENTER', cellsize = CELL_SIZE)
    else:
        zone_raster = zone_fc
    env.extent = "MINOF"

    # I tested and there is no need to resample the raster being summarized. It will be resampled correctly
    # internally in the following tool given that the necessary environments are set above (cell size, snap).
    in_value_raster = arcpy.Resample_management(in_value_raster, 'in_value_raster_resampled', CELL_SIZE)
    arcpy.sa.ZonalStatisticsAsTable(zone_raster, zone_field, in_value_raster, 'temp_zonal_table', 'DATA', 'ALL')

    if is_thematic:
        #for some reason env.cellSize doesn't work
        # calculate/doit
        arcpy.AddMessage("Tabulating areas...")
        arcpy.sa.TabulateArea(zone_raster, zone_field, in_value_raster, 'Value', 'temp_area_table', CELL_SIZE)

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
    arcpy.CopyRows_management(zone_raster, 'zones_VAT')
    arcpy.AddField_management('zones_VAT', 'DataCoverage_pct', 'DOUBLE')
    arcpy.JoinField_management('zones_VAT', zone_field, 'temp_entire_table', zone_field)
    calculate_expr = '100*(float(!COUNT_1!)/!Count!)'
    arcpy.CalculateField_management('zones_VAT', 'DataCoverage_pct', calculate_expr, "PYTHON")
    refine_zonal_output('zones_VAT', zone_field, is_thematic)

    # final table gets a record even for no-data zones
    keep_fields = [f.name for f in arcpy.ListFields('zones_VAT')]
    if zone_field.upper() in keep_fields:
        keep_fields.remove(zone_field.upper())
    if zone_field in keep_fields:
        keep_fields.remove(zone_field)
    cu.one_in_one_out('zones_VAT', keep_fields, zone_fc, zone_field, out_table)

    # Convert missing "DataCoverage_pct" values to 100
    codeblock = """def convert_pct(arg1):
        if arg1 is None:
            return float(0)
        else:
            return arg1"""
    arcpy.CalculateField_management(out_table, 'DataCoverage_pct', 'convert_pct(!DataCoverage_pct!)', 'PYTHON_9.3', codeblock)

    # count whether all zones got an output record or not)
    out_count = int(arcpy.GetCount_management('temp_entire_table').getOutput(0))
    in_count = int(arcpy.GetCount_management(zone_fc).getOutput(0))
    count_diff = in_count - out_count

    # cleanup
    if not debug_mode:
        for item in ['temp_zonal_table', 'temp_entire_table', 'in_memory', 'zones_VAT']:
            arcpy.Delete_management(item)
    arcpy.ResetEnvironments()
    arcpy.env.workspace = orig_env # hope this prevents problems using list of FCs from workspace as batch
    arcpy.CheckInExtension("Spatial")

    return [out_table, count_diff]

def handle_overlaps(zone_fc, zone_field, in_value_raster, out_table, is_thematic, debug_mode = False):
    # TODO: Add in debug_mode feature for this wrapper (for overlaps)
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
            result = stats_area_table(i_zone_fc, zone_field, in_value_raster, i_out_table, is_thematic, debug_mode)
            total_count_diff += result[1]
        arcpy.Merge_management(i_out_tables, out_table)

    else:
        result = stats_area_table(zone_fc, zone_field, in_value_raster, out_table, is_thematic, debug_mode)
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


# def test(out_table, is_thematic = False):
#     arcpy.env.overwriteOutput = True
#     os.chdir(os.path.dirname(os.path.abspath(__file__)))
#     test_data_gdb = os.path.abspath(os.path.join(os.pardir, 'TestData_0411.gdb'))
#     zone_fc = os.path.join(test_data_gdb, 'HU12')
#     zone_field = 'ZoneID'
#     if is_thematic:
#         in_value_raster = os.path.join(test_data_gdb, 'NLCD_LandCover_2006')
#     else:
#         in_value_raster = os.path.join(test_data_gdb, 'Total_Nitrogen_Deposition_2006')
#     handle_overlaps(zone_fc, zone_field, in_value_raster, out_table, is_thematic, debug_mode = True)
#     arcpy.env.overwriteOutput = False

if __name__ == '__main__':
    main()

