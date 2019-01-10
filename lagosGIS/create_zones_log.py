import csv
import os
import arcpy
from arcpy import management as DM
from arcpy import analysis as AN
from csiutils import create_temp_GDB
import lagosGIS

# files accessed by this script
MASTER_CLIPPING_POLY = r'D:\Continental_Limnology\Data_Working\LAGOS_US_GIS_Data_v0.5.gdb\NonPublished\US_Countybased_Clip_Polygon'
LAGOSNE_GDB = r'C:\Users\smithn78\Dropbox\CSI\CSI_LAGOS-exports\LAGOS-NE-EDI\LAGOS-NE-GIS\FileGDB\LAGOS_NE_GIS_Data_v1.0.gdb'
LAND_BORDER =  r'D:\Continental_Limnology\Data_Working\LAGOS_US_GIS_Data_v0.5.gdb\NonPublished\Derived_Land_Borders'
COASTLINE = r'D:\Continental_Limnology\Data_Working\LAGOS_US_GIS_Data_v0.5.gdb\NonPublished\TIGER_Coastline'
STATE_FC = r'D:\Continental_Limnology\Data_Downloaded\LAGOS_ZONES_ALL\TIGER_Boundaries\Unzipped Original\tl_2016_us_state.shp'
LAGOS_LAKES = r'D:\Continental_Limnology\Data_Working\LAGOS_US_GIS_Data_v0.5.gdb\LAGOS_US_All_Lakes_1ha'

# files to control this script
ZONE_CONTROL_CSV = r"C:\Users\smithn78\Dropbox\CL_HUB_GEO\Reprocessing_LAGOS_Zones.csv"
TEMP_GDB = create_temp_GDB('process_zones')

arcpy.env.workspace = TEMP_GDB
arcpy.env.outputCoordinateSystem = arcpy.SpatialReference(5070)

# read the control file
with open(ZONE_CONTROL_CSV) as csv_file:
    reader = csv.DictReader(csv_file)
    lines = [line for line in reader]

HU8_OUTPUT = [line for line in lines if line['LAGOS Zone Name'] == 'hu8'][0]['Output']

# Define the processing steps. 1) Dissolve on ID. 2) Clip to USA 3) Calculate original area. 4) Generate unique zone IDs.
def process_zone(zone_fc, output, zone_name, zone_id_field, zone_name_field, other_keep_fields, clip_hu8, lagosne_name):
    # dissolve fields by the field that zone_id is based on (the field that identifies a unique zone)
    dissolve_fields = [f for f in "{}, {}, {}".format(
        zone_id_field, zone_name_field, other_keep_fields).split(', ') if f != '']
    print("Dissolving...")
    dissolve1 = DM.Dissolve(zone_fc, 'dissolve1', dissolve_fields)

    # update name field to match our standard
    DM.AlterField(dissolve1, zone_name_field, 'name')

    # original area

    DM.AddField(dissolve1, 'originalarea', 'DOUBLE')
    DM.CalculateField(dissolve1, 'originalarea', '!shape.area@hectares!', 'PYTHON')

    #clip
    print("Clipping...")
    clip = AN.Clip(dissolve1, MASTER_CLIPPING_POLY, 'clip')
    if clip_hu8 == 'Y':
        final_clip = AN.Clip(clip, HU8_OUTPUT, 'final_clip')
    else:
        final_clip = clip

    print("Selecting...")
    # calc new area, orig area pct, compactness
    DM.AddField(final_clip, 'area_ha', 'DOUBLE')
    DM.AddField(final_clip, 'originalarea_pct', 'DOUBLE')
    DM.AddField(final_clip, 'compactness', 'DOUBLE')
    DM.JoinField(final_clip, zone_id_field, dissolve1, zone_id_field, 'originalarea_pct')

    uCursor_fields = ['area_ha', 'originalarea_pct', 'originalarea', 'compactness', 'SHAPE@AREA', 'SHAPE@LENGTH']
    with arcpy.da.UpdateCursor(final_clip, uCursor_fields) as uCursor:
        for row in uCursor:
            area, orig_area_pct, orig_area, comp, shape_area, shape_length = row
            area = shape_area/10000 # convert from m2 to hectares
            orig_area_pct = round(100 * area / orig_area, 2)
            comp = 4*3.14159*shape_area/(shape_length**2)
            row = (area, orig_area_pct, orig_area, comp, shape_area, shape_length)
            uCursor.updateRow(row)

    # if zones are present with <5% of original area and a compactness measure of <.2 (ranges from 0-1)
    # AND ALSO they are no bigger than 500 sq. km. (saves Chippewa County and a WWF), filter out
    # save eliminated polygons to temp database as a separate layer for inspection

    # Different processing for HU4 and HU8, so that they match the extent of HU8 more closely but still throw out tiny slivers
    # County also only eliminated if a tiny, tiny, tiny sliver (so: none should be eliminated)
    if zone_name not in ('hu4', 'hu12', 'county'):
        selected = AN.Select(final_clip, 'selected', "originalarea_pct >= 5 OR compactness >= .2 OR area_ha > 50000")
        not_selected = AN.Select(final_clip, '{}_not_selected'.format(output),
                                 "originalarea_pct < 5 AND compactness < .2 AND area_ha < 50000")

    else:
        selected = final_clip
    # eliminate small slivers, re-calc area fields, add perimeter and multipart flag
    # leaves the occasional errant sliver but some areas over 25 hectares are more valid so this is
    # CONSERVATIVE
    print("Trimming...")
    trimmed = DM.EliminatePolygonPart(selected, 'trimmed', 'AREA', '25 Hectares', part_option = 'ANY')

    # gather up a few calculations into one cursor because this is taking too long over the HU12 layer
    DM.AddField(trimmed, 'perimeter_m', 'DOUBLE')
    DM.AddField(trimmed, 'multipart', 'TEXT', field_length = 1)
    uCursor_fields = ['area_ha', 'originalarea_pct', 'originalarea', 'perimeter_m', 'multipart', 'SHAPE@']
    with arcpy.da.UpdateCursor(trimmed, uCursor_fields) as uCursor:
        for row in uCursor:
            area, orig_area_pct, orig_area, perim, multipart, shape = row
            area = shape.area/10000 # convert to hectares from m2
            orig_area_pct = round(100*area/orig_area, 2)
            perim = shape.length

            # multipart flag calc
            if shape.isMultipart:
                multipart = 'Y'
            else:
                multipart = 'N'
            row = (area, orig_area_pct, orig_area, perim, multipart, shape)
            uCursor.updateRow(row)

    # delete intermediate fields
    DM.DeleteField(trimmed, 'compactness')
    DM.DeleteField(trimmed, 'originalarea')

    print("Zone IDs....")
    # link to LAGOS-NE zone IDs
    DM.AddField(trimmed, 'zoneid', 'TEXT', field_length = 40)
    trimmed_lyr = DM.MakeFeatureLayer(trimmed, 'trimmed_lyr')
    if lagosne_name:
        # join to the old master GDB path on the same master field and copy in the ids
        old_fc = os.path.join(LAGOSNE_GDB, lagosne_name)
        old_fc_lyr = DM.MakeFeatureLayer(old_fc, 'old_fc_lyr')
        if lagosne_name == 'STATE' or lagosne_name == 'COUNTY':
            DM.AddJoin(trimmed_lyr, zone_id_field, old_fc_lyr, 'FIPS')
        else:
            DM.AddJoin(trimmed_lyr, zone_id_field, old_fc_lyr, zone_id_field) # usually works because same source data

        # copy
        DM.CalculateField(trimmed_lyr, 'zoneid', '!{}.ZoneID!.lower()'.format(lagosne_name), 'PYTHON')
        DM.RemoveJoin(trimmed_lyr)

    # generate new zone ids
    old_ids = [row[0] for row in arcpy.da.SearchCursor(trimmed, 'zoneid')]
    with arcpy.da.UpdateCursor(trimmed, 'zoneid') as cursor:
        counter = 1
        for row in cursor:
            if not row[0]: # if no existing ID borrowed from LAGOS-NE, assign a new one
                new_id = '{name}_{num}'.format(name = zone_name, num = counter)

                # ensures new ids don't re-use old numbers but fills in all positive numbers eventually
                while new_id in old_ids:
                    counter +=1
                    new_id = '{name}_{num}'.format(name = zone_name, num = counter)
                row[0] = new_id
                cursor.updateRow(row)
                counter += 1

    print("Edge flags...")
    # add flag fields
    DM.AddField(trimmed, 'onlandborder', 'TEXT', field_length = 2)
    DM.AddField(trimmed, 'oncoast', 'TEXT', field_length = 2)

    # identify border zones
    border_lyr = DM.MakeFeatureLayer(LAND_BORDER, 'border_lyr')
    DM.SelectLayerByLocation(trimmed_lyr, 'INTERSECT', border_lyr)
    DM.CalculateField(trimmed_lyr, 'onlandborder', "'Y'", 'PYTHON')
    DM.SelectLayerByAttribute(trimmed_lyr, 'SWITCH_SELECTION')
    DM.CalculateField(trimmed_lyr, 'onlandborder' ,"'N'", 'PYTHON')

    # identify coastal zones
    coastal_lyr = DM.MakeFeatureLayer(COASTLINE, 'coastal_lyr')
    DM.SelectLayerByLocation(trimmed_lyr, 'INTERSECT', coastal_lyr)
    DM.CalculateField(trimmed_lyr, 'oncoast', "'Y'", 'PYTHON')
    DM.SelectLayerByAttribute(trimmed_lyr, 'SWITCH_SELECTION')
    DM.CalculateField(trimmed_lyr, 'oncoast' ,"'N'", 'PYTHON')

    print("State assignment...")
    # State?
    DM.AddField(trimmed, "state", 'text', field_length = '2')
    state_center = arcpy.SpatialJoin_analysis(trimmed, STATE_FC, 'state_center', join_type = 'KEEP_COMMON',
                                              match_option = 'HAVE_THEIR_CENTER_IN')
    state_intersect = arcpy.SpatialJoin_analysis(trimmed, STATE_FC, 'state_intersect', match_option = 'INTERSECT')
    state_center_dict = {row[0]:row[1] for row in arcpy.da.SearchCursor(state_center, ['ZoneID', 'STUSPS'])}
    state_intersect_dict = {row[0]:row[1] for row in arcpy.da.SearchCursor(state_intersect, ['ZoneID', 'STUSPS'])}
    with arcpy.da.UpdateCursor(trimmed, ['ZoneID', 'state']) as cursor:
        for updateRow in cursor:
            keyValue = updateRow[0]
            if keyValue in state_center_dict:
                updateRow[1] = state_center_dict[keyValue]
            else:
                updateRow[1] = state_intersect_dict[keyValue]
            cursor.updateRow(updateRow)

    # glaciation status?
    # TODO as version 0.6

    # preface the names with the zones
    DM.DeleteField(trimmed, 'ORIG_FID')
    fields = [f.name for f in arcpy.ListFields(trimmed, '*') if f.type not in ('OID', 'Geometry') and not f.name.startswith('Shape_')]
    for f in fields:
        new_fname = '{zn}_{orig}'.format(zn=zone_name, orig = f).lower()
        try:
            DM.AlterField(trimmed, f, new_fname, clear_field_alias = 'TRUE')
        # sick of debugging the required field message-I don't want to change required fields anyway
        except:
            pass

    DM.CopyFeatures(trimmed, output)

    # cleanup
    lyr_objects = [lyr_object for var_name, lyr_object in locals().items() if var_name.endswith('lyr')]
    temp_fcs = arcpy.ListFeatureClasses('*')
    for l in lyr_objects + temp_fcs:
        DM.Delete(l)

# COUNTY was originally processed by hand due to the need for manual editing
# Then it was used the make the clipping poly that is used in this script

# Then process HU8 because it will be used to clip HU4 and HU12 also
hu8 = [line for line in lines if line['LAGOS Zone Name'] == 'hu8'][0]
print('hu8')
process_zone(hu8['Original'],
             hu8['Output'],
             hu8['LAGOS Zone Name'],
             hu8['Zone Field'],
             hu8['Name Field'],
             hu8['Other Keep Fields'],
             hu8['Clip to HU8'],
             hu8['LAGOS-NE Name'])

# Then loop through everything else
# County is included just to make it easier to reproduce and prove it's consistent with the others
lines = [line for line in lines if line['LAGOS Zone Name'] not in ('hu8')]
for line in lines:
    print(line['LAGOS Zone Name'])
    process_zone(line['Original'],
                 line['Output'],
                 line['LAGOS Zone Name'],
                 line['Zone Field'],
                 line['Name Field'],
                 line['Other Keep Fields'],
                 line['Clip to HU8'],
                 line['LAGOS-NE Name'])


# # Add 100% open water designation to HU12
# # First select only LAGOS lakes over 250 hectares (0.2% of HU12 size):  3567 lakes
# arcpy.env.workspace = 'in_memory'
# hu12 = [line for line in lines if line['LAGOS Zone Name'] == 'hu12'][0]['Output']
# lagos_lakes_250ha = AN.Select(LAGOS_LAKES, 'lagos_lakes_250ha', 'Hectares > 250')
# hu12_erase = AN.Erase(hu12, lagos_lakes_250ha, 'hu12_erase')
# DM.AddField(hu12_erase, 'not_lake_pct', 'FLOAT')
# pct_dict = {}
# with arcpy.da.UpdateCursor(hu12_erase, ['hu12_zoneid', 'hu12_area_ha', 'not_lake_pct', 'SHAPE@']) as uCursor:
#     for zone_id, area_ha, not_lake_pct, shape in uCursor:
#         not_lake_pct = 100*shape.area/(area_ha*10000) # convert area_ha to square meters
#         pct_dict[zone_id] = not_lake_pct
#         uCursor.updateRow((zone_id, area_ha, not_lake_pct, shape))
#
# DM.AddField(hu12, 'openwaterhu12', 'TEXT', field_length = 1)
# with arcpy.da.UpdateCursor(hu12, ['hu12_zoneid', 'openwaterhu12']) as uCursor:
#     for zone_id, flag in uCursor:
#         if pct_dict[zone_id] <= 20:
#             flag = 'Y'
#         else:
#             flag = 'N'
#     uCursor.updateRow((zone_id, flag))
#
# DM.Delete('in_memory')
#
#
#
# # Add hu12edge
# # Atlantic Ocean name or Pacific Ocean or Gulf of Mexico name, does not have "Frontal", "Beach", "Bank" in the name AND contains no lakes
# # 	Border slivers as detected by compactness (something like this query original_area_pct < 0.1 AND compactness < .2 AND area_ha < 60)
# # 	Belongs to a HU8 not found in LAGOS (true for just one HU12: 040602000000)

