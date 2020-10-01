# Filename: CrypticWetalnds.py
# Purpose: Raster analysis to find low flat spots (potential wetlands)
#          that aren't captured in the NWI. Then zones are converted to polygons.


import os, arcpy
from arcpy.sa import *
arcpy.CheckOutExtension("Spatial")

# Environmental settings:
mem = "in_memory"
albers = arcpy.SpatialReference()
albers.factoryCode = 102039
albers.create()
arcpy.env.outputCoordinateSystem = albers
arcpy.env.overwriteOutput = "TRUE"
arcpy.env.parallelProcessingFactor = "100%"
arcpy.env.workspace = mem

# Input parameters
slope = arcpy.GetParameterAsText(0) # degrees slope raster from gdaldem tool
tpi = arcpy.GetParameterAsText(1) # topographic position index raster from gdaldem tool
# nwi = arcpy.GetParameterAsText(2) # NWI conus_wet_poly feature class
outfolder = arcpy.GetParameterAsText(2) # output folder

# Copy input rasters to memory
arcpy.CopyRaster_management(slope, "slope")
arcpy.CopyRaster_management(tpi, "tpi")

# Find flat spots
flat = LessThan("slope", 0.25)
flat.save("flat")
flat.save(os.path.join(outfolder,"slope.tif"))
arcpy.Delete_management("slope")

# Find low spots
low = LessThan("tpi", 3)
low.save("low")
low.save(os.path.join(outfolder,"tpi.tif"))
arcpy.Delete_management("tpi")

# Find spots that are both flat and low
lowflat = BooleanAnd("flat", "low")
lowflat.save("lowflat")
lowflat.save(os.path.join(outfolder,"lowflat.tif"))
# Make into binary raster
gt = GreaterThan("lowflat", 0)
gt.save("gt")

binary = (Raster("gt") == 1)
binary.save("binary")

arcpy.Delete_management("gt")
arcpy.Delete_management("lowflat")

# Apply a filter for cleanup
maj = MajorityFilter("binary", "EIGHT")
maj.save("maj")
#maj.save(os.path.join(outfolder, "maj.tif"))

# Group cells into clusters giving the cells in the cluster the same value.
regrp = RegionGroup("maj", "EIGHT")
regrp.save("regrp")
#regrp.save(os.path.join(outfolder, "regrp.tif"))

arcpy.Delete_management("maj")

# Extract groups that are 1 hectare or larger
extract = ExtractByAttributes("regrp", '"Count" > 400')
extract.save("extract")
extract.save(os.path.join(outfolder, "wetlands.tif"))

arcpy.Delete_management("regrp")










