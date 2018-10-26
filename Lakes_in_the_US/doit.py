import os, zipfile
import arcpy
import assumptions # in this repo
import lakes_us # in this repo


# Locations. Change these for your system. To re-run this code, you can always run this whole section.
NHD_DOWNLOAD_DIR = r"D:\Continental_Limnology\Data_Downloaded\National_Hydrography_Dataset\Zipped"
NHD_UNZIPPED_DIR = r"D:\Continental_Limnology\Data_Downloaded\National_Hydrography_Dataset\Unzipped_Original"
ALL_LAKES_FC = 'D:/Continental_Limnology/Data_Working/LAGOS_US_Predecessors.gdb/NHDWaterbody_merge202_jun30_deduped'
<<<<<<< HEAD
ALL_XREF_TABLE = 'D:/Continental_Limnology/Data_Working/LAGOS_US_Predecessors.gdb/NHDReachCrossReference_all_merged'
LAKES_XREF_TABLE = 'D:/Continental_Limnology/Data_Working/LAGOS_US_Predecessors.gdb/NHDReachCrossReference_lakes'
CONUS_LAKES_FC = 'D:/Continental_Limnology/Data_Working/LAGOS_US_Predecessors.gdb/NHDWaterbody_CONUS_2'
CONUS_LAKES_FC_PROJ = 'D:/Continental_Limnology/Data_Working/LAGOS_US_Predecessors.gdb/NHDWaterbody_CONUS_2_Albers'
=======
CONUS_LAKES_FC = 'D:/Continental_Limnology/Data_Working/LAGOS_US_Predecessors.gdb/NHDWaterbody_CONUS'
>>>>>>> parent of 38a20a8... change names of the variables
BROAD_LAKE_RESERVOIR_FILTER = "FType IN (436, 390)"
US_SPATIAL_EXTENT = r'D:\grad03\Data_Working\LAGOS_US_GIS_Data_v0.1.gdb\Spatial_Classifications\STATE'
USGS_ALBERS_PROJ = arcpy.SpatialReference(102039)


# Step 1: Download the NHD by subregion and unzip. You WILL need the HYDRO_NET to do the connectivity analyses so you cannot
# use the national snapshot. We only downloaded regions 01-20 to cover the contiguous United States.

# TODO: Convert this wget statement to something that works in Python

# if NHD_DOWNLOAD_DIR doesn't exist, create it.

#wget -t 20 ftp://rockyftp.cr.usgs.gov/vdelivery/Datasets/Staged/Hydrography/NHD/HU4/HighResolution/GDB/NHD_H_[0,1][0,1,2,3,4,5,6,7,8,9]*_GDB.*[zip,xml]

nhd_zip_list = [f for f in os.listdir(NHD_DOWNLOAD_DIR)
                if os.path.isfile(os.path.join(NHD_DOWNLOAD_DIR, f)) and "NHD_H" in f and f.endswith('.zip')]

# Unzip
for f in nhd_zip_list:
    dest_file = os.path.join(NHD_UNZIPPED_DIR, "{0}.gdb".format(os.path.splitext(os.path.basename(f))[0]))
    if not os.path.exists(dest_file):
        zf = zipfile.ZipFile(f)
        zf.extractall(NHD_UNZIPPED_DIR)
    else:
        print("{} is already unzipped.").format(os.path.basename(dest_file))


# Step 2: Add the nhd_merge_id. It just concatenates Permanent_Identifier and FDate together so that we can
# de-duplicate merged NHD features and output features from tools that need to be run with the network data
# with methods that won't cause any misalignment.
lakes_us.batch_add_merge_ids(NHD_UNZIPPED_DIR)


# Step 3: Merge all the lakes and remove full duplicates. Also delete duplicate Permanent_Identifiers by keeping
# the feature with the most recent FDate.

# Step 3 COMMENTS: Because I may want to make the crosswalk a little more general than LAGOS lakes, I'm using any
# waterbody that is the lake or reservoir feature type without getting more specific with the FCodes just yet.

# SETUP
arcpy.env.workspace = NHD_UNZIPPED_DIR
arcpy.env.scratchWorkspace = os.getenv("TEMP")
nhd_gdbs = arcpy.ListWorkspaces('NHD_H*')
waterbody_fcs = [os.path.join(gdb, 'NHDWaterbody') for gdb in nhd_gdbs]
fc_count = len(waterbody_fcs)
all_exist_test = all(arcpy.Exists(wb) for wb in waterbody_fcs)

# EXECUTE
# Start with FC containing Lake Superior to prevent spatial grid errors
lake_superior_wb = [wb for wb in waterbody_fcs if "0401" in wb][0]
waterbody_fcs.remove(lake_superior_wb)

# This is a fast and stable merge method for this number of features compared to arcpy Merge
if all_exist_test:
    print("Beginning merge of {} feature classes".format(fc_count))
    arcpy.SetLogHistory = False # speeds up iterative updates, won't write to geoprocessing for every step
    arcpy.Select_analysis(lake_superior_wb, ALL_LAKES_FC, BROAD_LAKE_RESERVOIR_FILTER)
    insertRows = arcpy.da.InsertCursor(ALL_LAKES_FC, ["SHAPE@", "*"])

    for wb in waterbody_fcs:
        print("Merging {0} features from {1}".format(arcpy.GetCount_management(wb).getOutput(0), wb.split(nhd_parent_directory)[1]))
        searchRows = arcpy.da.SearchCursor(wb, ["SHAPE@", "*"], BROAD_LAKE_RESERVOIR_FILTER)
        for searchRow in searchRows:
            insertRows.insertRow(searchRow)
        del searchRow, searchRows
    del insertRows
    arcpy.SetLogHistory = True

else:
    print("ERROR: One or more waterbody paths is not valid. Merged waterbody feature class not created.")

# TODO: Switch back
lakes_us.deduplicate_nhd(ALL_LAKES_FC)

# TEST IT
# Check that at least some duplicates were removed
merge_count = int(arcpy.GetCount_management(ALL_LAKES_FC).getOutput(0))
inputs_count_sum = sum([int(arcpy.GetCount_management(fc).getOutput(0)) for fc in waterbody_fcs]) + int(int(arcpy.GetCount_management(lake_superior_wb).getOutput(0)))
merge_count < inputs_count_sum

# Check that the Permanent_Identifier field is now unique
unique_perm_ids_count = len(set([r[0] for r in arcpy.da.SearchCursor(ALL_LAKES_FC, "Permanent_Identifier")]))
merge_count == unique_perm_ids_count

#CLEANUP
arcpy.ResetEnvironments()

# Step 4: Select lakes intersecting United States boundaries

all_lakes_lyr = arcpy.MakeFeatureLayer_management(ALL_LAKES_FC)
states_lyr = arcpy.MakeFeatureLayer_management(US_SPATIAL_EXTENT) # Albers USGS, slower but okay
arcpy.SelectLayerByLocation_management(all_lakes_lyr, "INTERSECT", states_lyr)
arcpy.CopyFeatures_management(all_lakes_lyr, CONUS_LAKES_FC)
arcpy.Delete_management(all_lakes_lyr)

<<<<<<< HEAD
# Step 5: Repair geometry
# Optional: to see which features will change: arcpy.CheckGeometry_management(CONUS_LAKES_FC, 'in_memory/checkgeom_lakes')
# 155 self-intersections
arcpy.RepairGeometry_management(CONUS_LAKES_FC)

# Step 6: Densify features with 2 vertices (circular arcs) using 10 meters as maximum deviation (within National Map
# horizontal accuracy standards)
arcpy.AddField_management(CONUS_LAKES_FC, "VertexCount", "LONG")
arcpy.CalculateField_management(CONUS_LAKES_FC, "VertexCount", "!shape!.pointcount", "PYTHON")
conus_lakes_lyr = arcpy.MakeFeatureLayer_management(CONUS_LAKES_FC)
arcpy.SelectLayerByAttribute_management(conus_lakes_lyr, "NEW_SELECTION", "VertexCount < 4")
arcpy.Densify_edit(CONUS_LAKES_FC, "OFFSET", max_deviation = "10 Meters")
arcpy.CalculateField_management(conus_lakes_lyr, "VertexCount", "!shape!.pointcount", "PYTHON")
arcpy.Delete_management(conus_lakes_lyr)

# Step 7: Add HU2, HU4, HU6, HU8 based on reach code
arcpy.AddField_management(CONUS_LAKES_FC, "HU4", "TEXT", field_length = 4)
arcpy.AddField_management(CONUS_LAKES_FC, "HU6", "TEXT", field_length = 6)
arcpy.AddField_management(CONUS_LAKES_FC, "HU8", "TEXT", field_length = 8)
conus_lakes_lyr = arcpy.MakeFeatureLayer_management(CONUS_LAKES_FC)
arcpy.CalculateField_management(conus_lakes_lyr, "HU4", "!ReachCode![0:4]", "PYTHON")
arcpy.CalculateField_management(conus_lakes_lyr, "HU6", "!ReachCode![0:6]", "PYTHON")
arcpy.CalculateField_management(conus_lakes_lyr, "HU8", "!ReachCode![0:8]", "PYTHON")
arcpy.Delete_management(conus_lakes_lyr)

# Step 8: Remove Great Lakes, etc.
great_lakes_filter = '''HU8 IN ('04020300', '04060200', '04080300', '04090001', '04120200', '04150200') AND AreaSqKm > 10'''
with arcpy.da.UpdateCursor(CONUS_LAKES_FC, ['Permanent_Identifier','HU8', 'AreaSqKm'], where_clause = great_lakes_filter) as cursor:
    perm_ids = []
    for row in cursor:
        perm_ids.append(row[0])
        cursor.deleteRow()

# Manual step 9: Add processing note to lakes layer listing the removed Permanent_Identifiers
print(', '.join(perm_ids))


# Step 10: Project and add Area calculated in Hectares
arcpy.Project_management(CONUS_LAKES_FC, CONUS_LAKES_FC_PROJ, USGS_ALBERS_PROJ)
arcpy.AddField_management(CONUS_LAKES_FC_PROJ, "AreaHa", "DOUBLE")
conus_lakes_lyr = arcpy.MakeFeatureLayer_management(CONUS_LAKES_FC_PROJ)
arcpy.CalculateField_management(conus_lakes_lyr, "AreaHa",'!shape!.area*0.0001', "PYTHON")
arcpy.Delete_management(conus_lakes_lyr)

# Step 11: Filter for LAGOS lakes
arcpy.Select_analysis(CONUS_LAKES_FC_PROJ, LAGOS_LAKES_FC, LAGOS_LAKE_FILTER)
arcpy.AddIndex_management(LAGOS_LAKES_FC, 'Permanent_Identifier', 'IDX_Permanent_Identifier')
arcpy.AddIndex_management(LAGOS_LAKES_FC, 'nhd_merge_id', 'IDX_nhd_merge_id')

# There is one lake discrepency between my file and Alex's. It's a lake in Mexico--probably the intersect operation
# was done in different projections. Just remove that lake from my layer.
mexico_lake_mismatch_filter = '''Permanent_Identifier = 'e05e57b5-d29f-4e1e-8369-73e55f8be9df' '''
with arcpy.da.UpdateCursor(LAGOS_LAKES_FC, 'Permanent_Identifier', mexico_lake_mismatch_filter) as cursor:
    for row in cursor:
        cursor.deleteRow()




# Step 11: Repair areas of lakes that have the wrong AreaSqKm value by more than 0.1 hectare. (10 lakes, 9 of which are in 0310)
#(100*AreaSqKm) - Hectares > 0.1










# Step 6: R spatial join to WQP sites
# Is there a way to list some R code here??

=======
>>>>>>> parent of 38a20a8... change names of the variables
# Step 5: # Spatial Join to WQP sites
# Get WQP sites ready for spatial join
r_file = 'D:/Continental_Limnology/Data_Working/WQP_Sites_into_ArcGIS.shp'
arcpy.AddSpatialIndex_management(r_file)
arcpy.MakeFeatureLayer_management(r_file, "wqp_sites")
# NHD file: from deduping, above.
arcpy.MakeFeatureLayer_management(ALL_LAKES_FC, "nhd_lake_polygons")






# Spatial Intersect Only
arcpy.AddField_management()
arcpy.SelectLayerByLocation
out_file = 'D:/Continental_Limnology/Data_Working/WQP_NHD_joined.shp'
arcpy.SpatialJoin_analysis("wqp_sites", "nhd_lake_polygons", out_file, "JOIN_ONE_TO_MANY", "KEEP_ALL", match_option = "INTERSECT")


# Step 6:
# Delete the Great Lakes, Long Island Sound, Delaware Bay
updateRows = arcpy.da.UpdateCursor()
