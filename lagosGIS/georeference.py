import os
import arcpy
from collections import Counter
from arcpy import analysis as AN
from arcpy import management as DM
import lagosGIS

# Change these to match your computer. Yes, this is a crap way to code this.
MASTER_LAKES_FC = r'D:/Continental_Limnology/Data_Working/LAGOS_US_Predecessors.gdb/NHDWaterbody_LAGOS'
MASTER_STREAMS_FC = r'D:/Continental_Limnology/Data_Working/LAGOS_US_Predecessors.gdb/NHDArea_Natl_SelectStreamRiver'

# Can change but probably don't need to
MASTER_LAKE_ID = 'lagoslakeid'
MASTER_GNIS_NAME = "GNIS_Name"
#MASTER_STREAM_ID = 'Permanent_Identifier' #hard-coded below
MASTER_COUNTY_NAME = 'NAME'
MASTER_STATE_NAME = 'STATE'
STATES = ("AK","AL","AR","AZ","CA","CO","CT","DC","DE","FL","GA","GU","HI","IA","ID", "IL","IN","KS","KY","LA","MA",
          "MD","ME","MH","MI","MN","MO","MS","MT","NC","ND","NE","NH","NJ","NM","NV","NY", "OH","OK","OR","PA","PR",
          "PW","RI","SC","SD","TN","TX","UT","VA","VI","VT","WA","WI","WV","WY")
CRS_DICT = {'NAD83':4269,
            'WGS84':4326
            }


def spatialize_lakes(lake_points_csv, out_fc, in_x_field, in_y_field, in_crs = 'NAD83'):
    if in_crs not in CRS_DICT.keys():
        raise ValueError('Use one of the following CRS names: {}'.format(','.join(CRS_DICT.keys())))
    DM.MakeXYEventLayer(lake_points_csv, in_x_field, in_y_field, 'xylayer', arcpy.SpatialReference(CRS_DICT[in_crs]))
    arcpy.env.outputCoordinateSystem = arcpy.SpatialReference(102039)
    DM.CopyFeatures('xylayer', out_fc)

def georeference_lakes(lake_points_fc, out_fc, state, lake_id_field, lake_name_field, lake_county_field = ''):
    arcpy.AddMessage("Joining...")
    if state.upper() not in STATES:
        raise ValueError('Use the 2-letter state code abbreviation')
    arcpy.env.workspace = 'in_memory'
    out_short = os.path.splitext(os.path.basename(out_fc))[0]
    join1 = '{}_1'.format(out_short)
    join2 = '{}_2'.format(out_short)
    join3 = '{}_3'.format(out_short)
    join4 = '{}_4'.format(out_short)
    join5 = '{}_5'.format(out_short)
    freq = 'frequency_of_lake_id'

    if lake_county_field and not lake_county_field in arcpy.ListFields(lake_points_fc, '{}*'.format(lake_county_field)):
        print('{} field does not exist in dataset.'.format(lake_county_field))
        raise Exception

    # # This code doesn't work because you can't project to in_memory. For now enforce externally (thru work practice)
    # # Ensure same projection
    # master_streams_fc = MASTER_STREAMS_FC
    # d_lakes_fc = arcpy.Describe(MASTER_LAKES_FC).spatialReference.exportToString()
    # d_streams_fc = arcpy.Describe(master_streams_fc).spatialReference.exportToString()
    # d_points_fc = arcpy.Describe(lake_points_fc).spatialReference.exportToString()
    #
    # if d_lakes_fc <> d_streams_fc:
    #     master_streams_fc = DM.Project(lake_points_fc, 'in_memory/master_streams_fc_proj',
    #                                 arcpy.Describe(MASTER_STREAMS_FC).spatialReference)
    #     if d_lakes_fc <> d_points_fc:
    #         lake_points_fc = DM.Project(lake_points_fc, 'in_memory/lake_points_fc_proj',
    #                                     arcpy.Describe(MASTER_LAKES_FC).spatialReference)

    point_fields = [f.name for f in arcpy.ListFields(lake_points_fc)]

    # If identifier matches a LAGOS lake in the crosswalk, then do these steps
    # TODO: Finish the crosswalk so you can use this step

    # Try to make some spatial connections and fulfill some logic to assign a link
    join1 = AN.SpatialJoin(lake_points_fc, MASTER_LAKES_FC, join1, 'JOIN_ONE_TO_MANY', 'KEEP_ALL', match_option = 'INTERSECT')
    join2 = AN.SpatialJoin(join1, MASTER_STREAMS_FC, join2, 'JOIN_ONE_TO_MANY', 'KEEP_ALL', match_option = 'INTERSECT')
    join3 = AN.SpatialJoin(join2, MASTER_LAKES_FC, join3, 'JOIN_ONE_TO_MANY', 'KEEP_ALL', match_option = 'INTERSECT', search_radius = '10 meters')
    join4 = AN.SpatialJoin(join3, MASTER_LAKES_FC, join4, 'JOIN_ONE_TO_MANY', 'KEEP_ALL', match_option = 'INTERSECT', search_radius =  '100 meters')

    # TODO: Add back frequency thing
    # freq = AN.Frequency(join4, freq, lake_id_field)

    DM.AddField(join4, 'Auto_Comment', 'TEXT', field_length = 100)
    DM.AddField(join4, 'Manual_Review', 'SHORT')
    DM.AddField(join4, 'Shared_Words', 'TEXT', field_length = 100)
    DM.AddField(join4, 'Linked_lagoslakeid', 'LONG')

    update_fields = [lake_id_field, lake_name_field,  MASTER_LAKE_ID, MASTER_GNIS_NAME, # 0m match
                     'PERMANENT_IDENTIFIER_1', 'GNIS_NAME_1', # stream match
                     MASTER_LAKE_ID + '_1', MASTER_GNIS_NAME +'_12', # 10m match
                     MASTER_LAKE_ID + '_12', MASTER_GNIS_NAME + '_12_13', # 100m match
                     'Auto_Comment', 'Manual_Review', 'Shared_Words',
                     'Linked_lagoslakeid']
    all_fields = [f.name for f  in arcpy.ListFields(join4)]
    for f in update_fields:
        if f not in all_fields:
            print f
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

    # Select down to a minimum set because we're about to join on county, which will create lots of duplicate matches
    # Then join calculated results back to full set
    if lake_county_field:
        join5 = AN.Select(join4, join5, 'Manual_Review IS NULL')
        lakes_state = AN.Select(MASTER_LAKES_FC, 'lakes_state', "{0} = '{1}'".format(MASTER_STATE_NAME, state))
        join5 = DM.JoinField(join5, lake_county_field, lakes_state, MASTER_COUNTY_NAME, MASTER_COUNTY_NAME)
        # cursor_fields = [lake_id_field, lake_name_field, lake_county_field,
        #                  MASTER_LAKE_ID + '_12', MASTER_GNIS_NAME + '_12_13',  # 100m match
        #                  'Comment', 'Manual_Review', 'Shared_Words']
        # cursor = arcpy.da.UpdateCursor(join5, update_fields.extend([lake_county_field, MASTER_COUNTY_NAME]))
        # for whatever in cursor:
        #     if mcounty is not None:
        #         words = lagosGIS.list_shared_words()
    else:
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


    # Then make sure to only keep the fields necessary when you write to an output
    copy_fields = point_fields + ['Linked_lagoslakeid', 'Auto_Comment', 'Manual_Review', 'Shared_Words', 'Comment']
    copy_fields.remove('Shape')
    copy_fields.remove('OBJECTID')

    lagosGIS.select_fields(join5, out_fc, copy_fields)

    DM.AssignDomainToField(out_fc, 'Comment', 'Comment')

    DM.AddField(out_fc, 'Join_Count', 'Short')

    # Get the join_count for each limno lake ID
    # De-dupe anything resulting from limno ID duplicates first before counting
    id_pairs = list(set([row[0] for row in arcpy.da.SearchCursor(out_fc, [lake_id_field, MASTER_LAKE_ID])]))
    # THEN pull out LAGOS id. Any duplicate now are only due to multiple distinct points within lake
    lagos_ids = [ids[1] for ids in id_pairs]
    counts = Counter(lagos_ids)

    with arcpy.da.UpdateCursor(out_fc, [MASTER_LAKE_ID, 'Total_points_in_lake_poly']) as cursor:
        for lagos_id, join_count in cursor:
            join_count = counts[lagos_id]
            cursor.updateRow(lagos_id, join_count)



    DM.AddField(out_fc, 'Note', 'TEXT', field_length=140)
    DM.Delete('in_memory')

    # Then deal with the frequency issue somehow













