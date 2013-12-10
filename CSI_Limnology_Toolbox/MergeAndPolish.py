# mergeandeliminate.py
import arcpy, os
mem = "in_memory"
arcpy.env.workspace = mem
infolder = arcpy.GetParameterAsText(0)
outname = arcpy.GetParameterAsText(1)
list = []
for root, dirs,files in arcpy.da.Walk(infolder):
    for file in files:
        list.append(os.path.join(root,file))
fc = list[1]

fcs = arcpy.ListFeatureClasses(infolder)
fms = arcpy.FieldMappings()
fm = arcpy.FieldMap()
fm.addInputField(fc,"NHD_ID")
fms.addFieldMap(fm)
arcpy.Merge_management(list, "merge", fms)
arcpy.EliminatePolygonPart_management("merge", outname, "AREA", "3.9 Hectares", "0", "CONTAINED_ONLY")

                                      