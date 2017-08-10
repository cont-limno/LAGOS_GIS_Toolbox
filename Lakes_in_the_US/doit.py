import os, zipfile
import arcpy
import assumptions # in this repo
import lakes_us # in this repo


# Locations. Change these for your system. To re-run this code, you can always run this whole section.
NHD_DOWNLOAD_DIR = r"D:\Continental_Limnology\Data_Downloaded\National_Hydrography_Dataset\Zipped"
NHD_UNZIPPED_DIR = r"D:\Continental_Limnology\Data_Downloaded\National_Hydrography_Dataset\Unzipped_Original"
ALL_LAKES_FC = 'D:/Continental_Limnology/Data_Working/LAGOS_US_Predecessors.gdb/NHDWaterbody_merge202_jun30_deduped'
ALL_XREF_TABLE = 'D:/Continental_Limnology/Data_Working/LAGOS_US_Predecessors.gdb/NHDReachCrossReference_all_merged'
LAKES_XREF_TABLE = 'D:/Continental_Limnology/Data_Working/LAGOS_US_Predecessors.gdb/NHDReachCrossReference_lakes'
CONUS_LAKES_FC = 'D:/Continental_Limnology/Data_Working/LAGOS_US_Predecessors.gdb/NHDWaterbody_CONUS'
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
        print("Merging {0} features from {1}".format(arcpy.GetCount_management(wb).getOutput(0), wb))
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

# Add indexes
arcpy.AddIndex_management(ALL_LAKES_FC, 'Permanent_Identifier', "IDX_Permanent_Identifier")
arcpy.AddIndex_management(ALL_LAKES_FC, 'ReachCode', 'IDX_ReachCode')

# Step 4: Merge the NHDReachCrossReference tables and de-duplicate, so we can can connect to other NHD products later
xref_tables = [os.path.join(gdb, 'NHDReachCrossReference') for gdb in nhd_gdbs]
t_count = len(xref_tables)
all_exist_test = all(arcpy.Exists(t) for t in xref_tables)

if all_exist_test:
    print("Beginning merge of {} tables".format(t_count))
    arcpy.SetLogHistory = False  # speeds up iterative updates, won't write to geoprocessing for every step
    arcpy.CopyRows_management(xref_tables.pop(0), ALL_XREF_TABLE)
    insertRows = arcpy.da.InsertCursor(ALL_XREF_TABLE, "*")

    for t in xref_tables:
        print("Merging {0} rows from {1}".format(arcpy.GetCount_management(t).getOutput(0), t))
        searchRows = arcpy.da.SearchCursor(t, "*")
        for searchRow in searchRows:
            insertRows.insertRow(searchRow)
        del searchRow, searchRows
    del insertRows
    arcpy.SetLogHistory = True

before_count = int(arcpy.GetCount_management(t).getOutput(0))
check_fields = [f.name for f in arcpy.ListFields(t) if f.name != 'OBJECTID']
arcpy.DeleteIdentical_management(ALL_XREF_TABLE, check_fields)
after_count = int(arcpy.GetCount_management(t).getOutput(0))
arcpy.AddIndex_management(ALL_XREF_TABLE, "NewReachCode", "IDX_NewReachCode")
arcpy.AddIndex_management(ALL_XREF_TABLE, "OldReachCode", "IDX_OldReachCode")


# Step 5: Select only NHDReachCrossReference rows that have a corresponding lake (the rest are stream reaches, etc.)
# with a join. For some reason, Join Field is way too slow and others have noted that. Use Add Join instead.
# Also field mappings are too annoying so copy and then delete fields instead
arcpy.MakeTableView_management(ALL_XREF_TABLE, 'xref_lyr')
arcpy.MakeTableView_management(ALL_LAKES_FC, 'lakes_lyr')
keep_fields = [f.name for f in arcpy.ListFields(ALL_XREF_TABLE)]
joined_perm_id_field = '{}_Permanent_Identifier'.format(os.path.splitext(os.path.basename(ALL_LAKES_FC))[0])
keep_fields.append(joined_perm_id_field)
arcpy.AddJoin_management('xref_lyr', 'NewReachCode', 'lakes_lyr', 'ReachCode')
print([f.name for f in arcpy.ListFields('xref_lyr')])

# Copy table, with selection
arcpy.TableToTable_conversion('xref_lyr', os.path.dirname(ALL_XREF_TABLE), os.path.basename(LAKES_XREF_TABLE), '{} is not null'.format(joined_perm_id_field.replace('_','.')))
arcpy.RemoveJoin_management('xref_lyr')

# Delete extra fields
output_fields = [f.name for f in arcpy.ListFields(LAKES_XREF_TABLE)]
for f in output_fields:
    if f not in keep_fields:
        arcpy.DeleteField_management(LAKES_XREF_TABLE, f)
arcpy.AlterField_management(LAKES_XREF_TABLE, joined_perm_id_field, new_field_name = 'New_Permanent_Identifier')

# Indexes and stuff?
arcpy.AddIndex_management(LAKES_XREF_TABLE, 'NewReachCode', 'IDX_NewReachCode')
arcpy.AddIndex_management(LAKES_XREF_TABLE, 'OldReachCode', 'IDX_OldReachCode')
arcpy.AddIndex_management(LAKES_XREF_TABLE, 'New_Permanent_Identifier', 'IDX_New_Permanent_Identifier')

arcpy.ResetEnvironments()

# Step 4: Select lakes intersecting United States boundaries

all_lakes_lyr = arcpy.MakeFeatureLayer_management(ALL_LAKES_FC)
states_lyr = arcpy.MakeFeatureLayer_management(US_SPATIAL_EXTENT) # Albers USGS, slower but okay
arcpy.SelectLayerByLocation_management(all_lakes_lyr, "INTERSECT", states_lyr)
arcpy.CopyFeatures_management(all_lakes_lyr, CONUS_LAKES_FC)
arcpy.Delete_management(all_lakes_lyr)

# Step 5: Repair geometry
# Optional: to see which features will change: arcpy.CheckGeometry_management(CONUS_LAKES_FC, 'in_memory/checkgeom_lakes')
# 155 self-intersections
arcpy.RepairGeometry_management(CONUS_LAKES_FC)

# Densify features with 2 vertices (circular arcs) using 10 meters as maximum deviation (within National Map
# horizontal accuracy standards)
arcpy.AddField_management(CONUS_LAKES_FC, "VertexCount", "LONG")
arcpy.CalculateField_management(CONUS_LAKES_FC, "VertexCount", "!shape!.pointcount", "PYTHON")
conus_lakes_lyr = arcpy.MakeFeatureLayer_management(CONUS_LAKES_FC)
arcpy.SelectLayerByAttribute_management(conus_lakes_lyr, "NEW_SELECTION", "VertexCount < 4")
arcpy.Densify_edit(CONUS_LAKES_FC, "OFFSET", max_deviation = "10 Meters")
arcpy.CalculateField_management(conus_lakes_lyr, "VertexCount", "!shape!.pointcount", "PYTHON")
arcpy.Delete_management(conus_lakes_lyr)
# Step 6: R spatial join to WQP sites
# Is there a way to list some R code here??

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
