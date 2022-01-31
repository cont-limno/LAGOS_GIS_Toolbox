# filename: make_lagos_streams.py
# author: Nicole J Smith
# version: 2.0 Beta
# LAGOS module(s): GEO
# tool type: code journal, no ArcGIS toolbox
# status: work in progress

import os
import re
import arcpy
import lagosGIS

NHD_DIR = r'F:\Continental_Limnology\Data_Downloaded\NHDPlus_High_Resolution_COMPLETE\Unzipped_Original\Vectors'
OUTPUT_GDB = r'F:\Continental_Limnology\Data_Downloaded\NHDPlus_High_Resolution_COMPLETE\Pre-processed\NHDPlus_HR_Streams.gdb'

# get list of gdbs
arcpy.env.workspace = NHD_DIR
gdb_list = arcpy.ListWorkspaces('NHDPLUS*')
regions = ["%02d" % i for i in range(1,19)]

def stream_process(gdb):
    flowline = os.path.join(gdb, 'NHDFlowline')
    flowline_vaa = os.path.join(gdb, 'NHDPlusFlowlineVAA')
    hu4 = re.search('\d{4}', gdb).group()
    out_streams = os.path.join(OUTPUT_GDB, 'streams_{}'.format(hu4))
    if not arcpy.Exists(out_streams):
        arcpy.CopyFeatures_management(flowline, out_streams)
        strahler_dict = {r[0]:r[1] for r in arcpy.da.SearchCursor(flowline_vaa, ['NHDPlusID', 'StreamOrde'])}
        arcpy.AddField_management(out_streams, 'StreamOrder', 'SHORT')
        with arcpy.da.UpdateCursor(out_streams, ['NHDPlusID', 'StreamOrder']) as cursor:
            # add Strahler order for each flowline
            for row in cursor:
                row[1] = strahler_dict.get(row[0])
                cursor.updateRow(row)

    return out_streams

# # make a stream layer with Strahler for each gdb
# for gdb in gdb_list:
#     print(gdb)
#     stream_process(gdb)
#
# # then merge to region
# arcpy.env.workspace = OUTPUT_GDB
# for region in regions:
#     wildcard = 'streams_{}*'.format(region)
#     print wildcard
#     fcs = arcpy.ListFeatureClasses(wildcard)
#     print(fcs)
#     streams_all = 'streams_all_{}'.format(region)
#     streams_24k = 'streams_24k_{}'.format(region)
#     if not arcpy.Exists(streams_all):
#         lagosGIS.efficient_merge(fcs, streams_all)
#         arcpy.Select_analysis(streams_all, streams_24k, 'VisibilityFilter >= 24000')
#
#
# streams_all_all = [os.path.join(OUTPUT_GDB, 'streams_all_{}'.format(region)) for region in regions if region not in ('10', '01', '02', '03')]
#
all_streams_nhdhr = os.path.join(OUTPUT_GDB, 'all_streams_nhdhr')
all_nhdarea = os.path.join(OUTPUT_GDB, 'all_nhdarea')
artificial_paths = os.path.join(OUTPUT_GDB, 'artificial_paths')
final_streams = os.path.join(OUTPUT_GDB, 'lagos_streams')
headwater = os.path.join(OUTPUT_GDB, 'headwater')
midreach = os.path.join(OUTPUT_GDB, 'midreach')
river = os.path.join(OUTPUT_GDB, 'river')


# lagosGIS.efficient_merge(streams_all_all, all_streams_nhdhr))

# # # Merge all NHDArea polygons with StreamRiver ftype (460)
# # nhd_areas = [os.path.join(gdb, 'NHDArea') for gdb in gdb_list]
# # lagosGIS.efficient_merge(nhd_areas, all_nhdarea, 'FType = 460')
#
# # find artificial paths that are associated with StreamRiver polygons
# print("artificial paths")
# artificial_paths = arcpy.Select_analysis(all_streams_nhdhr, artificial_paths, 'FType = 558')
# arcpy.Select_analysis(all_streams_nhdhr, final_streams, 'FType NOT IN (566, 558)')
# area_permids = [r[0] for r in arcpy.da.SearchCursor(all_nhdarea, 'Permanent_Identifier')]
# with arcpy.da.UpdateCursor(artificial_paths, ['WBArea_Permanent_Identifier']) as cursor:
#     for row in cursor:
#         if row[0] not in area_permids:
#             cursor.deleteRow()
#
# #append
# arcpy.Append_management(artificial_paths, final_streams)

print("river")
arcpy.Select_analysis(final_streams, river, 'StreamOrder >= 7')
print("midreach")
arcpy.Select_analysis(final_streams, midreach, 'StreamOrder > 3 AND StreamOrder <= 6')
print("headwater")
arcpy.Select_analysis(final_streams, headwater, 'StreamOrder <= 3 OR StreamOrder IS NULL') # StreamOrder = 1, 2, 3, -9, None




