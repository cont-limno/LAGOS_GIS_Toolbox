# Filename: Reclassify.py
# Purpose: Reclassify Taudem D8 flow direction to the numbering scheme used by Esri flow direction

import os
import arcpy
from arcpy.sa import *
import csiutils as cu
arcpy.CheckOutExtension("Spatial")

def taudem_to_esri_flowdir(raster_list, out_dir):
    for r in raster_list:
        flowras = Raster(r)
        flowras_reclass = Reclassify(flowras, "Value",
            RemapValue([[1,1],[2,128],[3,64],[4,32],[5,16],[6,8],[7,4],[8,2]]))
        out_name = os.path.join(out_dir, os.path.basename(r).replace('p', 'esri_flowdir'))
        flowras_reclass.save(out_name)

def main():
    raster_list = arcpy.GetParameterAsText(0).split(';')
    print(raster_list)
    out_dir = arcpy.GetParameterAsText(1)
    taudem_to_esri_flowdir(raster_list, out_dir)

if __name__ == '__main__':
    main()