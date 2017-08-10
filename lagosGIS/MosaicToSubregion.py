# Filename: NHDSubregionMosaic.py
# Purpose: Mosaics NEDs to HUC6 boundary
import os
import sys
import arcpy
from arcpy import env
import fnmatch
from arcpy.da import *

# Folder containing NHD Subregion file geodatabse
arcpy.ResetEnvironments()
arcpy.env.workspace = arcpy.GetParameterAsText(0)
nhdgdb = arcpy.env.workspace
outfolder = arcpy.GetParameterAsText(1)
tilefolder = arcpy.GetParameterAsText(2)
outname = arcpy.GetParameterAsText(3)
# Projections
#   NAD83 GCS
sr = arcpy.SpatialReference()
sr.factoryCode = 4269
sr.create()

#   USGS Albers
albers = arcpy.SpatialReference()
albers.factoryCode = 102039
albers.create()

# Environments
arcpy.env.compression = "None"
arcpy.env.outputCoordinateSystem = sr
arcpy.env.pyramid = "NONE"
arcpy.env.overwriteOutput = "TRUE"

# Select the right HUC6 from WBD_HU4 and make it it's own layer.
arcpy.MakeFeatureLayer_management("NHDPoint", "NHDPoints")
arcpy.MakeFeatureLayer_management("WBD_HU4", "HU4")
arcpy.SelectLayerByLocation_management("HU4", "COMPLETELY_CONTAINS", "NHDPoints")
arcpy.CopyFeatures_management("HU4", "Subregion")

# Apply a 5000 meter buffer around subregion
arcpy.Buffer_analysis("Subregion", "Subregion_5000m_buffer", "5000 meters")

# Naming conventions
subregion_number = os.path.basename(nhdgdb)
nhdsubregion = subregion_number[4:8]



# Walk through the folder with NEDs to make a list of rasters
rasters = []
for dirpath, dirnames, filenames in arcpy.da.Walk(tilefolder,
                                                  datatype="RasterDataset",
                                                  type="TIFF"):
    for filename in filenames:
        rasters.append(os.path.join(dirpath, filename))

# Mosaic, clip and then project to USGS Albers
arcpy.MosaicToNewRaster_management(rasters, outfolder, "mosaicNAD.tif", sr, "32_BIT_FLOAT", "", "1", "BLEND")
arcpy.Clip_management(outfolder + "\\" + "mosaicNAD.tif", '', outfolder + "\\" + "tempNED13_" + nhdsubregion + ".tif", "Subregion_5000m_buffer", "0", "ClippingGeometry")
arcpy.ProjectRaster_management(outfolder + "\\" + "tempNED13_" + nhdsubregion + ".tif", outfolder + "\\" + outname + nhdsubregion + ".tif", albers, "BILINEAR", "", "", "", sr)

# Variables for intermediate data
MosaicNAD = os.path.join(outfolder, "mosaicNAD.tif")
MosaicClip = outfolder + "\\" + "tempNED13_" + nhdsubregion + ".tif"

# Clean up
arcpy.Delete_management(MosaicNAD)
arcpy.Delete_management(MosaicClip)
arcpy.Delete_management("Subregion")
arcpy.Delete_management("Subregion_5000m_buffer")

    







