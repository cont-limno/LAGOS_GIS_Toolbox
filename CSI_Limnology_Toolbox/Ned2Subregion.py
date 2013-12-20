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

import fnmatch, os, shutil, zipfile
import arcpy
from arcpy import env
import csiutils as cu

def stage_files(nhdPath, nedPath, wbd, nedFootprints, sr2Process, finalOutPath, zippedNED):

    #####################################################################
    cu.multi_msg("1) Creating Directory Structure and Copying NHD Geodatabase")
    #####################################################################
    srName = "NHD" + sr2Process
    gdbName = "NHDH" + sr2Process + ".gdb"
    outputDir = os.path.join(finalOutPath,"NHD" + sr2Process)
    if not os.path.exists(outputDir):
        os.mkdir(outputDir)
    nhd_source = os.path.join(nhdPath, gdbName)
    nhd_destination = os.path.join(outputDir, gdbName)

    if not os.path.exists(nhd_destination):
        shutil.copytree(nhd_source, nhd_destination)

    # set initial environments
    env.overwriteOutput = True
    arcpy.env.workspace = outputDir

    ####################################################################
    cu.multi_msg("2) Getting WBD Poly For Subregion and Buffering by 5000m")
    #####################################################################

    # Buffer only this subregion
    whereClause = "HUC_4 = '" + sr2Process + "'"
    cu.multi_msg("making featurelayer")
    arcpy.MakeFeatureLayer_management(wbd, "wbd_poly", whereClause)
    cu.multi_msg("making wbd_poly featurelayer complete")
    cu.multi_msg("buffering")
    arcpy.Buffer_analysis("wbd_poly", "in_memory/wbd_buf", 5000)
    cu.multi_msg("buffering complete")

    #####################################################################
    cu.multi_msg("3) Clipping NED Tile polys from Buffered NHD Subregion From WBD")
    #####################################################################

    arcpy.Clip_analysis(nedFootprints, "in_memory/wbd_buf", "in_memory/ned_clip")
    cu.multi_msg("clipping complete")

    #####################################################################
    cu.multi_msg("4) Getting File_ID of clipped NED footprint polys and copying NED data to output location")
    #####################################################################



    clip_fc = "in_memory/ned_clip"
    fields = ["FILE_ID"]
    missing_NED_list = []
    with arcpy.da.SearchCursor(clip_fc, fields) as cursor:
        for row in cursor:
            file_id = row[0].replace("g","")

            # unzipping if needed

            if zippedNED:
                unzipped_file = unzip_file(file_id, nedPath, outputDir)
                if not unzipped_file:
                    missing_NED_list.append(file_id)
            else:

                # copy ned tiles to output location
                ned_source = os.path.join(nedPath,file_id)
                ned_destination = os.path.join(outputDir,file_id)
                if not os.path.exists(ned_source):
                    cu.multi_msg("ERROR: Tile %s does not exist in the specified location" % file_id)
                    missing_NED_list.append(file_id)
                else:
                    if not os.path.exists(ned_destination):
                        shutil.copytree(ned_source, ned_destination)
                    else:
                        cu.multi_msg("Output folder for this NED tile already exists.")
    if missing_NED_list:
        cu.multi_msg("WARNING: NED tile directories did not exist for the following: %s" % ','.join(missing_NED_list))

def unzip_file(file_id, nedPath, outputDir):
                # clunky but this works in USA: zipped files sometimes called
                # something like n36w87 instead of n36w087 so try all 3
                filename_variants = [os.path.join(nedPath, f) for f in [file_id + ".zip",
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
                    zf.extractall(outputDir)
                else:
                    cu.multi_msg("ERROR: A tile for %s does not exist in the specified location" % file_id)
                    return False

# If module called directly, run with test parameters
if __name__ == '__main__':

    #test the script with the following parameters
    test_nhdPath = r"C:\GISData\NHD_bySubregion"
    test_nedPath = r"E:\Downloaded_NED"
    test_wbd = r"C:\GISData\Old_Watersheds.gdb\Boundaries_Basemap\HUC4_inStudyArea"
    test_nedFootprints = r"C:\GISData\Old_Watersheds.gdb\Boundaries_Basemap\NEDTiles"
    test_sr2Process = "0109"
    test_finalOutPath = r"C:\GISData\Scratch_njs"
    test_zippedNED = 'True'
    stage_files(test_nhdPath, test_nedPath, test_wbd,
                test_nedFootprints, test_sr2Process,
                test_finalOutPath, test_zippedNED)

else:
    # Otherwise when called from toolbox run the tool
    # with parameters passed

    nhdPath = arcpy.GetParameterAsText(0)          # NHD subregion file geodatabase
    nedPath = arcpy.GetParameterAsText(1)    # Folder containing NED ArcGrids
    wbd = arcpy.GetParameterAsText(2)           #FC of 4 digit HUC Subregions
    nedFootprints = arcpy.GetParameterAsText(3)
    sr2Process = arcpy.GetParameterAsText(4)    # Subregion to process, (4 digit HUC designation, include leading 0)
    finalOutPath = arcpy.GetParameterAsText(5)    # Output folder
    zippedNED = arcpy.GetParameterAsText(6) # Whether NED tiles are zipped or not

    stage_files(nhdPath, nedPath, wbd, nedFootprints, sr2Process, finalOutPath, zippedNED)
    print("Complete")