# Filename: cleanwatersheds.py
# Purpose: Interpolate and fill in values for watershed holes.

import os
import arcpy
from arcpy import env
from arcpy.sa import *

def clean_watersheds(wsraster, subregion, seedline, seedpoly, outfolder):

    arcpy.CheckOutExtension("Spatial")

    # Starting environmental variables:
    env.extent = subregion
    env.snapRaster = wsraster
    env.cellSize = 10

    # Create a scratch folder and set as current workspace.
    scratch = os.path.join(outfolder, "scratch")
    if not os.path.exists(scratch):
        os.mkdir(scratch)
    env.workspace = scratch

    # Watershed raster to polygons
    print('1')
    arcpy.RasterToPolygon_conversion(wsraster, "wspoly1.shp", '', "Value")

    # Clip watershed polygons to subregion polys.
    arcpy.Clip_analysis("wspoly1.shp", subregion, "wsclip1.shp")

    # Calculate hectares
    arcpy.AddField_management("wsclip1.shp", "HA", "DOUBLE")
    arcpy.CalculateField_management("wsclip1.shp", "HA", '''!shape.area@hectares!''', "PYTHON")

    # Create fc of watershed polygons >= 1 ha that coincide with seed lines and polys.
    arcpy.MakeFeatureLayer_management("wsclip1.shp", "wsclip1.lyr")

    arcpy.SelectLayerByLocation_management("wsclip1.lyr", "INTERSECT", seedline, '', "NEW_SELECTION")
    arcpy.SelectLayerByLocation_management("wsclip1.lyr", "INTERSECT", seedpoly, '', "ADD_TO_SELECTION")
    arcpy.SelectLayerByAttribute_management("wsclip1.lyr", "SUBSET_SELECTION",'''"HA" >= 1''')

    arcpy.CopyFeatures_management("wsclip1.lyr", "wslegit.shp")

    # Polygon back to raster
    print('2')
    arcpy.PolygonToRaster_conversion("wslegit.shp","GRIDCODE", "ws_legit.tif")

    arcpy.Clip_management("ws_legit.tif", '', "ws_legit_clipped_ras.tif",
                          subregion, "0", "ClippingGeometry")

    # Make a raster from the subregion (boundary) polygon with zero for cell values.
    arcpy.AddField_management(subregion, "Value", "SHORT")
    arcpy.CalculateField_management(subregion, "Value", "0", "PYTHON")
    arcpy.PolygonToRaster_conversion(subregion, "Value","bnd.tif")
    arcpy.Clip_management("bnd.tif", '', "bnd_ras_clip.tif", subregion, '', "ClippingGeometry")

    # Fill NoData in watersheds with the zero values from the subregion raster's cells.
    composite = Con(IsNull("ws_legit_clipped_ras.tif"), "bnd_ras_clip.tif", "ws_legit_clipped_ras.tif")
    composite.save("composite_ras.tif")
    arcpy.Clip_management("composite_ras.tif", '', "composite_clip.tif", subregion, '0', "ClippingGeometry")

    # Make a mask of zero cells. NoData cells are the actual mask for nibble.
    premask = Con(IsNull("composite_clip.tif"), "composite_clip.tif", 0)
    premask.save("premask.tif")

    arcpy.Clip_management("premask.tif",'', "mask.tif", subregion, '', "ClippingGeometry")

    # Set Null to 1.
    prews = Con(IsNull("composite_clip.tif"), 1, "composite_clip.tif")
    prews.save("prews.tif")

    print('3')
    # Nibble masked values (null values along boundary).
    nibble = Nibble("prews.tif", "mask.tif", "DATA_ONLY")
    nibble.save("nibble.tif")

    arcpy.Buffer_analysis(subregion, "subregion_buffer.shp", "100 meters")
    watersheds_ras = os.path.join(outfolder, "watersheds.tif")
    arcpy.Clip_management("nibble.tif", "", watersheds_ras, "subregion_buffer.shp", "NoData","ClippingGeometry")

    print('5')
    # Convert watershed raster to polygon.
    arcpy.RasterToPolygon_conversion(watersheds_ras, "rawwatersheds.shp",'', "Value")
    watersheds = os.path.join(outfolder, "watersheds.shp")
    arcpy.Clip_analysis("rawwatersheds.shp", subregion, watersheds)

    # Add and calculate a new text join field.
    arcpy.AddField_management(watersheds, "JOIN", "TEXT")
    arcpy.CalculateField_management(watersheds, "JOIN", '''!GRIDCODE! - 1''', "PYTHON")

    # Join Permanent ID from Waterbody seed shapefile
    arcpy.SpatialJoin_analysis(watersheds, seedpoly, os.path.join(outfolder, "CleanWatersheds.shp"), "", "","", "HAVE_THEIR_CENTER_IN")

    arcpy.CheckInExtension("Spatial")

def main():
    wsraster = arcpy.GetParameterAsText(0) # Watershed raster
    subregion = arcpy.GetParameterAsText(1) # Single polygon CSI subregion feature class for boundary.
    seedline = arcpy.GetParameterAsText(2) # Stream lines used as seeds for watersheds
    seedpoly = arcpy.GetParameterAsText(3) # Lake polys used as seeds for watersheds
    outfolder = arcpy.GetParameterAsText(4) # Folder for output.
    clean_watersheds(wsraster, subregion, seedline, seedpolyg, outfolder)
    arcpy.ResetEnvironments()

def test():
    wsraster = r'C:\GISData\Scratch\new_watersheds.gdb\huc08020203_watersheds_precursors'
    subregion = r'C:\GISData\Scratch\Scratch.gdb\huc08020203'
    seedline = r'C:\GISData\Scratch\new_pourpoints\pourpoints0802\pourpoints.gdb\eligible_flowlines'
    seedpoly = r'C:\GISData\Scratch\new_pourpoints\pourpoints0802\pourpoints.gdb\eligible_lakes'
    outfolder = r'C:\GISData\Scratch\scott 08020203'
    clean_watersheds(wsraster, subregion, seedline, seedpoly, outfolder)
    arcpy.ResetEnvironments()

if __name__ == '__main__':
    main()












