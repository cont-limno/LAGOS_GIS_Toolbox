import os
import arcpy
from arcpy import management as DM
from arcpy import analysis as AN
from arcpy import env
import csiutils as cu
import lagosGIS
from collections import defaultdict

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
        uCursor = arcpy.da.UpdateCursor(t, cursor_fields)
        for uRow in uCursor:
            # unpacks area + 3 tuples of the right fields for each, no matter how many there are
            vf_i_end = len(value_field_names)+1
            pf_i_end = vf_i_end + len(pct_fields)

            # pct_values and ha_values are both null at this point but unpack for clarity
            area, value_values, pct_values, ha_values = uRow[0], uRow[1:vf_i_end], uRow[vf_i_end:pf_i_end], uRow[pf_i_end:]
            new_pct_values = [100*vv/area for vv in value_values]
            new_ha_values = [vv/10000 for vv in value_values] # convert square m to ha
            new_row = [area] + value_values + new_pct_values + new_ha_values
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
    # # in_value_raster = arcpy.Resample_management(in_value_raster, 'in_value_raster_resampled', CELL_SIZE)
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
        arcpy.AddField_management(temp_entire_table, 'AREA', 'DOUBLE')
        arcpy.AddField_management(temp_entire_table, 'COUNT', 'DOUBLE')

        cursor_fields = ['AREA', 'COUNT']
        value_fields = [f.name for f in arcpy.ListFields(temp_entire_table, 'VALUE*')]
        cursor_fields.extend(value_fields)
        with arcpy.da.UpdateCursor(temp_entire_table, cursor_fields) as uCursor:
            for uRow in uCursor:
                area, count, value_fields = uRow[0], uRow[1], uRow[2:]
                area = sum(value_fields)
                count = round(area/(CELL_SIZE*CELL_SIZE), 0)
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
        zone_field = zone_field.upper()
    if zone_field in keep_fields:
        keep_fields.remove(zone_field)

    # not needed as long we are working only with rasters
    # in order to add vector capabilities back, need to do something with this
    # right now we just can't fill in polygon zones that didn't convert to raster in our system
    cu.one_in_one_out(temp_entire_table, keep_fields, zone_fc, zone_field, out_table)

    # Convert "DataCoverage_pct" values to 0 for zones with no metrics calculated
    codeblock = """def convert_pct(arg1):
        if arg1 is None:
            return float(0)
        else:
            return arg1"""
    arcpy.CalculateField_management(out_table, 'DataCoverage_pct', 'convert_pct(!DataCoverage_pct!)', 'PYTHON_9.3', codeblock)

    # count whether all zones got an output record or not)
    out_count = int(arcpy.GetCount_management(temp_entire_table).getOutput(0))
    in_count = int(arcpy.GetCount_management(zone_fc).getOutput(0))
    count_diff = in_count - out_count

    # cleanup
    if not debug_mode:
        for item in ['temp_zonal_table', 'convertraster']:
            arcpy.Delete_management(item)
    arcpy.ResetEnvironments()
    arcpy.env.workspace = orig_env # hope this prevents problems using list of FCs from workspace as batch
    arcpy.CheckInExtension("Spatial")

    return [out_table, count_diff]

def flatten_overlaps(fc_with_overlapping_polygons, zone_id, in_value_raster, out_table, is_thematic):
    orig_workspace = arcpy.env.workspace
    arcpy.env.workspace = 'in_memory'
    objectid = [f.name for f in arcpy.ListFields(fc_with_overlapping_polygons) if f.type == 'OID'][0]
    zone_type = [f.type for f in arcpy.ListFields(fc_with_overlapping_polygons, zone_id)][0]
    fid1 = 'FID_{}'.format(os.path.basename(fc_with_overlapping_polygons))
    fid2 = fid1 + '_1'
    flat_zoneid = 'flat{}_zoneid'.format(os.path.basename(fc_with_overlapping_polygons))
    flat_zoneid_prefix = 'flat{}_'.format(os.path.basename(fc_with_overlapping_polygons))

    # Set up the output table
    if os.path.dirname(out_table):
        out_path = os.path.dirname(out_table)
    else:
        out_path = orig_workspace

    result = DM.CreateTable(out_path, os.path.basename(out_table))
    DM.AddField(result, zone_id, zone_type)
    DM.AddField(result, 'CELL_COUNT', 'LONG')
    DM.AddField(result, 'MEAN', 'DOUBLE')
    DM.AddField(result, 'DataCoverage_pct', 'DOUBLE')

    # Union with FID_Only (A)
    zoneid_dict = {r[0]:r[1] for r in arcpy.da.SearchCursor(fc_with_overlapping_polygons, [objectid, zone_id])}
    self_union = AN.Union([fc_with_overlapping_polygons, fc_with_overlapping_polygons], 'self_union', 'ONLY_FID')

    # Add the original zone ids and save to table (E)
    unflat_table = DM.CopyRows(self_union, 'unflat_table')
    DM.AddField(unflat_table, zone_id, zone_type) # default text length of 50 is fine if needed
    with arcpy.da.UpdateCursor(unflat_table, [fid1, zone_id]) as u_cursor:
        for row in u_cursor:
            row[1] = zoneid_dict[row[0]] # assign zone id
            u_cursor.updateRow(row)

    # Find Identical by Shape (B)
    identical_shapes = DM.FindIdentical(self_union, 'identical_shapes', 'Shape')

    # Join A to B and calc flat[zone]_zoneid = FEAT_SEQ (C)
    DM.AddField(self_union, flat_zoneid, 'TEXT', field_length=20)
    identical_shapes_dict = {r[0]:r[1] for r in arcpy.da.SearchCursor(identical_shapes, ['IN_FID', 'FEAT_SEQ'])}
    with arcpy.da.UpdateCursor(self_union, [objectid, flat_zoneid]) as u_cursor:
        for row in u_cursor:
            row[1] = '{}{}'.format(flat_zoneid_prefix, identical_shapes_dict[row[0]])
            u_cursor.updateRow(row)

    # Add the original zone ids and save to table (E)
    unflat_table = DM.CopyRows(self_union, 'unflat_table')
    DM.AddField(unflat_table, zone_id, zone_type) # default text length of 50 is fine if needed
    with arcpy.da.UpdateCursor(unflat_table, [fid1, zone_id]) as u_cursor:
        for row in u_cursor:
            row[1] = zoneid_dict[row[0]] # assign zone id
            u_cursor.updateRow(row)

    # Delete Identical (C) (save as flat[zone])
    DM.CopyFeatures(self_union, 'flatzone')
    DM.DeleteIdentical('flatzone', flat_zoneid)
    DM.Delete(self_union) # large and we're done with it

    # Run Stats tool on C (D)
    flatzone_stats_table = stats_area_table('flatzone', flat_zoneid, in_value_raster, 'temp_out_table', is_thematic)
    count_diff = flatzone_stats_table[1]
    flatzone_stats_table = flatzone_stats_table[0]


    # map original zone ids to new zone ids
    original_flat = defaultdict(list)
    with arcpy.da.SearchCursor(unflat_table, [zone_id, flat_zoneid]) as cursor:
        for row in cursor:
            if row[1] not in original_flat[row[0]]:
                original_flat[row[0]].append(row[1])

    # Use CELL_COUNT as weight for means to calculate final values for each zone.
    i_cursor = arcpy.da.InsertCursor(result, [zone_id, 'CELL_COUNT', 'MEAN', 'DataCoverage_pct']) # open output table cursor
    flat_stats = {r[0]:r[1:] for r in arcpy.da.SearchCursor(flatzone_stats_table, [flat_zoneid, 'CELL_COUNT', 'MEAN', 'DataCoverage_pct'])}

    for zid, unflat_ids in original_flat.items():
        area_vec = [float(flat_stats[id][0]) for id in unflat_ids] # CELL_COUNT
        mean_vec = [flat_stats[id][1] for id in unflat_ids] # MEAN
        pct_vec = [flat_stats[id][2] for id in unflat_ids] # DataCoverage_pct
        weighted_mean = sum([a*b for a,b in zip(area_vec, mean_vec)])/sum(area_vec)
        weighted_pct = sum([a*b for a,b in zip(area_vec, pct_vec)])/sum(area_vec)
        cell_count = sum(area_vec)
        i_cursor.insertRow((zid, cell_count, weighted_mean, weighted_pct))

    del i_cursor

    for item in [unflat_table, identical_shapes, 'flatzone', flatzone_stats_table]:
        DM.Delete(item)

    return [result, count_diff]

def handle_overlaps(zone_fc, zone_field, zone_has_overlaps, in_value_raster, out_table, is_thematic, debug_mode = False):
    if zone_has_overlaps:
        out_table = flatten_overlaps(zone_fc, zone_field, in_value_raster, out_table, is_thematic)
    else:
        out_table = stats_area_table(zone_fc, zone_field, in_value_raster, out_table, is_thematic, debug_mode)

    total_count_diff = out_table[1]

    if total_count_diff > 0:
        warn_msg = ("WARNING: {0} zones have null zonal statistics. There are 2 possible reasons:\n"
                    "1) Presence of zones that are fully outside the extent of the raster summarized.\n"
                    "2) Zones are too small relative to the raster resolution.".format(total_count_diff))
        arcpy.AddWarning(warn_msg)
    return out_table

def main():
    zone_fc = arcpy.GetParameterAsText(0)
    zone_field = arcpy.GetParameterAsText(1)
    zone_has_overlaps = arcpy.GetParameter(2) # boolean
    in_value_raster = arcpy.GetParameterAsText(3)
    out_table = arcpy.GetParameterAsText(5)
    is_thematic = arcpy.GetParameter(4) # boolean
    handle_overlaps(zone_fc, zone_field, zone_has_overlaps, in_value_raster, out_table, is_thematic)

if __name__ == '__main__':
    main()

