#--------------------------------------------------------------------------------
#Name:     Ned2Subregion
# Purpose:  The purpose of this script is to create a directory of NED tiles for a NHD subregion and
#           copy in an NHD subregion file geodatabase for the purpose of HPCC processing
#
# Reqs:     1) nhdPath => file directory path of NHD subregion gdbs
#           2) nedPath => file directory path of NED tiles
#           3) finalOutPath => file directory path where output will be created
#           3) nedFootprints => fc path of projected NED tile footprint polygons
#           4) wbd => fc path to NHD subregion polygons
#
# Steps:    1) Create the output directory
#           2) Get WBD poly for subregion and Buffer it by 5000m to make sure we get enough data
#           3) Clip NED footprints wtih bufferd NHD subregion
#           4) Read list of clipped NED footprints and copy them from nedPath to finalOutPath
#           5) Copy NHD subregion gdb to finalOutPath
#
# Author:   Ed Bissell
#
# Created:   4/2/2013
#
#
#-------------------------------------------------------------------------------

import fnmatch, os, shutil, re, zipfile
import arcpy
from arcpy import env
import csiutils as cu

def stage_files(nhd_gdb, ned_dir, ned_footprints_fc, out_dir, is_zipped):
    env.workspace = 'in_memory'

    #####################################################################
    cu.multi_msg("1) Creating Directory Structure and Copying NHD Geodatabase")
    #####################################################################
    #finds the 4-digit huc code in the filename
    huc4_code = re.search('\d{4}', os.path.basename(nhd_gdb)).group()

    out_subdir = os.path.join(out_dir, "NHD" + huc4_code)
    if not os.path.exists(out_subdir):
        os.mkdir(out_subdir)
    nhd_gdb_copy  = os.path.join(out_subdir, os.path.basename(nhd_gdb))
    arcpy.Copy_management(nhd_gdb,nhd_gdb_copy)

    ####################################################################
    cu.multi_msg("2) Getting WBD Poly For Subregion and Buffering by 5000m...")
    #####################################################################

    #select only this subregion from the wbd layer in the nhd_gdb (bordering
    # subregions are included in there too) and buffer it
    wbd_hu4 = os.path.join(nhd_gdb_copy, "WBD_HU4")
    if not arcpy.Exists(wbd_hu4):
        wbd_hu4 = os.path.join(nhd_gdb_copy, "WBDHU4")
    field_name = (arcpy.ListFields(wbd_hu4, "HU*4"))[0].name
    whereClause =  """{0} = '{1}'""".format(arcpy.AddFieldDelimiters(nhd_gdb_copy, field_name), huc4_code)
    arcpy.MakeFeatureLayer_management(wbd_hu4, "wbd_poly", whereClause)
    arcpy.Buffer_analysis("wbd_poly", "wbd_buf", "5000 meters")

    #####################################################################
    cu.multi_msg("3) Clipping NED Tile polys from Buffered NHD Subregion From WBD...")
    #####################################################################
    arcpy.Clip_analysis(ned_footprints_fc, "wbd_buf", "ned_clip")

    #####################################################################
    cu.multi_msg("4) Getting File_ID of clipped NED footprint polys and copying NED data to output location")
    #####################################################################
    missing_NED_list = []
    with arcpy.da.SearchCursor("ned_clip", ["FILE_ID"]) as cursor:
        for row in cursor:
            file_id = row[0].replace("g","")

            # unzipping if needed

            if is_zipped:
                unzipped_file = unzip_ned(file_id, ned_dir, out_subdir)
                if not unzipped_file:
                    missing_NED_list.append(file_id)
            else:

                # copy ned tiles to output location
                ned_source = os.path.join(ned_dir, file_id)
                ned_destination = os.path.join(out_subdir,  file_id)
                if not os.path.exists(ned_source):
                    cu.multi_msg("ERROR: Tile %s does not exist in the specified location" % file_id)
                    missing_NED_list.append(file_id)
                else:
                    if not os.path.exists(ned_destination):
                        shutil.copytree(ned_source, ned_destination)
                    else:
                        cu.multi_msg("Output folder for this NED tile already exists.")
    if missing_NED_list:
        warning_text = "WARNING: NED tiles did not exist for the following: %s" % ','.join(missing_NED_list)
        arcpy.AddWarning(warning_text)
        print(warning_text)
    for item in ["wbd_buf", "ned_clip"]:
        arcpy.Delete_management(item)
    return out_subdir

def unzip_ned(file_id, ned_dir, out_dir):
                # clunky but this works in USA: zipped files sometimes called
                # something like n36w87 instead of n36w087 so try all 3
                filename_variants = [os.path.join(ned_dir, f) for f in [file_id + ".zip",
                file_id[0:4] + file_id[5:] + ".zip",
                file_id[0] + file_id[2:] + ".zip"]]
                filename_to_use = ''
                for f in filename_variants:
                    if not os.path.exists(f):
                        continue
                    else:
                        filename_to_use = f

                if filename_to_use:
                    cu.multi_msg("Unzipping file %s" % filename_to_use)
                    zf = zipfile.ZipFile(filename_to_use)
                    zf.extractall(out_dir)
                    return True
                else:
                    cu.multi_msg("ERROR: A tile for %s does not exist in the specified location" % file_id)
                    return False


####################################################################################################################################################
# Mosiac NED tiles and clip to subregion.
def mosaic(in_workspace, out_dir, available_ram = 4, projection = arcpy.SpatialReference(102039)) :

    # Set up environments
    env.terrainMemoryUsage = True
    env.compression = "LZ77" # compress temp tifs for speed
    env.pyramids = "NONE" # for intermediates only
    env.outputCoordinateSystem = projection

    env.workspace = in_workspace
    huc4_code = re.search('\d{4}', os.path.basename(in_workspace)).group()
    nhd_gdb = arcpy.ListWorkspaces()[0]

    # Select the right HUC4 from WBD_HU4 and make it it's own layer.
    wbd_hu4 = os.path.join(nhd_gdb, "WBD_HU4")
    if not arcpy.Exists(wbd_hu4):
        wbd_hu4 = os.path.join(nhd_gdb, "WBDHU4")
    arcpy.AddMessage(wbd_hu4)
    arcpy.AddMessage(arcpy.Exists(wbd_hu4))
    field_name = (arcpy.ListFields(wbd_hu4, "HU*4"))[0].name
    whereClause =  """{0} = '{1}'""".format(arcpy.AddFieldDelimiters(nhd_gdb, field_name), huc4_code)
    arcpy.MakeFeatureLayer_management(wbd_hu4, "Subregion", whereClause)

    # Apply a 5000 meter buffer around subregion
    subregion_buffer = os.path.join(nhd_gdb, "Subregion_Buffered_5000m")
    arcpy.Buffer_analysis("Subregion", subregion_buffer, "5000 meters")
    cu.multi_msg("Buffered subregion.")

    # Walk through the folder with NEDs to make a list of rasters
    in_workspace = r'D:\Continental_Limnology\Data_Working\Test_Watersheds\NHD0503'
    mosaic_rasters = []
    for dirpath, dirnames, filenames in arcpy.da.Walk(in_workspace, datatype="RasterDataset"):
        for filename in filenames:
            print(filename)
            if not '.jpg' in filename:
                name = os.path.join(dirpath, filename)
                mosaic_rasters.append(name)


    cu.multi_msg("Found NED rasters.")

    # Update environments
    env.extent = subregion_buffer
    approx_size_dir_GB = len(mosaic_rasters) * .5

    if approx_size_dir_GB < .5 * int(available_ram):
        env.workspace = 'in_memory'
        memory_msg = ("Attempting to use in_memory workspace. If you" +
                    " experience problems during the execution of this tool, " +
                    "try running it again with a lower value " +
                    "entered for 'Available RAM'.")
        cu.multi_msg(memory_msg)

    else:
        env.workspace = out_dir
    env.outputCoordinateSystem = mosaic_rasters[0]

    # Assign names to intermediate outputs in outfolder
    mosaic_unproj = "mosaic_t1"
    mosaic_proj = "mosaic_t2"

    # Mosaic, then project
    # Cannot do this in one step using MosaicToNewRaster's projection parameter
    # because you cannot set the cell size correctly
    cu.multi_msg("Creating initial mosaic. This may take a while...")

    arcpy.MosaicToNewRaster_management(mosaic_rasters, env.workspace,
    mosaic_unproj, "", "32_BIT_FLOAT", "", "1", "LAST")

    cu.multi_msg("Projecting mosaic...")

    arcpy.ProjectRaster_management(mosaic_unproj, mosaic_proj,
    projection, "BILINEAR", "10")

    #final mosaic environs
    env.pyramids = "PYRAMIDS -1 SKIP_FIRST" # need to check outputs efficiently
    env.outputCoordinateSystem = projection
    cu.multi_msg("Clipping final mosaic...")

    out_mosaic = os.path.join(out_dir, "NED13_%s.tif" % huc4_code)
    arcpy.Clip_management(mosaic_proj, '', out_mosaic, subregion_buffer,
     "0", "ClippingGeometry")

    # Clean up
    for item in [mosaic_unproj, mosaic_proj]:
        arcpy.Delete_management(item)
    cu.multi_msg("Mosaicked NED tiles and clipped to HUC4 extent.")

    for raster in mosaic_rasters:
        arcpy.Delete_management(raster)

    return out_mosaic


# END OF DEF mosaic

# def delete_neds(workspace):
#     os.chdir(workspace)
#     for root, dirs, files in os.walk(workspace):
#         for d in dirs:
#             if re.match('n\d+w\d+', d):
#                 print("Deleting NED folder %s" % d)
#                 shutil.rmtree(d)


def main():
    nhd_gdb = arcpy.GetParameterAsText(0)          # NHD subregion file geodatabase
    ned_dir = arcpy.GetParameterAsText(1)    # Folder containing NED ArcGrids
    ned_footprints_fc = arcpy.GetParameterAsText(2)
    out_dir = arcpy.GetParameterAsText(3)    # Output folder
    is_zipped = arcpy.GetParameter(4) # Whether NED tiles are zipped or not
    mosaic_workspace = stage_files(nhd_gdb, ned_dir, ned_footprints_fc, out_dir, is_zipped)

    available_ram = arcpy.GetParameterAsText(5)
    mosaic(mosaic_workspace, mosaic_workspace, available_ram)
    #delete_neds(mosaic_workspace)


#######################################
#TESTING
########################################
def test():
    """Tests the tool. Call from another module to test."""
    nhd_gdb = 'E:/RawNHD_byHUC/NHDH0415.gdb'
    ned_dir = 'E:/Downloaded_NED'
    ned_footprints_fc = 'C:/GISData/NED_FootPrint_Subregions.gdb/nedfootprints'
    out_dir = 'C:/GISData/Scratch'
    is_zipped = True
    available_ram = '12'

    mosaic_workspace = stage_files(nhd_gdb, ned_dir, ned_footprints_fc,
                        out_dir, is_zipped)
    mosaic(mosaic_workspace, mosaic_workspace, available_ram)
    #delete_neds(mosaic_workspace)
    arcpy.ResetEnvironments()


if __name__ == '__main__':
    main()