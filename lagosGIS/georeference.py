import os
import arcpy
from arcpy import analysis as AN
from arcpy import management as DM
from lagosGIS import list_shared_words

MASTER_LAKES_FC = r''
MASTER_STREAMS_FC = r''
MASTER_COUNTY_FC = r''
MASTER_LAKE_ID = 'lagoslakeid'
MASTER_GNIS_NAME = "GNIS_Name"
MASTER_STREAM_ID = 'Permanent_Identifier'
MASTER_COUNTY_NAME = 'NAME'



def georeference_lakes(lake_points_fc, out_fc, lake_id_field, lake_name_field, lake_county_field = ''):
    arcpy.env.workspace = 'in_memory'
    join1 = '{}_1'.format(os.path.splitext(out_fc)[0])
    join2 = '{}_2'.format(os.path.splitext(out_fc)[0])
    join3 = '{}_3'.format(os.path.splitext(out_fc)[0])
    join4 = '{}_4'.format(os.path.splitext(out_fc)[0])
    join5 = '{}_5'.format(os.path.splitext(out_fc)[0])
    freq = 'frequency_of_lake_id'

    point_fields = arcpy.ListFields(lake_points_fc)

    if not lake_county_field in arcpy.ListFields(lake_points_fc, '{}*'.format(lake_county_field)):
        print('{} field does not exist in dataset.'.format(lake_county_field))
        raise Exception

    # If identifier matches a LAGOS lake in the crosswalk, then do these steps
    # TODO: Finish the crosswalk so you can use this step

    join1 = AN.SpatialJoin(lake_points_fc, MASTER_LAKES_FC, join1, 'JOIN_ONE_TO_MANY', 'KEEP_ALL', 'INTERSECT')
    join2 = AN.SpatialJoin(join1, MASTER_STREAMS_FC, join2, 'JOIN_ONE_TO_MANY', 'KEEP_ALL', 'INTERSECT')
    join3 = AN.SpatialJoin(join2, MASTER_LAKES_FC, join3, 'JOIN_ONE_TO_MANY', 'KEEP_ALL', 'INTERSECT', '10 meters')
    join4 = AN.SpatialJoin(join3, MASTER_LAKES_FC, join4, 'JOIN_ONE_TO_MANY', 'KEEP_ALL', 'INTERSECT', '100 meters')

    freq = AN.Frequency(join4, freq, lake_id_field)
    DM.AddField(join4, 'Comment', 'TEXT', field_length = 100)
    DM.AddField(join4, 'Manual_Review', 'SHORT')
    DM.AddField(join4, 'Shared_Words', 'TEXT', field_length = 100)


    update_fields = [lake_id_field, lake_name_field,  MASTER_LAKE_ID, MASTER_GNIS_NAME, # 0m match
                     MASTER_STREAM_ID, # stream match
                     MASTER_LAKE_ID + '_1', MASTER_GNIS_NAME +'_12', # 10m match
                     MASTER_LAKE_ID + '_12', MASTER_GNIS_NAME + '_12_13', # 100m match
                     'Comment', 'Manual_Review', 'Shared_Words']
    cursor = arcpy.da.UpdateCursor(join4, update_fields)

    for id, name, mid_0, mname_0, stream_id, mid_10, mname_10, mid_100, mname_100, comment, review, words in cursor:
        if mid_0 is not None: # if the point is directly in a polygon
            words = list_shared_words(name, mname_0, exclude_lake_words=False)
            comment = 'Exact location link'
            review = -1
        elif mid_0 is None and mid_10 is not None: # if the point is only within 10m of a lake
            words = list_shared_words(name, mname_10, exclude_lake_words=False)
            if words:
                comment = 'Linked by common name and location'
                review = -1
            if not words:
                comment = 'Linked by common location'
                review = 1
        elif mid_0 is None and mid_10 is None and mid_100 is not None: # if the point is only within 100m of lake(s)
            words = list_shared_words(name, mname_100, exclude_lake_words=True)
            # TODO: Frequency check
            if stream_id is not None: # if there is a stream match
                comment = 'Not linked because represented as river in NHD'
                review = 2
            if stream_id is None:
                if words:
                    comment = 'Linked by common name and location'
                    review = 1
                if not words:
                    comment = 'Linked by common location'
                    review = 2
        cursor.updateRow(words, comment, review)

    join5 = AN.Select(join4, join5, 'Manual_Review IS NULL')
    if lake_county_field:
        join5 = DM.JoinField(join5, lake_county_field, MASTER_COUNTY_FC, MASTER_COUNTY_NAME, MASTER_COUNTY_NAME)



    cursor = arcpy.da.UpdateCursor(join5, update_fields.append

    # then the county stuff

    # then re-code the no matches as a 3






    # Then deal with the frequency issue somehow

    # Then make sure to only keep the fields necessary when you write to an output











