# Filename: cleanwatersheds.py
# Purpose: Interpolate and fill in values for watershed holes.

import os, re
import arcpy
from arcpy import env
from arcpy.sa import *
import csiutils as cu

def create_csi_watersheds(flowdir, pour_dir, nhd_gdb, out_dir):

    # Starting environmental variables:
    env.extent = flowdir
    env.snapRaster = flowdir
    env.cellSize = 10

    # Create a scratch folder and set as current workspace.
    huc4_code = re.search('\d{4}', os.path.basename(nhd_gdb)).group()
    watersheds_dir = os.path.join(out_dir, 'watersheds{0}'.format(huc4_code))
    if not os.path.exists(watersheds_dir):
        os.mkdir(watersheds_dir)

    # Create the basic watersheds
    pour_points = os.path.join(pour_dir, 'pour_points.tif')
    raw_watersheds = os.path.join(watersheds_dir, 'watershed_precursor.tif')
    outWatershed = Watershed(flowdir, pour_points)
    outWatershed.save(raw_watersheds)

    # create temp directory because we need shape geometry
    temp_gdb = 'watersheds' + huc4_code
    cu.create_temp_GDB(temp_gdb)
    env.workspace = temp_gdb

    # Watershed raster to polygons
    arcpy.RasterToPolygon_conversion(raw_watersheds, "wspoly1", 'NO_SIMPLIFY', "Value")

    # Clip watershed polygons to subregion polys.
    arcpy.Clip_analysis("wspoly1", subregion, "wsclip1")

##    # Calculate hectares
##    arcpy.AddField_management("wsclip1", "HA", "DOUBLE")
##    arcpy.CalculateField_management("wsclip1", "HA", '''!shape.area@hectares!''', "PYTHON")

    # Create fc of watershed polygons >= 1 ha that coincide with seed lines and polys.
    seedline = os.path.join(pour_dir, 'pourpoints.gdb', 'eligible_flowlines')
    seedpoly = os.path.join(pour_dir, 'pourpoints.gdb', 'eligible_lakes')
    arcpy.MakeFeatureLayer_management("wsclip1", "wsclip1_lyr")

    arcpy.SelectLayerByLocation_management("wsclip1_lyr", "INTERSECT", seedline, '', "NEW_SELECTION")
    arcpy.SelectLayerByLocation_management("wsclip1_lyr", "INTERSECT", seedpoly, '', "ADD_TO_SELECTION")
    arcpy.SelectLayerByAttribute_management("wsclip1_lyr", "SUBSET_SELECTION",'''"Shape_Area" >= 10000''')

    # Polygon back to raster
    arcpy.PolygonToRaster_conversion("wsclip_lyr","GRIDCODE", "ws_legit_ras")

    arcpy.Clip_management("ws_legit_ras", '', "ws_legit_clipped_ras",
                          subregion, "0", "ClippingGeometry")

    # Make a raster from the subregion (boundary) polygon with zero for cell values.
    wbd_hu4 = os.path.join(nhd_gdb, "WBD_HU4")
    field_name = (arcpy.ListFields(wbd_hu4, "HU*4"))[0].name
    whereClause =  """{0} = '{1}'""".format(arcpy.AddFieldDelimiters(nhd_gdb, field_name), huc4_code)
    arcpy.MakeFeatureLayer_management(wbd_hu4, "subregion", whereClause)
    arcpy.AddField_management("subregion", "Value", "SHORT")
    arcpy.CalculateField_management("subregion", "Value", "0", "PYTHON")

    arcpy.PolygonToRaster_conversion("subregion", "Value","boundary_raster")
    arcpy.Clip_management("boundary_raster", '', "boundary_raster_clip", "subregion", '', "ClippingGeometry")

    # Fill NoData in watersheds with the zero values from the subregion raster's cells.
    composite = Con(IsNull("ws_legit_clipped_ras"), "boundary_raster_clip", "ws_legit_clipped_ras")
    composite.save("composite_raster")
    arcpy.Clip_management("composite_raster", '', "composite_raster_clip", "subregion", '0', "ClippingGeometry")

    # Make a mask of zero cells. NoData cells are the actual mask for nibble.
    premask = Con(IsNull("composite_raster_clip"), "composite_raster_clip", 0)
    premask.save("premask")

    arcpy.Clip_management("premask",'', "mask", subregion, '', "ClippingGeometry")

    # Set Null to 1.
    pre_watersheds = Con(IsNull("composite_raster_clip"), 1, "composite_raster_clip")
##    prews.save("prews.tif")

    # Nibble masked values (null values along boundary).
    nibble = Nibble(pre_watersheds, "mask", "DATA_ONLY")
    nibble.save("nibble")

    arcpy.Buffer_analysis("subregion", "subregion_buffer", "100 meters")
    arcpy.Clip_management("nibble", "", "watersheds_ras", "subregion_buffer", "NoData","ClippingGeometry")

    # Convert watershed raster to polygon.
    arcpy.RasterToPolygon_conversion("watersheds_ras", "rawwatersheds",'', "Value")
    arcpy.Clip_analysis("rawwatersheds", "subregion", "final_watersheds")

    # Add and calculate a new text join field.
    arcpy.AddField_management("final_watersheds", "JOIN", "TEXT")
    arcpy.CalculateField_management("final_watersheds", "JOIN", '''!GRIDCODE! - 1''', "PYTHON")

    # Join Permanent ID from Waterbody seed shapefile
    final_watersheds_out = os.path.join(watersheds_dir, 'final_watersheds.shp')
    arcpy.SpatialJoin_analysis("final_watersheds", seedpoly, final_watersheds_out, "", "","", "HAVE_THEIR_CENTER_IN")

def main():
    wsraster = arcpy.GetParameterAsText(0) # Watershed raster
    subregion = arcpy.GetParameterAsText(1) # Single polygon CSI subregion feature class for boundary.
    seedline = arcpy.GetParameterAsText(2) # Stream lines used as seeds for watersheds
    seedpoly = arcpy.GetParameterAsText(3) # Lake polys used as seeds for watersheds
    outfolder = arcpy.GetParameterAsText(4) # Folder for output.
    clean_watersheds(wsraster, subregion, seedline, seedpolyg, outfolder)
    arcpy.ResetEnvironments()

def test():
    pass

if __name__ == '__main__':
    main()









