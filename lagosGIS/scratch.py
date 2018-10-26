def merge_many(merge_list, out_fc, group_size = 20):
    """arcpy merge a list without blowing up your system
        this can be slow, but is usually better than the alternative
        if there are more than x (usually 20) files to merge, merge them in
        groups of 20 at a time to speed it up some"""
    if len(merge_list) > group_size:
        partitions = 1 + len(merge_list) // (group_size)
        multi_msg("Merging partition 1 of %s" % partitions)
        arcpy.Merge_management(merge_list[:group_size], out_fc)
        for n in range(2, partitions+1):
            multi_msg("Merging partition %s of %s" % (n, partitions))
            multi_msg(merge_list[group_size*(n-1):group_size*(n)])
            arcpy.Append_management(merge_list[group_size*(n-1):group_size*n], out_fc)
    else:
        arcpy.Merge_management(merge_list, out_fc)


arcpy.env.workspace = r'C:\Continental_Limnology\MGD_dev\Ver7Metadata\LAGOS_NE_GIS_Data.gdb'

fds = arcpy.ListDatasets()
fds.append('')
fcs = []
for fd in fds:
    fcs.append(arcpy.ListFeatureClasses(feature_dataset = fd))
fcs = [fc for fclist in fcs for fc in fclist]


import itertools
output = []
for fc in fcs:
    fields = arcpy.ListFields(fc)
    fieldnames = [f.name for f in fields if f.type <> 'OID' and f.type <> 'Geometry' and f.name <> 'Shape_Length' and f.name <> 'Shape_Area']
    print fieldnames
    output.append(zip(fieldnames, itertools.repeat((fc))))
output = [item for sublist in output for item in sublist]

import os
import csv
os.chdir('C:/Continental_Limnology/MGD_dev')
with open('fieldlist3.csv', 'wb') as f:
    writer = csv.writer(f)
    for row in output:
        writer.writerow(row)


import csv
import urllib
f = open('D:/Continental_Limnology/Downloaded_Data/NED 1-3 arc-second/ned_961.csv')
csv_f = csv.reader(f)

for row in csv_f:
    file_url = row[7]
    file_url
    urllib.urlretrieve(file_url, os.path.basename(file_url)