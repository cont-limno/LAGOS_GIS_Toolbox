# filename: mosaic_dems.py
# author: Ed Bissell, Nicole J Smith
# version: 2.0
# LAGOS module(s): LOCUS
# tool type: re-usable (ArcGIS Toolbox)
# purpose:  The purpose of this script is to create a directory of NED tiles for a NHD subregion and
#           copy in an NHD subregion file geodatabase for the purpose of HPCC processing

import os
import shutil
import re
import zipfile
import arcpy
from arcpy import env


def stage_files(nhd_gdb, ned_dir, ned_footprints_fc, out_dir, is_zipped):
    """
    Gather files to a common location on hard disk and prepare them for mosaicking.
    :param nhd_gdb: The NHD subregion for which the DEMs are being mosaicked
    :param ned_dir: Directory containing all the NED DEMs needed to create mosaic (more files can be in this directory,
    for instance all DEMS for US)
    :param ned_footprints_fc: The NED footprints polygon feature class (packaged with all NED file downloads)
    :param out_dir: The directory being used to hold ALL subregion mosaicking folders, a subdirectory for
    this subregion will be created
    :param bool is_zipped: True if NED files are stored as zips, False if they are unzipped first
    :return: The subdirectory created in the out_dir
    """

    env.workspace = 'in_memory'

    #####################################################################
    arcpy.AddMessage("1) Creating Directory Structure and Copying NHD Geodatabase")
    #####################################################################
    #finds the 4-digit huc code in the filename
    huc4_code = re.search('\d{4}', os.path.basename(nhd_gdb)).group()

    out_subdir = os.path.join(out_dir, "NHD" + huc4_code)
    if not os.path.exists(out_subdir):
        os.mkdir(out_subdir)
    nhd_gdb_copy  = os.path.join(out_subdir, os.path.basename(nhd_gdb))
    arcpy.Copy_management(nhd_gdb,nhd_gdb_copy)

    ####################################################################
    arcpy.AddMessage("2) Getting WBD Poly For Subregion and Buffering by 5000m...")
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
    arcpy.AddMessage("3) Clipping NED Tile polys from Buffered NHD Subregion From WBD...")
    #####################################################################
    arcpy.Clip_analysis(ned_footprints_fc, "wbd_buf", "ned_clip")

    #####################################################################
    arcpy.AddMessage("4) Getting File_ID of clipped NED footprint polys and copying NED data to output location")
    #####################################################################
    missing_NED_list = []
    with arcpy.da.SearchCursor("ned_clip", ["FILE_ID"]) as cursor:
        for row in cursor:
            file_id = row[0].replace("g","")
            print(file_id)
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
                    arcpy.AddMessage("ERROR: Tile %s does not exist in the specified location" % file_id)
                    missing_NED_list.append(file_id)
                else:
                    if not os.path.exists(ned_destination):
                        shutil.copytree(ned_source, ned_destination)
                    else:
                        arcpy.AddMessage("Output folder for this NED tile already exists.")
    if missing_NED_list:
        warning_text = "WARNING: NED tiles did not exist for the following: %s" % ','.join(missing_NED_list)
        arcpy.AddWarning(warning_text)
        print(warning_text)
    for item in ["wbd_poly", "wbd_buf", "ned_clip"]:
        arcpy.Delete_management(item)
    return out_subdir

def unzip_ned(file_id, ned_dir, out_dir):
    """
    Unzips NED files
    :param file_id: The file identifier code, looks like "n36w87" or "n36w087" for example
    :param ned_dir: The directory containing the NED DEM files to unzip
    :param out_dir: The directory to unzip the files to
    :return: True if file_id finds a matching file that is unzipped successfully, False when this
    function fails to create a valid unzipped file
    """

    # clunky but this works in USA: zipped files sometimes called
    # something like n36w87 instead of n36w087 so try all 3
    # plus two filename patterns
    tag_variants = [file_id, file_id[0:4] + file_id[5:], file_id[0:4] + file_id[5:]]
    pattern_variants = ['{}.zip', 'USGS_NED_13_{}_IMG.zip']
    filename_variants = []
    for t in tag_variants:
        for p in pattern_variants:
            f = os.path.join(ned_dir, p.format(t))
            filename_variants.append(f)
    filename_to_use = ''
    for f in filename_variants:
        if not os.path.exists(f):
            continue
        else:
            filename_to_use = f

    if filename_to_use:
        arcpy.AddMessage("Unzipping file %s" % filename_to_use)
        zf = zipfile.ZipFile(filename_to_use)
        zf.extractall(out_dir)
        return True
    else:
        arcpy.AddMessage("ERROR: A tile for %s does not exist in the specified location" % file_id)
        return False


####################################################################################################################################################
def mosaic(in_workspace, nhd_gdb, out_dir, available_ram=4, projection=arcpy.SpatialReference(102039)):
    """ Mosaic the NED DEM tiles and clip to subregion.
    :param in_workspace: The result of stage_files, the workspace containing all the unzipped NED files for mosaicking
    :param nhd_gdb: The subregion for which the mosaic is being created
    :param out_dir: The directory to save the mosaic to
    :param available_ram: Optional, if workstation has greater thn 4GB increase this value for faster processing
    :param projection: Optional, default is USGS Albers (102039)
    :return: Path to the mosaicked DEM
    """

    # Set up environments
    env.terrainMemoryUsage = True
    env.compression = "LZ77" # compress temp tifs for speed
    env.pyramids = "NONE" # for intermediates only
    env.outputCoordinateSystem = projection

    env.workspace = in_workspace
    huc4_code = re.search('\d{4}', os.path.basename(in_workspace)).group()

    # Select the right HUC4 from WBD_HU4 and make it it's own layer.
    wbd_hu4 = os.path.join(nhd_gdb, "WBD_HU4")
    if not arcpy.Exists(wbd_hu4):
        wbd_hu4 = os.path.join(nhd_gdb, "WBDHU4")
    field_name = (arcpy.ListFields(wbd_hu4, "HU*4"))[0].name
    whereClause =  """{0} = '{1}'""".format(arcpy.AddFieldDelimiters(nhd_gdb, field_name), huc4_code)
    arcpy.MakeFeatureLayer_management(wbd_hu4, "Subregion", whereClause)

    # Apply a 5000 meter buffer around subregion
    subregion_buffer = "in_memory/Subregion_Buffered_5000m"
    arcpy.Buffer_analysis("Subregion", subregion_buffer, "5000 meters")
    arcpy.AddMessage("Buffered subregion.")

    # Walk through the folder with NEDs to make a list of rasters
    mosaic_rasters = []
    for dirpath, dirnames, filenames in arcpy.da.Walk(in_workspace, datatype="RasterDataset"):
        for filename in filenames:
            if not '.jpg' in filename:
                name = os.path.join(dirpath, filename)
                mosaic_rasters.append(name)


    arcpy.AddMessage("Found NED rasters.")

    # Update environments
    orig_extent = env.extent
    env.extent = subregion_buffer
    approx_size_dir_GB = len(mosaic_rasters) * .5

    if approx_size_dir_GB < .5 * int(available_ram):
        env.workspace = 'in_memory'
        memory_msg = ("Attempting to use in_memory workspace. If you" +
                    " experience problems during the execution of this tool, " +
                    "try running it again with a lower value " +
                    "entered for 'Available RAM'.")
        arcpy.AddMessage(memory_msg)

    else:
        env.workspace = out_dir
    env.outputCoordinateSystem = mosaic_rasters[0]

    # Assign names to intermediate outputs in outfolder
    mosaic_unproj = "mosaic_t1"
    mosaic_proj = "mosaic_t2"

    # Mosaic, then project
    # Cannot do this in one step using MosaicToNewRaster's projection parameter
    # because you cannot set the cell size correctly
    arcpy.AddMessage("Creating initial mosaic. This may take a while...")

    arcpy.MosaicToNewRaster_management(mosaic_rasters, env.workspace,
    mosaic_unproj, "", "32_BIT_FLOAT", "", "1", "LAST")

    arcpy.AddMessage("Projecting mosaic...")

    arcpy.ProjectRaster_management(mosaic_unproj, mosaic_proj,
    projection, "BILINEAR", "10")

    #final mosaic environs
    env.pyramids = "PYRAMIDS -1 SKIP_FIRST" # need to check outputs efficiently
    env.outputCoordinateSystem = projection
    arcpy.AddMessage("Clipping final mosaic...")

    nodata = arcpy.Describe(mosaic_rasters[0]).noDataValue
    out_mosaic = os.path.join(out_dir, "NED13_%s.tif" % huc4_code)
    arcpy.Clip_management(mosaic_proj, '', out_mosaic, subregion_buffer, str(nodata), "ClippingGeometry")

    # Clean up
    for item in [mosaic_unproj, mosaic_proj, "Subregion"]:
        arcpy.Delete_management(item)
    arcpy.AddMessage("Mosaicked NED tiles and clipped to HUC4 extent.")

    env.extent = orig_extent
    return out_mosaic


def main():
    nhd_gdb = arcpy.GetParameterAsText(0)          # NHD subregion file geodatabase
    ned_dir = arcpy.GetParameterAsText(1)    # Folder containing NED ArcGrids
    ned_footprints_fc = arcpy.GetParameterAsText(2)
    out_dir = arcpy.GetParameterAsText(3)    # Output folder
    is_zipped = arcpy.GetParameter(4) # Whether NED tiles are zipped or not
    mosaic_workspace = stage_files(nhd_gdb, ned_dir, ned_footprints_fc, out_dir, is_zipped)

    available_ram = arcpy.GetParameterAsText(5)
    mosaic(mosaic_workspace, mosaic_workspace, available_ram)


if __name__ == '__main__':
    main()