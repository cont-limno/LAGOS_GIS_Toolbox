# filename: mosaic_dem_and_tri.py
# author: Nicole J Smith
# version: 2.0
# LAGOS module(s): GEO
# tool type: code journal, modify paths by hand

import os
import subprocess
import zipfile
import arcpy

GDALDEM = r'C:\cygwin64\bin\gdaldem.exe' # version GDAL 3.3.0, released 2021/04/26

zip_dir = 'F:/Continental_Limnology/Data_Downloaded/3DEP_National_Elevation_Dataset/Zipped'
arcpy.env.snapRaster = './common_grid.tif'
arcpy.env.cellSize = './common_grid.tif'
arcpy.env.outputCoordinateSystem = arcpy.SpatialReference(5070)


zip_files = [os.path.join(zip_dir, f) for f in os.listdir(zip_dir)]
# for each file

def process_file(file):
    print(file)

    # unzip
    zf = zipfile.ZipFile(file)
    out_dir = os.path.splitext(file)[0]
    zf.extractall(out_dir)
    img_file = [os.path.join(out_dir,f) for f in os.listdir(out_dir) if f.endswith('.img')][0]

    # calc TRI
    tri_file = '{}_TRI.tif'.format(os.path.splitext(img_file)[0])
    tri_call = '{} TRI {} {} -alg Riley'.format(GDALDEM, img_file, tri_file)
    subprocess.call(tri_call)

    # warp orig to 30/30 with env settings above
    img_30 = '{}_30.tif'.format(os.path.splitext(img_file)[0])
    arcpy.Resample_management(img_file, img_30, cell_size=30, resampling_type='BILINEAR')

    # warp TRI to 30/30 with env settings above
    tri_30 = '{}_30.tif'.format(os.path.splitext(tri_file)[0])
    arcpy.Resample_management(tri_file, tri_30, cell_size=30, resampling_type='BILINEAR')

    # delete unzipped files
    all_files = os.listdir(out_dir)
    arcpy.env.workspace = out_dir
    for f in all_files:
        if os.path.basename(img_30) not in f and os.path.basename(tri_30) not in f:
            arcpy.Delete_management(f)

counter = 0
for f in zip_files:
    counter += 1
    print(counter)
    process_file(f)

os.mkdir(os.path.join(zip_dir, 'tri'))
os.mkdir(os.path.join(zip_dir, 'elevation'))
for root, dirs, files in os.walk(zip_dir):
    for file in files:
        if '_TRI_30.tif' in file:
            os.rename(os.path.join(root, file), os.path.join(zip_dir, 'tri', file))
        elif '_30.tif' in file:
            os.rename(os.path.join(root, file), os.path.join(zip_dir, 'elevation', file))



