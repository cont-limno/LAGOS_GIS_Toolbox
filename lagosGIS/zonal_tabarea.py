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
    if is_thematic:
        value_fields = arcpy.ListFields(t, "VALUE*")
        pct_fields = [f.name.replace("VALUE", "Pct") for f in value_fields]
        ha_fields = [f.name.replace("VALUE", "Ha") for f in value_fields]
        # add all the new fields needed
        # ha field does NOT add up to original feature area, cannot if vector inputs aren't used.
        # it's unnecessary--being dropped at the export stage. calculating for data QA only.
        for f, pct_field, ha_field in zip(value_fields, pct_fields, ha_fields):
            # find percent of total area in a new field
            arcpy.AddField_management(t, pct_field, f.type)
            arcpy.AddField_management(t, ha_field, f.type)

        value_field_names = [f.name for f in value_fields]
        cursor_fields = ['AREA'] + value_field_names + pct_fields + ha_fields
        print cursor_fields
        uCursor = arcpy.da.UpdateCursor(t, cursor_fields)
        for uRow in uCursor:
            # unpacks area + 3 tuples of the right fields for each, no matter how many there are
            vf_i_end = len(value_field_names)+1
            pf_i_end = vf_i_end + len(pct_fields)+1
            hf_i_end = pf_i_end + len(ha_fields)+1
            print uRow
            print vf_i_end
            print pf_i_end
            print hf_i_end
            # pct_values and ha_values are both null at this point but unpack for clarity
            area, value_values, pct_values, ha_values = uRow[0], uRow[1:vf_i_end], uRow[vf_i_end:pf_i_end], uRow[pf_i_end:hf_i_end]
            new_pct_values = [100*vv/area for vv in value_values]
            new_ha_values = [vv/10000 for vv in value_values] # convert square m to ha
            new_row = (area, value_values, new_pct_values, new_ha_values)
            uCursor.updateRow(new_row)

        for vf in value_field_names:
            arcpy.DeleteField_management(t, vf)

    arcpy.AlterField_management(t, 'COUNT', 'CELL_COUNT')
    drop_fields = ['ZONE_CODE', 'COUNT', 'AREA']
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

    # Set up environments for alignment between zone raster and theme raster
    this_files_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(this_files_dir)
    common_grid = os.path.abspath('../common_grid.tif')
    env.snapRaster = common_grid
    env.cellSize = common_grid
    CELL_SIZE = 30
    env.extent = zone_fc

    zone_desc = arcpy.Describe(zone_fc)
    zone_raster = 'convertraster'
    if zone_desc.dataType != 'RasterDataset':
        arcpy.PolygonToRaster_conversion(zone_fc, zone_field, zone_raster, 'CELL_CENTER', cellsize = CELL_SIZE)
    else:
        zone_raster = zone_fc

    # I tested and there is no need to resample the raster being summarized. It will be resampled correctly
    # internally in the following tool given that the necessary environments are set above (cell size, snap).
    #in_value_raster = arcpy.Resample_management(in_value_raster, 'in_value_raster_resampled', CELL_SIZE)
    if not is_thematic:
        arcpy.AddMessage("Calculating Zonal Statistics...")
        temp_entire_table = arcpy.sa.ZonalStatisticsAsTable(zone_raster, zone_field, in_value_raster, 'temp_zonal_table', 'DATA', 'MIN_MAX_MEAN')

    if is_thematic:
        #for some reason env.cellSize doesn't work
        # calculate/doit
        arcpy.AddMessage("Tabulating areas...")
        temp_entire_table = arcpy.sa.TabulateArea(zone_raster, zone_field, in_value_raster, 'Value', 'temp_area_table', CELL_SIZE)

        # replaces join to Zonal Stats in previous versions of tool
        # no joining, just calculate the area/count from what's produced by TabulateArea
        arcpy.AddField_management(temp_entire_table, 'AREA', 'LONG')
        arcpy.AddField_management(temp_entire_table, 'COUNT', 'LONG')

        cursor_fields = ['AREA', 'COUNT']
        value_fields = [f.name for f in arcpy.ListFields(temp_entire_table, 'VALUE*')]
        cursor_fields.extend(value_fields)
        with arcpy.da.UpdateCursor(temp_entire_table, cursor_fields) as uCursor:
            for uRow in uCursor:
                area, count, value_fields = uRow[0], uRow[1], uRow[2:]
                area = sum(value_fields)
                count = area/(CELL_SIZE*CELL_SIZE)
                new_row = [area, count] + value_fields
                uCursor.updateRow(new_row)

    arcpy.AddMessage("Refining output table...")

    arcpy.AddField_management(temp_entire_table, 'DataCoverage_pct', 'DOUBLE')

    # calculate DataCoverage_pct by comparing to original areas in zone raster
    # alternative to using JoinField, which is prohibitively slow if zones exceed hu12 count
    zone_raster_dict = {row[0]:row[1] for row in arcpy.da.SearchCursor(zone_raster, [zone_field, 'Count'])}
    temp_entire_table_dict = {row[0]:row[1] for row in arcpy.da.SearchCursor(temp_entire_table, [zone_field, 'COUNT'])}
    with arcpy.da.UpdateCursor(temp_entire_table, [zone_field, 'DataCoverage_Pct']) as cursor:
        for uRow in cursor:
            key_value, data_pct = uRow
            count_orig = zone_raster_dict[key_value]
            if key_value in temp_entire_table_dict:
                count_summarized = temp_entire_table_dict[key_value]
                data_pct = 100*float(count_summarized/count_orig)
            else:
                data_pct = None
            cursor.updateRow((key_value, data_pct))

    # Refine the output
    refine_zonal_output(temp_entire_table, zone_field, is_thematic)

    # final table gets a record even for no-data zones
    keep_fields = [f.name for f in arcpy.ListFields(temp_entire_table)]
    if zone_field.upper() in keep_fields:
        keep_fields.remove(zone_field.upper())
    if zone_field in keep_fields:
        keep_fields.remove(zone_field)

    # not needed as long we are working only with rasters
    # in order to add vector capabilities back, need to do something with this
    # right now we just can't fill in polygon zones that didn't convert to raster in our system
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

