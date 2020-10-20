import os
import time
import arcpy
from arcpy import management as DM
from lagosGIS import select_fields


def preprocess(padus_combined_fc, output_fc):
    """
    The Protected Areas Database of the U.S. feature class contains overlapping polygons representing multiple
    protection types. This tool "flattens" the PADUS2_0Combined_Marined_Fee_Designation_Easement dataset so that the
    Own_Type, GAP_Sts, and IUCN_Cat fields are values are retained, renamed, and filtered for one primary value per
    region according to the following rules:
    Own_Type -> "agency". "Fee" type > "Easement" > "Marine" > "Designation
    GAP_Sts -> "gap" . Highest GAP status preferentially retained.
    IUCN_Cat -> "iucn". Lowest number codes preferentially retained, then "Other", last "Unassigned".
    :param padus_combined_fc:
    :param output_fc:
    :return:
    """

    arcpy.env.workspace = 'in_memory'

    # Prep: Select only the fields needed, remove curves (densify) which prevents problems with geometry
    # that prevents DeleteIdentical based on Shape
    padus_fields = ['FeatClass', 'Own_Type', 'GAP_Sts', 'IUCN_Cat']
    arcpy.AddMessage('{} select...'.format(time.ctime()))
    padus_select = select_fields(padus_combined_fc, 'padus_select', padus_fields, convert_to_table=False)
    arcpy.Densify_edit(padus_select, 'OFFSET', max_deviation = '1 Meters')
    arcpy.AddMessage('{} union...'.format(time.ctime()))

    # self-union
    union = arcpy.Union_analysis([padus_select, padus_select], 'union', 'ALL', cluster_tolerance='1 Meters')

    # self-union creates duplicates, remove
    fid1 = 'FID_padus_select'
    fid2 = 'FID_padus_select_1'
    padus_fields_1 = padus_fields + [f + '_1' for f in padus_fields]
    padus_fields_1.extend([fid1, fid2])
    arcpy.AddMessage('{} delete identical round 1...'.format(time.ctime()))
    DM.DeleteIdentical(union, padus_fields_1)

    # calculate the new class values based on the overlaid polygons
    new_fields = ['agency', 'gap', 'iucn', 'merge_flag', 'area_m2']
    cursor_fields = sorted(padus_fields_1) + new_fields + ['SHAPE@AREA']
    DM.AddField(union, 'agency', 'TEXT', field_length=5)
    DM.AddField(union, 'gap', 'TEXT', field_length=1)
    DM.AddField(union, 'iucn', 'TEXT', field_length=24)
    DM.AddField(union, 'merge_flag', 'TEXT', field_length=1)
    DM.AddField(union, 'area_m2', 'DOUBLE')

    owner_rule = {'Fee': 1, 'Easement': 2, 'Marine': 3, 'Designation': 4}
    iucn_rule = {'Ia': 1,
                 'Ib': 2,
                 'II': 3,
                 'III': 4,
                 'IV': 5,
                 'V': 6,
                 'VI': 7,
                 'Other Conservation Area': 8,
                 'Unassigned': 9}

    arcpy.AddMessage('{}  calculate...'.format(time.ctime()))
    with arcpy.da.UpdateCursor(union, cursor_fields) as cursor:
        for row in cursor:
            id1, id2, fc1, fc2, gap1, gap2, iucn1, iucn2, own1, own2, agency, gap, iucn, flag, areacalc, areashp = row
            flag = 'N'
            # take fee first, designation last to pull owner type from
            if owner_rule[fc1] < owner_rule[fc2]:
                agency = own1
            else:
                agency = own2

            # most protected gap
            gap = min([gap1, gap2])

            # numbered iucn over other or unassigned; use numbers as priority order
            if iucn_rule[iucn1] < iucn_rule[iucn2]:
                iucn = iucn1
            else:
                iucn = iucn2

            if fc1 <> fc2 or own1 <> own2 or gap1 <> gap2 or iucn1 <> iucn2:
                flag = 'Y'

            areacalc = areashp

            row = (id1, id2, fc1, fc2, gap1, gap2, iucn1, iucn2, own1, own2, agency, gap, iucn, flag, areacalc, areashp)
            cursor.updateRow(row)


    # Prep for DeleteIdentical: Dispose of small polygons (they cause trouble, don't effect
    # stats enough to bother) and repair geometry on the rest.
    large_enough = arcpy.Select_analysis(union, 'large_enough', 'area_m2 > 4')
    arcpy.AddMessage('{} repair...'.format(time.ctime()))
    DM.RepairGeometry(large_enough)

    # Sort so that merged polygons are retained in DeleteIdentical, and delete identical shapes to end
    # up with just the merged polygons and non-overlapping polygons
    arcpy.AddMessage('{}  sort...'.format(time.ctime()))
    sorted_fc = DM.Sort(large_enough, 'sorted_fc', [['merge_flag', 'DESCENDING']])

    arcpy.AddMessage('{}  delete identical shape...'.format(time.ctime()))
    DM.DeleteIdentical(sorted_fc, "Shape")
    output_fields = [fid1, fid2] + new_fields
    output_fc = select_fields(sorted_fc, output_fc, output_fields)

    # cleanup
    for item in [padus_select, union, sorted_fc, large_enough]:
        DM.Delete(item)
    return output_fc

def main():
    padus_combined_fc = arcpy.GetParameterAsText(0)
    output_fc = arcpy.GetParameterAsText(1)
    preprocess(padus_combined_fc, output_fc)

if __name__ == '__main__':
    main()





