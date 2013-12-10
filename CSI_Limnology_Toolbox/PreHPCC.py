# Filename: PreHPCC.py
# Purpose: Mosaic NEDs to NHD subregions, burn streams and clip output to HUC8 boundaries.

import os
import shutil
import arcpy
from arcpy.sa import *
from arcpy.da import *
from arcpy import env
arcpy.CheckOutExtension("Spatial")

# User defined settings:
nhd = arcpy.GetParameterAsText(0)          # NHD subregion file geodatabase
nedfolder = arcpy.GetParameterAsText(1)    # Folder containing NED ArcGrids
outfolder = arcpy.GetParameterAsText(2)    # Output folder

# Reset environments to default
arcpy.ResetEnvironments()
arcpy.AddMessage("Reset Environments.")

# Environment settings
arcpy.env.compression = "NONE"
arcpy.env.overwriteOutput = "TRUE"
arcpy.env.pyramid = "NONE"
arcpy.env.parallelProcessingFactor = "8"
arcpy.env.workspace = nhd

# Naming Convention
subregion_number = os.path.basename(nhd)
nhdsubregion = subregion_number[4:8]

# Create output directory tree
if not os.path.exists(os.path.join(outfolder, "mosaic" + nhdsubregion)):
    os.mkdir(os.path.join(outfolder, "mosaic" + nhdsubregion))

mosaicfolder = os.path.join(outfolder, "mosaic" + nhdsubregion)   

if not os.path.exists(os.path.join(outfolder, "streamsburnt")):
    os.mkdir(os.path.join(outfolder, "streamsburnt"))

if not os.path.exists(os.path.join(outfolder, "walled")):
    os.mkdir(os.path.join(outfolder, "walled"))

if not os.path.exists(os.path.join(outfolder, "huc8clips" + nhdsubregion)):
    os.mkdir(os.path.join(outfolder, "huc8clips" + nhdsubregion))

arcpy.RefreshCatalog(outfolder)

# Create spatial reference objects:
# NAD83 GCS (Input from NHD and NED)
nad83 = arcpy.SpatialReference()
nad83.factoryCode = 4269
nad83.create()

# USGS Albers (Our project's projection)
albers = arcpy.SpatialReference()
albers.factoryCode = 102039
albers.create()


####################################################################################################################################################
# Mosiac NED tiles and clip to subregion.
def mosaic():
    global nhdsubregion
    
    # Select the right HUC4 from WBD_HU4 and make it it's own layer.
    arcpy.MakeFeatureLayer_management("WBD_HU4", "HU4")
    field = "HUC_4"
    where = '"' + field + '" = ' + "'" + str(nhdsubregion) + "'"
    arcpy.SelectLayerByAttribute_management("HU4", "NEW_SELECTION", where)
    arcpy.CopyFeatures_management("HU4", "Subregion")

    # Apply a 5000 meter buffer around subregion
    arcpy.Buffer_analysis("Subregion", "Subregion_5000m_buffer", "5000 meters")
    arcpy.AddMessage("Buffered subregion.")

    # Naming conventions for mosaic output file
    subregion_number = os.path.basename(nhd)
    nhdsubregion = subregion_number[4:8]

    # Walk through the folder with NEDs to make a list of rasters
    mosaicrasters = []
    for dirpath, dirnames, filenames in arcpy.da.Walk(nedfolder, datatype="RasterDataset"):
        for filename in filenames:
            name = os.path.join(dirpath, filename)
            mosaicrasters.append(name)

    arcpy.AddMessage("Found NED ArcGrids.")

    # Mosaic, clip and then project to USGS Albers
    arcpy.MosaicToNewRaster_management(mosaicrasters, outfolder, "mosaicNAD.tif", nad83, "32_BIT_FLOAT", "", "1", "LAST")
    arcpy.Clip_management(outfolder + "\\" + "mosaicNAD.tif", '', outfolder + "\\" + "tempNED13_" + nhdsubregion + ".tif", "Subregion_5000m_buffer", "0", "ClippingGeometry")
    tempned13 = os.path.join(outfolder, "tempNED13_" + nhdsubregion + ".tif")
    arcpy.ProjectRaster_management(tempned13, os.path.join(mosaicfolder, "NED13_" + nhdsubregion + ".tif"), albers, "BILINEAR", "10", "", "", nad83)
    arcpy.AddMessage("Mosaiced, clipped and projected NED tiles.")

    # Variables for intermediate data
    MosaicNAD = os.path.join(outfolder, "mosaicNAD.tif")
    MosaicClip = outfolder + "\\" + "tempNED13_" + nhdsubregion + ".tif"
    subregion_ned = outfolder + "\\" + "mosaic" + nhdsubregion + "\\" + "NED13_" + nhdsubregion + ".tif"
    global subregion_ned
    
    # Clean up
    arcpy.Delete_management(MosaicNAD)
    arcpy.Delete_management(MosaicClip)
    arcpy.Delete_management("Subregion")
    arcpy.Delete_management("Subregion_5000m_buffer")
    arcpy.AddMessage("Cleaned up intermediate data from mosaic tool. Mosaic done.")
    return
mosaic()

################################################################################################################################################

# Setting snapraster output coordinates and extent to the subregion NED mosaic raster.
arcpy.env.extent = subregion_ned
arcpy.env.snapRaster = subregion_ned
arcpy.env.outputCoordinateSystem = subregion_ned

#################################################################################################################################################
# Burning Streams

def burn():
    
    # Start burning streams

    # Export NHDFlowlines to temp shapefile (can't project directly beause of geometric network)
    arcpy.FeatureClassToShapefile_conversion("NHDFlowline", outfolder)
    FlowlineNAD83shp = os.path.join(outfolder, "NHDFlowline.shp")
    arcpy.AddMessage("Made temporary shapefile from NHDFlowline.")

    # Project NHDFlowline
    arcpy.Project_management(FlowlineNAD83shp, outfolder + "\\" + "FlowlineAlbers.shp", albers, "", nad83)
    Flowline = os.path.join(outfolder, "FlowlineAlbers.shp")
    arcpy.AddMessage("Projected temporary NHDFlowline shapefile to EPSG 102039.")

    # Feature to Raster- rasterize the NHDFlowline
    arcpy.FeatureToRaster_conversion(Flowline, "FID", outfolder + "\\" + "FlowlineRas.tif", "10")
    FlowlineRas = os.path.join(outfolder, "FlowlineRas.tif")
    arcpy.AddMessage("Converted flowlines to raster.")

    # Greater Than - makes raster flowline binary
    outGreaterThan = GreaterThan(FlowlineRas, 0)
    outGreaterThan.save(outfolder + "\\" + "BinaryRas.tif")
    arcpy.env.rasterStatistics = 'STATISTICS'
    BinaryRas = os.path.join(outfolder, "BinaryRas.tif")
    arcpy.AddMessage("Made flowlines raster binary.")


    # Reclassify - changes NoData values to zeros in BinaryRas
    arcpy.gp.Reclassify_sa(BinaryRas,"Value","1 1;NODATA 0", outfolder + "\\" + "FlowReclas.tif" )
    FlowReclas = os.path.join(outfolder, "FlowReclas.tif")
    arcpy.AddMessage("Changed Nodata values in flowline raster to zeros")

    # Euclidean Distance - distance from flowlines (must be performed on projected data, not gcs)
    arcpy.gp.EucDistance_sa(Flowline, outfolder + "\\" + "Distance.tif" ,"#","10","#")
    Distance = os.path.join(outfolder, "Distance.tif")
    arcpy.AddMessage("Made a Euclidean Distance raster that shows distance from flowlines")

    # Raster Calculator- burns in streams, beveling in from 500m
    burnt = Raster(subregion_ned) - 10 * Raster(FlowReclas) - 0.02 * (500 - Raster(Distance)) * (Raster(Distance) < 500)
    burnt.save(outfolder + "\\" + "streamsburnt" + "\\" + "Burnt_" + nhdsubregion + ".tif")
    arcpy.AddMessage("Burnt the streams into the NED 10m deep and beveling in from 500m out.")
    burnt_ned = outfolder + "\\" + "streamsburnt" + "\\" + "Burnt_" + nhdsubregion + ".tif"
    global burnt_ned
    # Delete intermediate rasters and shapefiles
    arcpy.Delete_management(BinaryRas)

    #arcpy.Delete_management(FlowlineRas)
    arcpy.Delete_management(FlowReclas)
    arcpy.Delete_management(Distance)
    arcpy.DeleteFeatures_management(FlowlineNAD83shp)
    arcpy.DeleteFeatures_management(Flowline)
    flowlinealbers = os.path.join(outfolder, "FlowlineAlbers.shp")
    arcpy.DeleteFeatures_management(flowlinealbers)
    nhdflowlineshp = os.path.join(outfolder, "NHDFlowline.shp")
    arcpy.DeleteFeatures_management(nhdflowlineshp)
    arcpy.AddMessage("Cleaned up temporary files from intermediate burn steps.")
    arcpy.AddMessage("Burn process completed")
    return
burn()

###############################################################################################################################################

def clip():
    
    arcpy.env.workspace = nhd
    arcpy.RefreshCatalog(nhd)
    arcpy.ResetEnvironments()

    # Burnt and walled mosaiced elevation
    raster = burnt_ned

    # Create a feature dataset in NHD file geodatabase named "HUC8_Albers" in Albers projection
    workspace = arcpy.ListWorkspaces("*", "FileGDB")
    sr = arcpy.SpatialReference()
    sr.factoryCode = 102039
    sr.create()
    arcpy.env.outputCoordinateSystem = sr
    arcpy.env.compression = "None"
    arcpy.env.pyramid = "NONE"
    arcpy.CreateFeatureDataset_management(arcpy.env.workspace, "HUC8_Albers", sr)

    # HUC8 polygon selected automaticly from input workspace
    inhuc8 = "WBD_HU8"
    inhuc8albers = "WBD_HU8_Albers"

    # Project WBD_HU8 to Albers
    srin = arcpy.SpatialReference()
    srin.factoryCode = 4269
    srin.create()

    arcpy.Project_management(inhuc8, "HUC8_Albers\WBD_HU8_Albers", sr, '', srin)

    # Output goes to feature dataset HUC8_Albers
    outfd = "HUC8_Albers"

    # Splits HUC8 into individual feature classes for each polygon
    arcpy.AddField_management("WBD_HU8_Albers", "Label", "TEXT")
    arcpy.RefreshCatalog(nhd)
    calcexp = '"HUC" + !HUC_8!'
    arcpy.CalculateField_management("WBD_HU8_Albers", "Label", calcexp, "PYTHON")
    if not os.path.exists(os.path.join(outfolder, "cliptemp")):
        os.mkdir(os.path.join(outfolder, "cliptemp"))
    cliptemp = os.path.join(outfolder, "cliptemp")
    arcpy.FeatureClassToShapefile_conversion("WBD_HU8_Albers", cliptemp)
    wbdshp = os.path.join(cliptemp, "WBD_HU8_Albers.shp")
    arcpy.Split_analysis(wbdshp, wbdshp, "Label", outfd, '')
    shutil.rmtree(cliptemp)
    
    # Buffer HUC8 feature classes by 5000m
    fcs = arcpy.ListFeatureClasses("", "Polygon", "HUC8_Albers")
    for fc in fcs:
        arcpy.Buffer_analysis(fc, outfd + "\\" + fc + "_buffer", "5000 meters")

    arcpy.RefreshCatalog(nhd)
    arcpy.ResetEnvironments()

    # Clips rasters
    fcs = arcpy.ListFeatureClasses("*_buffer", "Polygon", "HUC8_Albers")
    for fc in fcs:
        arcpy.env.compression = "None"
        arcpy.env.pyramid = "NONE"
        fcshort = fc[3:11]
        arcpy.Clip_management(raster, '', outfolder + "\\" + "huc8clips" + nhdsubregion + "\\" + "NED" + fcshort + ".tif", fc, "0", "ClippingGeometry")


    return

clip()

#################################################################################################################################################
# Clean up remaining temp files
arcpy.AddMessage("Cleaning up remaining temp files...")
string = 'NED'
for root, dirs, filenames in os.walk(outfolder):
 for filename in filenames:
    if not string in filename: # If NED isn't in the filename
      remfilename = os.path.join(root, filename) # Get the absolute path to the file.
      os.remove(remfilename) # Remove the file
try:
    arcpy.Delete_management(os.path.join(outfolder, "huc8clips" + nhdsubregion, "NED_HU8_Alb.tif"))

except:
    pass
try:
    shutil.rmtree(os.path.join(outfolder, "streamsburnt"))
    shutil.rmtree(os.path.join(outfolder, "walled"))
except:
    pass
################################################################################################################################################   




