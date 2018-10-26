# Filename: MergeManyShapefiles.py
import arcpy, os

infolder = arcpy.GetParameterAsText(0)
topoutfolder = arcpy.GetParameterAsText(1)
persub = 200

data = []
if not os.path.exists(os.path.join(topoutfolder, "MergeMany")):
    os.mkdir(os.path.join(topoutfolder, "MergeMany"))
outfolder = os.path.join(topoutfolder, "MergeMany")

for root, dirs, files in arcpy.da.Walk(infolder):
    for file in files:
        data.append(os.path.join(root,file))

chunks=[data[x:x+persub] for x in xrange(0, len(data), persub)]

for chunk in chunks:
    foldername = os.path.splitext(os.path.basename(chunk[0]))[0]
    if not os.path.exists(os.path.join(outfolder, foldername)):
        os.mkdir(os.path.join(outfolder, foldername))
    chunkfolder = os.path.join(outfolder, foldername)
    listfcs=[]
    for f in chunk:
        name = os.path.splitext(os.path.basename(f))[0]
        arcpy.CopyFeatures_management(f, os.path.join(chunkfolder, name))
        
    for root, dirs, files in arcpy.da.Walk(chunkfolder):
            for file in files:
                listfcs.append(os.path.join(root, file))
            
            
    arcpy.Merge_management(listfcs, os.path.join(chunkfolder, foldername + "merge.shp"))
    del listfcs
        
    
finalmergefcs = []
for root, dirs, files, in arcpy.da.Walk(outfolder):
    for file in files:
        if file.endswith("merge.shp"):
            finalmergefcs.append(os.path.join(root, file))

arcpy.Merge_management(finalmergefcs, os.path.join(topoutfolder, "MergeMany.shp"))
        
    
        