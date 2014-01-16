# Filename: Reclassify.py
# Purpose: Reclassify Taudem D8 flow direction to the numbering scheme used by Esri flow direction

import os
import arcpy
arcpy.CheckOutExtension("Spatial")

inraster = arcpy.GetParameterAsText(0)
outfolder = arcpy.GetParameterAsText(1)

flowras = Raster(inraster)

flowras_reclass = Reclassify(flowras, "Value",
            RemapValue([[1,1],[2,128],[3,64],[4,32],[5,16],[6,8],[7,4],[8,2]]))

outname = os.path.join(outfolder, "D8FDR" + os.path.basename(inraster)[3:10] + ".tif")
flowras_reclass.save(outname)