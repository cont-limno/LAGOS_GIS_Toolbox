import os
import arcpy
from collections import Counter
from arcpy import analysis as AN
from arcpy import management as DM
import lagosGIS

# Change these to match your computer. Yes, this is a crap way to code this.
MASTER_LAKES_FC = 'NHDWaterbody_LAGOS'
MASTER_LAKES_LINES = 'NHDWaterbody_LAGOS_Line'
MASTER_STREAMS_FC = 'NHDArea_LAGOS'

# Can change but probably don't need to
MASTER_LAKE_ID = 'lagoslakeid'
MASTER_GNIS_NAME = "GNIS_Name"
#MASTER_STREAM_ID = 'Permanent_Identifier' #hard-coded below
MASTER_COUNTY_NAME = 'COUNTY_NAME'
MASTER_STATE_NAME = 'STATE'
STATES = ("AK","AL","AR","AZ","CA","CO","CT","DC","DE","FL","GA","GU","HI","IA","ID", "IL","IN","KS","KY","LA","MA",
          "MD","ME","MH","MI","MN","MO","MS","MT","NC","ND","NE","NH","NJ","NM","NV","NY", "OH","OK","OR","PA","PR",
          "PW","RI","SC","SD","TN","TX","UT","VA","VI","VT","WA","WI","WV","WY")
CRS_DICT = {'NAD83':4269,
            'WGS84':4326,
            'NAD27':4267
            }


def spatialize_lakes(lake_points_csv, out_fc, in_x_field, in_y_field, in_crs = 'NAD83'):
    """
    Casts xy data as spatial points.
    :param lake_points_csv: The lake water quality dataset containing coordinates as text columns.
    :param out_fc: The output feature class
    :param in_x_field: Field containing the longitude or x coordinates
    :param in_y_field: Field containing the latitude or y coordinates
    :param in_crs: Abbreviation of the coordinate reference system used to specify the coordinates.

    Options supported are 'WGS84', 'NAD83', 'NAD27.
    :return: The output feature class
    """

    if in_crs not in CRS_DICT.keys():
        raise ValueError('Use one of the following CRS names: {}'.format(','.join(CRS_DICT.keys())))
    DM.MakeXYEventLayer(lake_points_csv, in_x_field, in_y_field, 'xylayer', arcpy.SpatialReference(CRS_DICT[in_crs]))
    arcpy.env.outputCoordinateSystem = arcpy.SpatialReference(102039)
    DM.CopyFeatures('xylayer', out_fc)
    arcpy.Delete_management('xylayer')
    return(out_fc)

def georeference_lakes(lake_points_fc, out_fc, lake_id_field,
                       lake_name_field, lake_county_field = '', state = '',
                       master_gdb=r'C:\Users\smithn78\Dropbox\CL_HUB_GEO\Lake_Georeferencing\Masters_for_georef.gdb'
                       ):
    """
    Evaluate water quality sampling point locations and either assign the point to a lake polygon or flag the
    point for manual review.
    :param lake_points_fc:
    :param out_fc:
    :param lake_id_field:
    :param lake_name_field:
    :param lake_county_field:
    :param state:
    :param master_gdb: Location of master geodatabase used for linking
    :return:
    """
    master_lakes_fc = os.path.join(master_gdb, MASTER_LAKES_FC)
    master_lakes_lines = os.path.join(master_gdb, MASTER_LAKES_LINES)
    master_streams_fc = os.path.join(master_gdb, MASTER_STREAMS_FC)

    # setup
    arcpy.AddMessage("Joining...")
    if state and state.upper() not in STATES:
        raise ValueError('Use the 2-letter state code abbreviation')
    arcpy.env.workspace = 'in_memory'
    out_short = os.path.splitext(os.path.basename(out_fc))[0]
    join1 = '{}_1'.format(out_short)
    join2 = '{}_2'.format(out_short)
    join3 = '{}_3'.format(out_short)
    join3_select = join3 + '_select'
    join4 = '{}_4'.format(out_short)
    join5 = '{}_5'.format(out_short)
    freq = 'frequency_of_lake_id'

    county_name_results = arcpy.ListFields(lake_points_fc, '{}*'.format(lake_county_field))[0].name
    if lake_county_field and not lake_county_field in county_name_results:
        print('{} field does not exist in dataset.'.format(lake_county_field))
        raise Exception

    point_fields = [f.name for f in arcpy.ListFields(lake_points_fc)]

    # If identifier matches a LAGOS lake in the crosswalk, then do these steps
    # TODO: Finish the crosswalk so you can use this step

    # Try to make some spatial connections and fulfill some logic to assign a link
    join1 = AN.SpatialJoin(lake_points_fc, master_lakes_fc, join1, 'JOIN_ONE_TO_MANY', 'KEEP_ALL', match_option = 'INTERSECT')
    join2 = AN.SpatialJoin(join1, master_streams_fc, join2, 'JOIN_ONE_TO_MANY', 'KEEP_ALL', match_option = 'INTERSECT')
    join3 = AN.SpatialJoin(join2, master_lakes_fc, join3, 'JOIN_ONE_TO_MANY', 'KEEP_ALL', match_option = 'INTERSECT', search_radius = '10 meters')
    join4 = AN.SpatialJoin(join3, master_lakes_fc, join4, 'JOIN_ONE_TO_MANY', 'KEEP_ALL', match_option = 'INTERSECT', search_radius =  '100 meters')

    # TODO: Add back frequency thing
    # freq = AN.Frequency(join4, freq, lake_id_field)

    # setup for editing lake assignment values
    DM.AddField(join4, 'Auto_Comment', 'TEXT', field_length = 100)
    DM.AddField(join4, 'Manual_Review', 'SHORT')
    DM.AddField(join4, 'Shared_Words', 'TEXT', field_length = 100)
    DM.AddField(join4, 'Linked_lagoslakeid', 'LONG')
    DM.AddField(join4, 'GEO_Discovered_Name', 'TEXT', field_length = 255)
    DM.AddField(join4, 'Duplicate_Candidate', 'TEXT', field_length = 1)

    update_fields = [lake_id_field, lake_name_field,  MASTER_LAKE_ID, MASTER_GNIS_NAME, # 0m match
                     'PERMANENT_IDENTIFIER_1', 'GNIS_NAME_1', # stream match
                     MASTER_LAKE_ID + '_1', MASTER_GNIS_NAME +'_12', # 10m match
                     MASTER_LAKE_ID + '_12', MASTER_GNIS_NAME + '_12_13', # 100m match
                     'Auto_Comment', 'Manual_Review', 'Shared_Words',
                     'Linked_lagoslakeid']
    all_fields = [f.name for f  in arcpy.ListFields(join4)]

    # use a cursor to go through each point and evaluate its assignment
    cursor = arcpy.da.UpdateCursor(join4, update_fields)
    arcpy.AddMessage("Calculating link status...")
    for row in cursor:
        id, name, mid_0, mname_0, stream_id, streamname_0, mid_10, mname_10, mid_100, mname_100, comment, review, words, lagosid = row
        if mid_0 is not None: # if the point is directly in a polygon
            if name and mname_0:
                words = lagosGIS.list_shared_words(name, mname_0, exclude_lake_words=False)
            comment = 'Exact location link'
            lagosid = mid_0
            review = -1
        elif mid_0 is None and mid_10 is not None: # if the point is only within 10m of a lake
            if name and mname_10:
                words = lagosGIS.list_shared_words(name, mname_10, exclude_lake_words=False)
            if words:
                comment = 'Linked by common name and location'
                lagosid = mid_10
                review = -1
            else:
                comment = 'Linked by common location'
                lagosid = mid_10
                review = 1
        elif mid_0 is None and mid_10 is None:
            if stream_id is not None: # if there is a stream match
                comment = 'Not linked because represented as river in NHD'
                review = 2
            else:
                if mid_100 is not None: # if the point is only within 100m of lake(s)
                    if name and mname_100:
                        words = lagosGIS.list_shared_words(name, mname_100, exclude_lake_words=True)
                # TODO: Frequency check
                    if words:
                        comment = 'Linked by common name and location'
                        lagosid = mid_100
                        review = 1
                    else:
                        comment = 'Linked by common location'
                        lagosid = mid_100
                        review = 2
        cursor.updateRow((id, name, mid_0, mname_0, stream_id, streamname_0, mid_10, mname_10, mid_100, mname_100, comment, review, words, lagosid))

    # # So I haven't been able to get the county logic to work and it hasn't been that important yet, ignore for now
    # Select down to a minimum set because we're about to join on county, which will create lots of duplicate matches
    # Then join calculated results back to full set
    # if lake_county_field:
    #     join5 = AN.Select(join4, join5, 'Manual_Review IS NULL')
    #     lakes_state = AN.Select(MASTER_LAKES_FC, 'lakes_state', "{0} = '{1}'".format(MASTER_STATE_NAME, state))
    #     lakes_state_lyr = DM.MakeFeatureLayer(lakes_state, 'lakes_state_lyr')
    #     join5_lyr = DM.MakeFeatureLayer(join5, 'join5_lyr')
    #     DM.AddJoin(join5_lyr, lake_county_field, lakes_state_lyr, MASTER_COUNTY_NAME)
    #     join5_with_county = DM.CopyFeatures(join5_lyr, 'join5_with_cty')
    #     j5 = 'DEDUPED_CA_SWAMP_data_linked_5.'
    #
    #     county_update_fields = [j5 + lake_id_field, j5 + lake_name_field, j5 + lake_county_field,
    #                             'lakes_state.' + MASTER_LAKE_ID, 'lakes_state.' + MASTER_GNIS_NAME, 'lakes_state.' + MASTER_COUNTY_NAME,
    #                             j5 + 'Auto_Comment', j5 + 'Manual_Review', j5 + 'Shared_Words',
    #                             j5 + 'Linked_lagoslakeid']
    #     with arcpy.da.UpdateCursor(join5_lyr, county_update_fields) as cursor:
    #         for row in cursor:
    #             id, name, county, mid_cty, mname_cty, mcounty, comment, review, words, lagosid = row
    #             if county is not None and mcounty is not None:
    #                 if name and mname_cty:
    #                     words = lagosGIS.list_shared_words(name, mname_cty, exclude_lake_words=True)
    #                 if words:
    #                     comment = 'PRELIMINARY: Linked by common name and location'
    #                     lagosid = mid_cty
    #                     review = 2
    #             cursor.updateRow((id, name, county, mid_cty, mname_cty, mcounty, comment, review, words, lagosid))
    #     DM.RemoveJoin(join5_lyr)
    #     join5_with_county = DM.CopyFeatures(join5_lyr, 'join5_with_county')
    #
    #     # join5 = DM.JoinField(join5, lake_county_field, lakes_state, MASTER_COUNTY_NAME,
    #                          fields = [MASTER_COUNTY_NAME, MASTER_LAKE_ID, MASTER_GNIS_NAME])
    #
    #     # This is a long way to make a join
    #     join_dict = {}
    #     with arcpy.da.SearchCursor(lakes_state, [MASTER_COUNTY_NAME, MASTER_LAKE_ID, MASTER_GNIS_NAME]) as cursor:
    #         for row in cursor:
    #             join_value, val1, val2 = row
    #             join_dict[join_value] = [val1, val2]
    #
    #     arcpy.AddField_management(join5, MASTER_LAKE_ID + 'cntyj', 'LONG')
    #     arcpy.AddField_management(join5, MASTER_GNIS_NAME + 'cntyj', 'TEXT', 255)
    #
    #     with arcpy.da.SearchCursor(join5, [lake_county_field, MASTER_LAKE_ID + 'cntyj', MASTER_GNIS_NAME + 'cntyj']) as cursor:
    #         for row in cursor:
    #             key_value = row[0]
    #             words = lagosGIS.list_shared_words()
    #             if join_dict.has_key(key_value):
    #                 row[1] = join_dict[key_value][0]
    #                 row[2] = join_dict[key_value][1]
    #             else:
    #                 row[1] = None
    #                 row[2] = None
    #             cursor.updateRow(row)
    #
    #
    #     county_update_fields = [lake_id_field, lake_name_field, lake_county_field,
    #                 MASTER_LAKE_ID + '_12_13_14', MASTER_GNIS_NAME + '_12_13',  MASTER_COUNTY_NAME + '_12_13', # county
    #                  'Auto_Comment', 'Manual_Review', 'Shared_Words',
    #                  'Linked_lagoslakeid']
    #     cursor = arcpy.da.UpdateCursor(join5, county_update_fields)
    #     for row in cursor:
    #         id, name, county, lagosid_cty, lagosname_cty, mcounty, comment, mreview, words, linked_lagosid = row
    #         if mcounty is not None:
    #             words = lagosGIS.list_shared_words()
    # else:
    #     join5 = join4
    #
    # # Undo the next line if you ever bring this chunk back.
    join5 = join4

    # then re-code the no matches as a 3 and copy comments to the editable field
    # compress the joined lake ids into one field
    # having two fields lets us keep track of how many of the auto matches are bad
    DM.AddField(join5, 'Comment', 'TEXT', field_length=100)
    with arcpy.da.UpdateCursor(join5, ['Manual_Review', 'Auto_Comment', 'Comment']) as cursor:
        for flag, ac, comment in cursor:
            if flag is None:
                flag = 3
                ac = 'Not linked'
            comment = ac
            cursor.updateRow((flag, ac, comment))

    # Re-code points more than 100m into the polygon of the lake as no need to check
    DM.MakeFeatureLayer(join5, 'join5_lyr')
    DM.MakeFeatureLayer(master_lakes_lines, 'lake_lines_lyr')
    DM.SelectLayerByLocation('join5_lyr', 'INTERSECT', 'lake_lines_lyr', '100 meters', 'NEW_SELECTION', 'INVERT')
    DM.SelectLayerByAttribute('join5_lyr', 'REMOVE_FROM_SELECTION', "Auto_Comment LIKE 'Not linked%'")
    DM.CalculateField('join5_lyr', 'Manual_Review', '-2', 'PYTHON')
    DM.Delete('join5_lyr', 'lake_lines_lyr')

    # Then make sure to only keep the fields necessary when you write to an output
    copy_fields = point_fields + ['Linked_lagoslakeid', 'Auto_Comment', 'Manual_Review',
                                  'Shared_Words', 'Comment', 'Duplicate_Candidate', 'GEO_Discovered_Name']
    copy_fields.remove('Shape')
    copy_fields.remove('OBJECTID')

    lagosGIS.select_fields(join5, out_fc, copy_fields)

    DM.AssignDomainToField(out_fc, 'Comment', 'Comment')

    DM.AddField(out_fc, 'Total_points_in_lake_poly', 'Short')

    # Remove any duplicates. (These originate from the join3/join4 transition because a point can be both
    # within 10m and 100m of lakes, this code takes the closest lake as true for my current sanity.)
    # Or, in other words, this is a hack solution.
    out_fc_fields = [f.name for f in arcpy.ListFields(out_fc) if f.name != 'OBJECTID']
    DM.DeleteIdentical(out_fc, out_fc_fields)

    # Get the join_count for each limno lake ID
    # De-dupe anything resulting from limno ID duplicates first before counting
    id_pairs = list(set(arcpy.da.SearchCursor(out_fc, [lake_id_field, 'Linked_lagoslakeid'])))
    # THEN pull out LAGOS id. Any duplicate now are only due to multiple distinct points within lake
    lagos_ids = [ids[1] for ids in id_pairs]
    sample_ids = [ids[0] for ids in id_pairs]
    lagos_lake_counts = Counter(lagos_ids)
    linked_multiple_lake_counts = Counter(sample_ids)

    # Get the count of points in the polygon
    with arcpy.da.UpdateCursor(out_fc, ['Linked_lagoslakeid', 'Total_points_in_lake_poly']) as cursor:
        for lagos_id, join_count in cursor:
            join_count = lagos_lake_counts[lagos_id]
            cursor.updateRow((lagos_id, join_count))

    # Mark any samples linked to more than one lake so that the analyst can select the correct lake in the
    # manual process
    with arcpy.da.UpdateCursor(out_fc, [lake_id_field, 'Duplicate_Candidate']) as cursor:
        for sample_id, duplicate_flag in cursor:
            duplicate_count = linked_multiple_lake_counts[sample_id]
            if duplicate_count > 1:
                duplicate_flag = "Y"
            else:
                duplicate_flag = "N"
            cursor.updateRow((sample_id, duplicate_flag))

    # clean up
    DM.AddField(out_fc, 'Note', 'TEXT', field_length=140)
    DM.Delete('in_memory')
    arcpy.AddMessage('Completed.')













