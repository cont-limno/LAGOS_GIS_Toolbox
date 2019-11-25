import csv
import os
import arcpy
from arcpy import management as DM
from arcpy import analysis as AN
from arcpy import env
import csiutils as cu
import lagosGIS
from collections import defaultdict

def handle_overlaps(zone_fc, zone_field, zone_has_overlaps, in_value_raster, out_table, is_thematic,
                    rename_tag='', units='', debug_mode=False):
    orig_env = env.workspace
    if debug_mode:
        env.overwriteOutput = True
        temp_gdb = cu.create_temp_GDB('zonal_tabarea')
        env.workspace = temp_gdb
        arcpy.AddMessage('Debugging workspace located at {}'.format(temp_gdb))
    else:
        env.workspace = 'in_memory'
    arcpy.SetLogHistory(False)
    arcpy.CheckOutExtension("Spatial")
    
    def stats_area_table(zone_fc=zone_fc, zone_field=zone_field, in_value_raster=in_value_raster,
                         out_table=out_table, is_thematic=is_thematic):
        def refine_zonal_output(t):
            """Makes a nicer output for this tool. Rename some fields, drop unwanted
                ones, calculate percentages using raster AREA before deleting that
                field."""
            if is_thematic:
                value_fields = arcpy.ListFields(t, "VALUE*")
                pct_fields = ['{}_pct'.format(f.name) for f in
                              value_fields]  # VALUE_41_pct, etc. Field can't start with number.

                # add all the new fields needed
                for f, pct_field in zip(value_fields, pct_fields):
                    arcpy.AddField_management(t, pct_field, f.type)

                # calculate the percents
                cursor_fields = ['AREA'] + [f.name for f in value_fields] + pct_fields
                uCursor = arcpy.da.UpdateCursor(t, cursor_fields)
                for uRow in uCursor:
                    # unpacks area + 3 tuples of the right fields for each, no matter how many there are
                    vf_i_end = len(value_fields) + 1
                    pf_i_end = vf_i_end + len(pct_fields)

                    # pct_values and ha_values are both null at this point but unpack for clarity
                    area, value_values, pct_values = uRow[0], uRow[1:vf_i_end], uRow[vf_i_end:pf_i_end]
                    new_pct_values = [100 * vv / area for vv in value_values]
                    new_row = [area] + value_values + new_pct_values
                    uCursor.updateRow(new_row)

                for vf in value_fields:
                    arcpy.DeleteField_management(t, vf.name)

            arcpy.AlterField_management(t, 'COUNT', 'CELL_COUNT')
            drop_fields = ['ZONE_CODE', 'COUNT', 'AREA']
            if not debug_mode:
                for df in drop_fields:
                    try:
                        arcpy.DeleteField_management(t, df)
                    except:
                        continue

        # Set up environments for alignment between zone raster and theme raster
        this_files_dir = os.path.dirname(os.path.abspath(__file__))
        os.chdir(this_files_dir)
        common_grid = os.path.abspath('../common_grid.tif')
        env.snapRaster = common_grid
        env.cellSize = common_grid

        env.extent = zone_fc

        zone_desc = arcpy.Describe(zone_fc)
        zone_raster = 'convertraster'
        if zone_desc.dataType not in ['RasterDataset', 'RasterLayer']:
            zone_raster = arcpy.PolygonToRaster_conversion(zone_fc, zone_field, zone_raster, 'CELL_CENTER',
                                                           cellsize=env.cellSize)
            print('cell size is {}'.format(env.cellSize))
        else:
            zone_raster = zone_fc
            env.cellSize = zone_raster
            print('cell size is {}'.format(env.cellSize))

        # I tested and there is no need to resample the raster being summarized. It will be resampled correctly
        # internally in the following tool given that the necessary environments are set above (cell size, snap).
        # # in_value_raster = arcpy.Resample_management(in_value_raster, 'in_value_raster_resampled', CELL_SIZE)
        if not is_thematic:
            arcpy.AddMessage("Calculating Zonal Statistics...")
            temp_entire_table = arcpy.sa.ZonalStatisticsAsTable(zone_raster, zone_field, in_value_raster,
                                                                'temp_zonal_table', 'DATA', 'MEAN')

        if is_thematic:
            # for some reason env.cellSize doesn't work
            # calculate/doit
            arcpy.AddMessage("Tabulating areas...")
            temp_entire_table = arcpy.sa.TabulateArea(zone_raster, zone_field, in_value_raster, 'Value',
                                                      'temp_area_table', processing_cell_size = env.cellSize)
            # TabulateArea capitalizes the zone for some annoying reason and ArcGIS is case-insensitive to field names
            # so we have this work-around:
            zone_field_t = '{}_t'.format(zone_field)
            DM.AddField(temp_entire_table, zone_field_t, 'TEXT', field_length = 20)
            expr = '!{}!'.format(zone_field.upper())
            DM.CalculateField(temp_entire_table, zone_field_t, expr, 'PYTHON')
            DM.DeleteField(temp_entire_table, zone_field.upper())
            DM.AlterField(temp_entire_table, zone_field_t, zone_field, clear_field_alias=True)

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
                    count = round(area / (int(env.cellSize) * int(env.cellSize)), 0)
                    new_row = [area, count] + value_fields
                    uCursor.updateRow(new_row)

        arcpy.AddMessage("Refining output table...")

        arcpy.AddField_management(temp_entire_table, 'datacoveragepct', 'DOUBLE')
        arcpy.AddField_management(temp_entire_table, 'ORIGINAL_COUNT', 'LONG')

        # calculate datacoveragepct by comparing to original areas in zone raster
        # alternative to using JoinField, which is prohibitively slow if zones exceed hu12 count
        zone_raster_dict = {row[0]: row[1] for row in arcpy.da.SearchCursor(zone_raster, [zone_field, 'Count'])}
        temp_entire_table_dict = {row[0]: row[1] for row in
                                  arcpy.da.SearchCursor(temp_entire_table, [zone_field, 'COUNT'])}
        with arcpy.da.UpdateCursor(temp_entire_table, [zone_field, 'datacoveragepct', 'ORIGINAL_COUNT']) as cursor:
            for uRow in cursor:
                key_value, data_pct, count_orig = uRow
                count_orig = zone_raster_dict[key_value]
                if key_value in temp_entire_table_dict:
                    count_summarized = temp_entire_table_dict[key_value]
                    data_pct = 100 * float(count_summarized / count_orig)
                else:
                    data_pct = None
                cursor.updateRow((key_value, data_pct, count_orig))

        # Refine the output
        refine_zonal_output(temp_entire_table)

        # in order to add vector capabilities back, need to do something with this
        # right now we just can't fill in polygon zones that didn't convert to raster in our system
        out_table = cu.one_in_one_out(temp_entire_table, zone_fc, zone_field, out_table)

        # Convert "datacoveragepct" and "ORIGINAL_COUNT" values to 0 for zones with no metrics calculated
        with arcpy.da.UpdateCursor(out_table,
                                   [zone_field, 'datacoveragepct', 'ORIGINAL_COUNT', 'CELL_COUNT']) as u_cursor:
            for row in u_cursor:
                # data_coverage pct to 0
                if row[1] is None:
                    row[1] = 0
                # original count filled in if a) zone outside raster bounds or b) zone too small to be rasterized
                if row[2] is None:
                    if row[0] in zone_raster_dict:
                        row[2] = zone_raster_dict[row[0]]
                    else:
                        row[2] = 0
                # cell count set to 0
                if row[3] is None:
                    row[3] = 0
                u_cursor.updateRow(row)

        # count whether all zones got an output record or not)
        out_count = int(arcpy.GetCount_management(temp_entire_table).getOutput(0))
        in_count = int(arcpy.GetCount_management(zone_fc).getOutput(0))
        count_diff = in_count - out_count

        # cleanup
        if not debug_mode:
            for item in ['temp_zonal_table', temp_entire_table, 'convertraster']:  # don't add zone_raster, orig
                arcpy.Delete_management(item)
        arcpy.ResetEnvironments()
        env.workspace = orig_env  # hope this prevents problems using list of FCs from workspace as batch
        arcpy.CheckInExtension("Spatial")

        return [out_table, count_diff]
    
    def flatten_overlaps():
        objectid = [f.name for f in arcpy.ListFields(zone_fc) if f.type == 'OID'][0]
        zone_type = [f.type for f in arcpy.ListFields(zone_fc, zone_field)][0]
        fid1 = 'FID_{}'.format(os.path.basename(zone_fc))
        fid2 = fid1 + '_1'
        flat_zoneid = 'flat{}'.format(zone_field)
        flat_zoneid_prefix = 'flat{}_'.format(zone_field.replace('_zoneid', ''))

        # Union with FID_Only (A)
        arcpy.AddMessage("Splitting overlaps in polygons...")
        zoneid_dict = {r[0]: r[1] for r in arcpy.da.SearchCursor(zone_fc, [objectid, zone_field])}
        self_union = AN.Union([zone_fc, zone_fc], 'self_union', 'ONLY_FID')
        # overlap_regions = arcpy.Select_analysis(self_union, 'overlap_regions', '{} <> {}'.format(fid1, fid2))
        # geom_check = arcpy.CheckGeometry_management(overlap_regions, 'geom_check')


        # Add the original zone ids and save to table (E)
        arcpy.AddMessage("Assigning temporary IDs to split polygons...")
        unflat_table = DM.CopyRows(self_union, 'unflat_table')
        DM.AddField(unflat_table, zone_field, zone_type)  # default text length of 50 is fine if needed
        with arcpy.da.UpdateCursor(unflat_table, [fid1, zone_field]) as u_cursor:
            for row in u_cursor:
                row[1] = zoneid_dict[row[0]]  # assign zone id
                u_cursor.updateRow(row)

        # Find Identical by Shape (B)
        identical_shapes = DM.FindIdentical(self_union, 'identical_shapes', 'Shape')

        # Join A to B and calc flat[zone]_zoneid = FEAT_SEQ (C)
        DM.AddField(self_union, flat_zoneid, 'TEXT', field_length=20)
        identical_shapes_dict = {r[0]: r[1] for r in arcpy.da.SearchCursor(identical_shapes, ['IN_FID', 'FEAT_SEQ'])}
        with arcpy.da.UpdateCursor(self_union, [objectid, flat_zoneid]) as u_cursor:
            for row in u_cursor:
                row[1] = '{}{}'.format(flat_zoneid_prefix, identical_shapes_dict[row[0]])
                u_cursor.updateRow(row)

        # Add the original zone ids and save to table (E)
        unflat_table = DM.CopyRows(self_union, 'unflat_table')
        DM.AddField(unflat_table, zone_field, zone_type)  # default text length of 50 is fine if needed
        with arcpy.da.UpdateCursor(unflat_table, [fid1, zone_field]) as u_cursor:
            for row in u_cursor:
                row[1] = zoneid_dict[row[0]]  # assign zone id
                u_cursor.updateRow(row)

        # Delete Identical (C) (save as flat[zone])
        flatzone = DM.CopyFeatures(self_union, 'flatzone')
        flatzone = DM.DeleteIdentical(flatzone, flat_zoneid)
        DM.Delete(self_union)  # large and we're done with it

        # Run Stats tool on C (D)
        flatzone_stats_table = stats_area_table('flatzone', flat_zoneid, in_value_raster, 'temp_out_table', is_thematic)
        count_diff = flatzone_stats_table[1]
        flatzone_stats_table = flatzone_stats_table[0]

        # Set up the output table (can't do this until the prior tool is run)
        if os.path.dirname(out_table):
            out_path = os.path.dirname(out_table)
        else:
            out_path = orig_env

        result = DM.CreateTable(out_path, os.path.basename(out_table))

        # get the fields to add to the table
        editable_fields = [f for f in arcpy.ListFields(flatzone_stats_table)
                           if f.editable and f.name.lower() != flat_zoneid.lower()]

        # populate the new table schema
        DM.AddField(result, zone_field, zone_type)
        for f in editable_fields:
            DM.AddField(result, f.name, f.type, field_length=f.length)

        # map original zone ids to new zone ids
        original_flat = defaultdict(list)
        with arcpy.da.SearchCursor(unflat_table, [zone_field, flat_zoneid]) as cursor:
            for row in cursor:
                if row[1] not in original_flat[row[0]]:
                    original_flat[row[0]].append(row[1])

        # Use CELL_COUNT as weight for means to calculate final values for each zone.
        fixed_fields = [zone_field, 'ORIGINAL_COUNT', 'CELL_COUNT', 'datacoveragepct']
        other_field_names = [f.name for f in editable_fields if f.name not in fixed_fields]
        i_cursor = arcpy.da.InsertCursor(result, fixed_fields + other_field_names)  # open output table cursor
        flat_stats = {r[0]: r[1:] for r in arcpy.da.SearchCursor(
            flatzone_stats_table, [flat_zoneid, 'ORIGINAL_COUNT', 'CELL_COUNT', 'datacoveragepct'] + other_field_names)}

        for zid, unflat_ids in original_flat.items():
            area_vec = [flat_stats[id][0] for id in unflat_ids]  # ORIGINAL_COUNT specified in 0 index earlier
            cell_vec = [flat_stats[id][1] for id in unflat_ids]
            coverage_vec = [flat_stats[id][2] for id in unflat_ids]  # datacoveragepct special handling
            stat_vectors_by_id = [flat_stats[id][3:] for id in unflat_ids]  # "the rest", list of lists

            # calc the new summarized values
            original_count = sum(filter(None, area_vec))  # None area is functionally equivalent to 0, all Nones = 0 too
            cell_count = sum(filter(None, cell_vec))
            if cell_count > 0:
                weighted_coverage = sum([a * b for a, b in zip(area_vec, coverage_vec)]) / original_count

                # this calculation accounts for fractional missing values, both kinds (whole zone is no data, or zone
                # was missing some data and had data coverage % < 100). This is done by converting None to 0
                # and by using the cell_count (count of cells with data present)
                # instead of the full zone original_count. You have to do both or the mean will be distorted.
                # hand-verification that this works as intended using test GIS data on was completed 2019-11-01 by NJS
                crossprods = []
                for i in range(0, len(unflat_ids)):
                    crossprods.append([cell_vec[i] * float(s or 0) for s in stat_vectors_by_id[i]])

                weighted_stat_means = []
                for i in range(0, len(other_field_names)):
                    weighted_stat_means.append(sum(zip(*crossprods)[i]) / cell_count)
            else:
                weighted_coverage = 0
                weighted_stat_means = [None] * len(other_field_names)

            new_row = [zid, original_count, cell_count, weighted_coverage] + weighted_stat_means
            i_cursor.insertRow(new_row)
        del i_cursor

        for item in [unflat_table, identical_shapes, 'flatzone', flatzone, flatzone_stats_table]:
            DM.Delete(item)

        return [result, count_diff]
    
    if zone_has_overlaps:
        result = flatten_overlaps()
    else:
        result= stats_area_table()
    out_table = result[0]
    total_count_diff = result[1]

    # rename things (LAGOS standard), if desired
    if rename_tag:
        arcpy.AddMessage("Renaming.")
        # datacoverage just gets tag
        new_datacov_name = '{}_datacoveragepct'.format(rename_tag)
        cu.rename_field(out_table, 'datacoveragepct', new_datacov_name, deleteOld=True)
        #DM.AlterField(out_table, 'datacoveragepct', new_datacov_name, clear_field_alias=True)
        if not is_thematic:
            new_mean_name = '{}_{}'.format(rename_tag, units).rstrip('_') # if no units, just rename_tag
            DM.AlterField(out_table, 'MEAN', new_mean_name, clear_field_alias=True)
        else:
            # look up the values based on the rename tag
            geo_file = os.path.abspath('../geo_metric_provenance.csv')
            with open(geo_file) as csv_file:
                reader = csv.DictReader(csv_file)
                mapping = {row['subgroup_original_code']: row['subgroup']
                             for row in reader if row['main_feature'] in rename_tag}
                print(mapping)

            # update them
            for old, new in mapping.items():
                old_fname= 'VALUE_{}_pct'.format(old)
                new_fname = '{}_{}_pct'.format(rename_tag, new)
                try:
                    # same problem with AlterField limit of 31 characters here.
                    #DM.AlterField(out_table, old_fname, new_fname, clear_field_alias=True)
                    cu.rename_field(out_table, old_fname, new_fname, deleteOld=True)
                except:
                    pass # sometimes not all values are included in the output table

    if total_count_diff > 0:
        warn_msg = ("WARNING: {0} zones have null zonal statistics. There are 2 possible reasons:\n"
                    "1) Presence of zones that are fully outside the extent of the raster summarized.\n"
                    "2) Zones are too small relative to the raster resolution.".format(total_count_diff))
        arcpy.AddWarning(warn_msg)

    arcpy.SetLogHistory(True)

    return out_table

def main():
    zone_fc = arcpy.GetParameterAsText(0)
    zone_field = arcpy.GetParameterAsText(1)
    zone_has_overlaps = arcpy.GetParameter(2) # boolean
    in_value_raster = arcpy.GetParameterAsText(3)
    is_thematic = arcpy.GetParameter(4) # boolean
    out_table = arcpy.GetParameterAsText(5)
    rename_tag = arcpy.GetParameterAsText(6) # optional
    units = arcpy.GetParameterAsText(7) # optional

    handle_overlaps(zone_fc, zone_field, zone_has_overlaps, in_value_raster, out_table, is_thematic,
                    rename_tag, units)

if __name__ == '__main__':
    main()