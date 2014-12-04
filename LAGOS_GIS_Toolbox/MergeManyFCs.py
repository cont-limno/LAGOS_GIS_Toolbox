# Filename: MergeManyFCs.py
import arcpy, os

infolder = arcpy.GetParameterAsText(0)
topoutfolder = arcpy.GetParameterAsText(1)
persub = 200
mem = "in_memory"
data = []
if not os.path.exists(os.path.join(topoutfolder, "MergeMany.gdb")):
    arcpy.CreateFileGDB_management(topoutfolder, "MergeMany.gdb")
outfolder = os.path.join(topoutfolder, "MergeMany.gdb")

for root, dirs, files in arcpy.da.Walk(infolder):
    for file in files:
        data.append(os.path.join(root,file))

chunks=[data[x:x+persub] for x in xrange(0, len(data), persub)]

for chunk in chunks:
    foldername = os.path.splitext(os.path.basename(chunk[0]))[0]
    if not os.path.exists(os.path.join(topoutfolder, foldername)):
        os.mkdir(os.path.join(topoutfolder, foldername))
    chunkfolder = os.path.join(topoutfolder, foldername)
    listfcs=[]
    for f in chunk:
        name = os.path.splitext(os.path.basename(f))[0]
        arcpy.CopyFeatures_management(f, os.path.join(chunkfolder, name + ".shp"))
        
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
        
    
        