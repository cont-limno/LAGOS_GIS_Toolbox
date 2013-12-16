# Filename: Export2CSV.py
import arcpy, os, csv
fc = arcpy.GetParameterAsText(0)
outfolder = arcpy.GetParameterAsText(1)

name = os.path.splitext(os.path.basename(fc))[0]

csv = os.path.join(outfolder, name + ".csv")
                        

def TableToCSV(fc,CSVFile):
    
    fields = [f.name for f in arcpy.ListFields(fc) if f.type <> 'Geometry']
    with open(CSVFile, 'w') as f:
        f.write(','.join(fields)+'\n') #csv headers
        with arcpy.da.SearchCursor(fc, fields) as cursor:
            for row in cursor:
                f.write(','.join([str(r) for r in row])+'\n')
    

if __name__ == '__main__':

 
    


    TableToCSV(fc, csv)
    