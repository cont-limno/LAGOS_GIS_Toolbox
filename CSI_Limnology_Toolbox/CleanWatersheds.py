# Filename: cleanwatersheds.py
# Purpose: Interpolate and fill in values for watershed holes.

import os, arcpy
from arcpy.sa import *

wsraster = arcpy.GetParameterAsText(0) # Watershed raster
subregion = arcpy.GetParameterAsText(1) # Single polygon CSI subregion feature class for boundary.
seedline = arcpy.GetParameterAsText(2) # Stream lines used as seeds for watersheds
seedpoly = arcpy.GetParameterAsText(3) # Lake polys used as seeds for watersheds
outfolder = arcpy.GetParameterAsText(4) # Folder for output.

# Starting environmental variables:
arcpy.ResetEnvironments()
arcpy.env.overwriteOutput = "TRUE"
arcpy.env.extent = subregion
arcpy.env.snapRaster = wsraster
arcpy.env.cellSize = 10

# Create a scratch folder and set as current workspace.
if not os.path.exists(os.path.join(outfolder, "scratch")):
    os.mkdir(os.path.join(outfolder, "scratch"))

scratch = os.path.join(outfolder, "scratch")
arcpy.env.workspace = scratch

# Watershed raster to polygons
arcpy.RasterToPolygon_conversion(wsraster, "wspoly1.shp", '', "Value")
wspoly1 = os.path.join(scratch, "wspoly1.shp")

# Clip watershed polygons to subregion polys.
arcpy.Clip_analysis(wspoly1, subregion, os.path.join(scratch, "wsclip1.shp"))
wsclip1 = os.path.join(scratch, "wsclip1.shp")

# Calculate hectares
arcpy.AddField_management(wsclip1, "HA", "DOUBLE")
arcpy.CalculateField_management(wsclip1, "HA", '''!shape.area@hectares!''', "PYTHON")

# Create fc of watershed polygons >= 1 ha that coincide with seed lines and polys.
arcpy.MakeFeatureLayer_management(wsclip1, os.path.join(scratch, "wsclip1.lyr"))
wsclip1_lyr = os.path.join(scratch, "wsclip1.lyr")

arcpy.SelectLayerByLocation_management(wsclip1_lyr, "INTERSECT", seedline, '', "NEW_SELECTION")
arcpy.SelectLayerByLocation_management(wsclip1_lyr, "INTERSECT", seedpoly, '', "ADD_TO_SELECTION")
arcpy.SelectLayerByAttribute_management(wsclip1_lyr, "SUBSET_SELECTION",'''"HA" >= 1''')


arcpy.CopyFeatures_management(wsclip1_lyr, os.path.join(scratch, "wslegit.shp"))
wslegit = os.path.join(scratch, "wslegit.shp")

# Polygon back to raster
arcpy.PolygonToRaster_conversion(wslegit,"GRIDCODE", os.path.join(scratch, "ws_legit.tif"))
ws_legit_ras = os.path.join(scratch, "ws_legit.tif")
arcpy.Clip_management(ws_legit_ras, '', os.path.join(scratch, "ws_legit_clipped_ras.tif"),\
                      subregion, "0", "ClippingGeometry")
ws_legit_clipped_ras = os.path.join(scratch, "ws_legit_clipped_ras.tif")

# Make a raster from the subregion (boundary) polygon with zero for cell values.
arcpy.AddField_management(subregion, "Value", "SHORT")
arcpy.CalculateField_management(subregion, "Value", "0", "PYTHON")
arcpy.PolygonToRaster_conversion(subregion, "Value", os.path.join(scratch, "bnd.tif")) 
bnd_ras1 = os.path.join(scratch, "bnd.tif")
arcpy.Clip_management(bnd_ras1, '', os.path.join(scratch, "bnd_ras_clip.tif"), subregion, '', "ClippingGeometry")
bnd_ras_clip = os.path.join(scratch, "bnd_ras_clip.tif")


# Fill NoData in watersheds with the zero values from the subregion raster's cells.
composite = Con(IsNull(ws_legit_clipped_ras), bnd_ras_clip, ws_legit_clipped_ras)
composite.save(os.path.join(scratch, "composite_ras.tif"))
composite_ras = os.path.join(scratch, "composite_ras.tif")
arcpy.Clip_management(composite_ras, '', os.path.join(scratch, "composite_clip.tif"), subregion, '0', "ClippingGeometry")
composite_clip = os.path.join(scratch, "composite_clip.tif")

# Make a mask of zero cells. NoData cells are the actual mask for nibble.

premask = Con(IsNull(composite_clip), composite_clip, 0)
premask.save(os.path.join(scratch, "premask.tif"))
premask_ras = os.path.join(scratch, "premask.tif")

arcpy.Clip_management(premask_ras,'', os.path.join(scratch, "mask.tif"), subregion, '', "ClippingGeometry")
mask = os.path.join(scratch, "mask.tif")

# Set Null to 1.
prews = Con(IsNull(composite_clip), 1, composite_clip)
prews.save(os.path.join(scratch, "prews.tif"))
prews = os.path.join(scratch, "prews.tif")

# Nibble masked values (null values along boundary).
nibble = Nibble(prews, mask, "DATA_ONLY")
nibble.save(os.path.join(scratch, "nibble.tif"))
nibble_ras = os.path.join(scratch, "nibble.tif")
arcpy.Buffer_analysis(subregion, os.path.join(scratch, "subregion_buffer.shp"), "100 meters")
subregion_buffer = os.path.join(scratch, "subregion_buffer.shp")
arcpy.Clip_management(nibble_ras, "", os.path.join(outfolder, "watersheds.tif"), subregion_buffer, "NoData","ClippingGeometry")
watersheds_ras = os.path.join(outfolder, "watersheds.tif")

# Convert watershed raster to polygon.
arcpy.RasterToPolygon_conversion(watersheds_ras, os.path.join(scratch, "rawwatersheds.shp"),'', "Value")
rawwatersheds_shp = os.path.join(scratch, "rawwatersheds.shp")
arcpy.Clip_analysis(rawwatersheds_shp, subregion, os.path.join(outfolder, "watersheds.shp"))
watersheds = os.path.join(outfolder, "watersheds.shp") 

# Add and calculate a new text join field.
arcpy.AddField_management(watersheds, "JOIN", "TEXT")
arcpy.CalculateField_management(watersheds, "JOIN", '''!GRIDCODE! - 1''', "PYTHON")

# Join Permanent ID from Waterbody seed shapefile
arcpy.SpatialJoin_analysis(watersheds, seedpoly, os.path.join(outfolder, "CleanWatersheds.shp"), "", "","", "HAVE_THEIR_CENTER_IN")
















