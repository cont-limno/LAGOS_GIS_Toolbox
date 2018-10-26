import os, arcpy
from arcpy.sa import *
arcpy.CheckOutExtension('Spatial')
arcpy.env.overwriteOutput = True

# Parameters
zone = arcpy.GetParameterAsText(0)
idfield = arcpy.GetParameterAsText(1)
raster = arcpy.GetParameterAsText(2)
outfolder = arcpy.GetParameterAsText(3)
arcpy.RepairGeometry_management(zone)
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
    name = os.path.splitext(os.path.basename(fc))[0]
    arcpy.sa.ZonalStatisticsAsTable(fc, idfield, raster, os.path.join(outfolder, tablesgdb, name))
 
# Merging tables
arcpy.RefreshCatalog(tablesgdb)
arcpy.RefreshCatalog(outfolder)
arcpy.AddMessage("Zonal stats calculated for each poly. Attempting to merge tables...")


def mergemany(infolder,topoutfolder):
    # Filename: MergeManyGDBTables.py
    import arcpy, os

    #infolder = arcpy.GetParameterAsText(0)
    #topoutfolder = arcpy.GetParameterAsText(1)
    persub = 200
    mem = "in_memory"
    data = []
    if not os.path.exists(os.path.join(topoutfolder, "ZonalStatistics.gdb")):
        arcpy.CreateFileGDB_management(topoutfolder, "ZonalStatistics.gdb")
    outfolder = os.path.join(topoutfolder, "ZonalStatistics.gdb")

    for root, dirs, files in arcpy.da.Walk(infolder):
        for file in files:
            data.append(os.path.join(root,file))

    chunks=[data[x:x+persub] for x in xrange(0, len(data), persub)]

    for chunk in chunks:
        foldername = os.path.splitext(os.path.basename(chunk[0]))[0]
        if not os.path.exists(os.path.join(topoutfolder, foldername)):
            os.mkdir(os.path.join(topoutfolder, foldername))
        topchunkfolder = os.path.join(topoutfolder, foldername)
        arcpy.CreateFileGDB_management(topchunkfolder, foldername)
        chunkfolder = os.path.join(topchunkfolder, foldername + ".gdb")
        listfcs=[]
        for f in chunk:
            name = os.path.splitext(os.path.basename(f))[0]
            arcpy.TableToTable_conversion(f,chunkfolder,name)
            
        for root, dirs, files in arcpy.da.Walk(chunkfolder):
                for file in files:
                    listfcs.append(os.path.join(root, file))
                
                
        arcpy.Merge_management(listfcs, os.path.join(outfolder, foldername + "merge"))
        del listfcs
           
       
    fcs = []
    for root, dirs, files in arcpy.da.Walk(outfolder):
        for file in files:
            fcs.append(os.path.join(root, file))
       
           
    arcpy.Merge_management(fcs, os.path.join(outfolder, "MergeMany"))
    for file in fcs:
        arcpy.Delete_management(file)


mergemany(tablesgdb,outfolder)




