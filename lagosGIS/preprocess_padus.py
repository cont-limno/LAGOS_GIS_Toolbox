import arcpy
from arcpy import management as DM
from lagosGIS import select_fields

def preprocess(padus_combined_fc, output_fc):
    arcpy.env.workspace = 'in_memory'
    padus_fields = ['FeatClass', 'Own_Type', 'GAP_Sts', 'IUCN_Cat']
    padus_select = select_fields(padus_combined_fc, 'padus_select', padus_fields)
    union = arcpy.Union_analysis([padus_select, padus_select], 'union', 'ALL')

    fid1 = 'FID_padus_select'
    fid2 = 'FID_padus_select_1'
    padus_fields_1 = padus_fields + [f + '_1' for f in padus_fields]
    padus_fields_1.extend([fid1, fid2])
    DM.DeleteIdentical(union, padus_fields_1)

    new_fields = ['agency', 'gap', 'iucn', 'merge_flag']
    cursor_fields = sorted(padus_fields_1) + new_fields
    DM.AddField(union, 'agency', 'TEXT', field_length=5)
    DM.AddField(union, 'gap', 'TEXT', field_length=1)
    DM.AddField(union, 'iucn', 'TEXT', field_length=24)
    DM.AddField(union, 'merge_flag', 'TEXT', field_length=1)

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

    with arcpy.da.UpdateCursor(union, cursor_fields) as cursor:
        for row in cursor:
            id1, id2, fc1, fc2, gap1, gap2, iucn1, iucn2, own1, own2, agency, gap, iucn, flag = row
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

            row = (id1, id2, fc1, fc2, gap1, gap2, iucn1, iucn2, own1, own2, agency, gap, iucn, flag)
            cursor.updateRow(row)

    sorted_fc = DM.Sort(union, 'sorted_fc', [['merge_flag', 'DESCENDING']])
    DM.DeleteIdentical(sorted_fc, "Shape")
    output_fields = [fid1, fid2] + new_fields
    output_fc = select_fields(sorted_fc, output_fc, output_fields)

    for item in [padus_select, union, sorted_fc]:
        DM.Delete(item)
    return output_fc

def main():
    padus_combined_fc = arcpy.GetParameterAsText(0)
    output_fc = arcpy.GetParameterAsText(1)
    preprocess(padus_combined_fc, output_fc)

if __name__ == '__main__':
    main()





