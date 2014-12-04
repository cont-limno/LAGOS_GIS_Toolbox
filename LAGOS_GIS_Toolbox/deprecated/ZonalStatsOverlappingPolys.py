import os, arcpy
from arcpy.sa import *
arcpy.CheckOutExtension('Spatial')
arcpy.env.overwriteOutput = True

# Parameters
zone = arcpy.GetParameterAsText(0)
idfield = arcpy.GetParameterAsText(1)
raster = arcpy.GetParameterAsText(2)
outfolder = arcpy.GetParameterAsText(3)

# Creating temp tables geodatabase.
try:
    arcpy.CreateFileGDB_management(outfolder, "tables")
except:
    arcpy.AddMessage("Failed to create temp 'tables.gdb'")
    pass
tablesgdb = os.path.join(outfolder, "tables.gdb")

# Creating output "ZonalStats" geodatabase.
try:
    arcpy.CreateFileGDB_management(outfolder, "ZonalStats")
except:
    arcpy.AddMessage("Failed to create 'ZonalStats.gdb' for output.")
    pass
outgdb = os.path.join(outfolder, "ZonalStats.gdb")

# Adding a temporary id field to zones
try:
    arcpy.AddField_management(zone, "tempid", "TEXT")
except:
    arcpy.AddMessage("Failed to add the field 'tempid' to the zone feature class. It might already exist. Continuing if it does...")
    pass
arcpy.CalculateField_management(zone, "tempid", '''"temp" + str(!OBJECTID!)''', "PYTHON")

# Splitting zones into single polygon feature classes
mem = "in_memory"
arcpy.env.workspace = mem
arcpy.Split_analysis(zone, zone, "tempid", mem, "10 meters")
arcpy.AddMessage("Done splitting zones.")

# Listing feature classes and performing zonal stats on each individually
fclist = arcpy.ListFeatureClasses("*")
fcs = []
for fc in fclist:
    fcs.append(os.path.join(mem,fc))
    

for fc in fcs:
    arcpy.RepairGeometry_management(fc)
    name = os.path.splitext(os.path.basename(fc))[0]
    arcpy.sa.ZonalStatisticsAsTable(fc, idfield, raster, os.path.join(outfolder, tablesgdb, name))
 
# Merging tables
arcpy.RefreshCatalog(tablesgdb)
arcpy.RefreshCatalog(outfolder)
arcpy.AddMessage("Zonal stats calculated for each poly. Attempting to merge tables...")
tables = []
for root, dirs, files in arcpy.da.Walk(tablesgdb):
    for file in files:
        tables.append(os.path.join(root, file))
rastername = os.path.splitext(os.path.basename(raster))[0]
arcpy.Merge_management(tables, os.path.join(outgdb, rastername))
arcpy.Delete_management(tablesgdb)


arcpy.AddMessage("All processes complete.")
        





