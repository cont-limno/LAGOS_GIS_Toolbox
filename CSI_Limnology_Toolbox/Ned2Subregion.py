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

import os,fnmatch
import arcpy
from arcpy import env
import shutil


arcpy.env.overwriteOutput = True


# User defined settings:
nhdPath = arcpy.GetParameterAsText(0)          # NHD subregion file geodatabase
nedPath = arcpy.GetParameterAsText(1)    # Folder containing NED ArcGrids
wbd = arcpy.GetParameterAsText(2)           #FC of 4 digit HUC Subregions
nedFootprints = arcpy.GetParameterAsText(3)  
sr2Process = arcpy.GetParameterAsText(4)    # Subregion to process, (4 digit HUC designation, include leading 0)
finalOutPath = arcpy.GetParameterAsText(5)    # Output folder

#nhdPath = "C:/NHD"
#nedPath = "C:/NED"
#wbd = "S:/FWL/labs/soranno/CSIGIS/GISData/NED_FootPrint_Subregions.gdb/HUC_4"
#nedFootprints = "S:/FWL/labs/soranno/CSIGIS/GISData/NED_FootPrint_Subregions.gdb/nedfootprints"
#nedFootprints = "C:/Dropbox/PrivatEd/NEDProcessing/NED_FootPrint_Subregions.gdb/nedfootprints"
#sr2Process = "0508"
#finalOutPath = "C:/PreHPCC"

#Store intermediate data in memory rather than writing out to disk
outPath = "in_memory"


def Run():

    #####################################################################
    print "1) Creating Directory Structure and Copying NHD Geodatabase"
    #####################################################################
    srName = "NHD" + sr2Process
    gdbName = "NHDH" + sr2Process + ".gdb"
    outputDir = os.path.join(finalOutPath,"NHD" + sr2Process)
    if not os.path.exists(outputDir):
        os.mkdir(outputDir)
    if not os.path.exists(os.path.join(outputDir,gdbName)):
        shutil.copytree(os.path.join(nhdPath,gdbName), (os.path.join(outputDir,gdbName)))


    ####################################################################
    print "2) Getting WBD Poly For Subregion and Buffering by 5000m"
    #####################################################################
    arcpy.env.workspace = wbd
    whereClause = "HUC_4 = '" + sr2Process + "'"
    print("making featurelayer")
    arcpy.MakeFeatureLayer_management(wbd, "wbd_poly", whereClause)
    print("making wbd_poly featurelayer complete")
    print("buffering")
    arcpy.Buffer_analysis("wbd_poly", outPath + os.sep + "wbd_buf", 5000) 
    print("buffering complete")

    #####################################################################
    print "3) Clipping NED Tile polys from Buffered NHD Subregion From WBD"
    #####################################################################
    ##tempData = arcpy.CreateScratchName(workspace=arcpy.env.scratchGDB)   
    arcpy.Clip_analysis(nedFootprints, outPath + os.sep + "wbd_buf", outPath + os.sep + "ned_clip")
    print("clipping complete")

    #####################################################################
    print "4) Getting File_ID of clipped NED footprint polys and copying NED data to output location"
    #####################################################################
    fc = outPath + os.sep + "ned_clip"
    fields = ["FILE_ID"]
    with arcpy.da.SearchCursor(fc,fields) as cursor:
        for row in cursor:
            file_id = row[0].replace("g","")
            print(file_id)
            ## copy ned tiles to output location
            if not os.path.exists(os.path.join(nedPath,file_id)):
                print("ERROR: Tile " + file_id + " does not exist in the specified location")            
            else:
                if not os.path.exists(os.path.join(outputDir,file_id)):
                    shutil.copytree(os.path.join(nedPath,file_id), (os.path.join(outputDir,file_id)))

Run()
print("Complete")