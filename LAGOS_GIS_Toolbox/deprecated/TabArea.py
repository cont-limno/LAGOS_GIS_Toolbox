

# Imports...
import arcpy
from arcpy.sa import *
import multiprocessing
import os
import shutil

infolder = arcpy.GetParameterAsText(0)
raster = arcpy.GetParameterAsText(1)
global raster
global infolder
try:
    os.mkdir(os.path.join(infolder, "TabAreaTables"))
except:
    pass
outfolder = os.path.join(infolder, "TabAreaTables")

def tabarea(fc):

    import arcpy
    name = os.path.splitext(os.path.basename(fc))[0]
    inraster = Raster[raster]
    mem = "in_memory"
    tatable = TabulateArea(fc, "FID", inraster, "Value", os.path.join(mem, name + "areas"))
    arcpy.Copy_management(tatable, os.path.join(outfolder, name + ".dbf"))
    arcpy.Delete_management(os.path.join(mem, name + "areas"))
    del tatable
    del name
   
def main():
    fclist = []
    for root, dirs, files in arcpy.da.Walk(infolder):
        for file in files:
            fclist.append(os.path.join(root, file))
    

    pool = multiprocessing.Pool()

    pool.map(tabarea, fclist)

    pool.close()
    pool.join()
if __name__ == "__main__":
    main()
                          

    
  
        

    

  