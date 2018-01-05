import os
import arcpy
from arcpy import analysis as AN
from arcpy import management as DM
from lagosGIS import list_shared_words

LAKES_MASTER = r''


def georeference_lakes(lake_points_fc, master_lakes_fc, out_fc, lake_id_field, lake_name_field):
    arcpy.env.workspace = 'in_memory'
    join1 = '{}_1'.format(os.path.splitext(out_fc)[0])
    join2 = '{}_2'.format(os.path.splitext(out_fc)[0])
    join3 = '{}_3'.format(os.path.splitext(out_fc)[0])
    freq = 'frequency_of_lake_id'
    # If identifier matches a LAGOS lake in the crosswalk, then do these steps
    # TODO: Finish the crosswalk so you can use this step

    join1 = AN.SpatialJoin(lake_points_fc, master_lakes_fc, join1, 'JOIN_ONE_TO_MANY', 'KEEP_ALL', 'INTERSECT')
    join2 = AN.SpatialJoin(join1, master_lakes_fc, join2, 'JOIN_ONE_TO_MANY', 'KEEP_ALL', 'INTERSECT', '10 meters')
    join3 = AN.SpatialJoin(join2, master_lakes_fc, join3, 'JOIN_ONE_TO_MANY', 'KEEP_ALL', 'INTERSECT', '100 meters')
    freq = AN.Frequency(join3, freq, lake_id_field)
    DM.AddField(join3, 'Comment', 'TEXT', field_length = 100)
    DM.AddField(join3, 'Manual_Review', 'SHORT')
    DM.AddField(join3, 'Shared_Words', 'TEXT', field_length = 100)


    update_fields = [lake_id_field, lake_name_field, 'lagoslakeid', 'GNIS_Name',
                     'lagoslakeid_1', 'GNIS_Name_1',
                     'lagoslakeid_12', 'GNIS_Name_12',
                     'Comment', 'Manual_Review', 'Shared_Words']
    cursor = arcpy.da.UpdateCursor(join3, update_fields)

    for id, name, mid_0, mname_0, mid_10, mname_10, mid_100, mname_100, comment, review, words in cursor:
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
            if words:
                comment = 'Linked by common name and location'
                review = 1
            if not words:
                comment = 'Linked by common location'
                review = 2

    cursor.updateRow(words, comment, review)










