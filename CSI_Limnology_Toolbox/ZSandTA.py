import arcpy, os, multiprocessing
from arcpy.sa import *
import string
import sys
arcpy.CheckOutExtension("Spatial")
arcpy.env.overwriteOutput = True
#################################################################################################
# Parameters
inzone = arcpy.GetParameterAsText(0)
infield = arcpy.GetParameterAsText(1)
raster = arcpy.GetParameterAsText(2)
outfolder = arcpy.GetParameterAsText(3)
joinfield = arcpy.GetParameterAsText(4)
#################################################################################################        
polyname = os.path.basename(inzone)
if not os.path.exists(os.path.join(outfolder, polyname)):
    os.mkdir(os.path.join(outfolder, polyname))
tablefolder = os.path.join(outfolder, polyname)

arcpy.env.extent = inzone
# Set workspace to be in RAM
arcpy.Delete_management("in_memory")

mem = "in_memory"
arcpy.env.workspace = mem

arcpy.Delete_management(mem)

# Copy inzone to mem
arcpy.CopyFeatures_management(inzone, "zone")
zone = os.path.join(mem, "zone")


# Make a field that's a text copy of the input field
arcpy.AddField_management(zone, "zone", "TEXT")
arcpy.CalculateField_management(zone, "zone",'!%s!' % (str(infield)), "PYTHON")
arcpy.AddField_management(zone, "tempid", "TEXT")
arcpy.CalculateField_management(zone, "tempid",'"zs" + !zone!' , "PYTHON")

# Drop all non-required fields except the zonefield
deletefields = []
fields = arcpy.ListFields(zone)
for field in fields:
    if not field.required:
        deletefields.append(field.name)
for field in fields:
    if field.name in infield:
        try:
            deletefields.remove(field.name)
        except:
            pass
    if field.name in 'tempid':
        try:
            deletefields.remove(field.name)
        except:
            pass
    if field.name in 'zone':
        try:
            deletefields.remove(field.name)
        except:
            pass

arcpy.DeleteField_management(zone, deletefields)

# Split so each feature becomes its own feature class in RAM (you need lots of ram for lots of features)
arcpy.AddMessage("Started splitting features...")
arcpy.Split_analysis(zone, zone, "tempid", mem)
arcpy.AddMessage("Done Splitting features.")

arcpy.RefreshCatalog(outfolder)
            
fcs = arcpy.ListFeatureClasses("*")

arcpy.AddMessage("Starting iteration.")
for fc in fcs:
    name = os.path.basename(fc)
    zstable = ZonalStatisticsAsTable(fc, infield, raster, os.path.join(mem, name + "zonal"))
    tatable = TabulateArea(fc, infield, raster, "Value", os.path.join(mem, name + "areas"))
    arcpy.Delete_management(fc)
    
arcpy.AddMessage("Finished iteration. Starting merge.")
list = arcpy.ListTables("*zonal")
arcpy.Merge_management(list, os.path.join(tablefolder, "ZonalStats.dbf"))
finalzs = os.path.join(tablefolder, "ZonalStats.dbf")
list2 = arcpy.ListTables("*areas")
arcpy.Merge_management(list2, os.path.join(tablefolder, "TabulatedAreas.dbf"))
finalta = os.path.join(tablefolder, "TabulatedAreas.dbf")
arcpy.JoinField_management(finalzs,infield,inzone,infield, [joinfield])
arcpy.JoinField_management(finalta,infield,inzone,infield, [joinfield])
arcpy.AddMessage("Done.")









                           

