# Filename: MergeManyGDBTables.py
import arcpy, os

infolder = arcpy.GetParameterAsText(0)
topoutfolder = arcpy.GetParameterAsText(1)
persub = 200
mem = "in_memory"
data = []
if not os.path.exists(os.path.join(topoutfolder, "MergeManyGDBTables.gdb")):
    arcpy.CreateFileGDB_management(topoutfolder, "MergeManyGDBTables.gdb")
outfolder = os.path.join(topoutfolder, "MergeManyGDBTables.gdb")

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


        
    
        