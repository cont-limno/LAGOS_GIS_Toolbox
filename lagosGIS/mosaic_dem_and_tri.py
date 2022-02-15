# filename: mosaic_dem_and_tri.py
# author: Nicole J Smith
# version: 2.0
# LAGOS module(s): GEO
# tool type: code journal, modify paths by hand
# purpose: Automate the steps to calculate TRI and convert terrain rasters to 30m in a way that conserves disk space
# while the processing is in progress

import os
import subprocess
import zipfile
import arcpy

# Locate files and specify raster processing environments
GDALDEM = r'C:\cygwin64\bin\gdaldem.exe' # version GDAL 3.3.0, released 2021/04/26

zip_dir = 'F:/Continental_Limnology/Data_Downloaded/3DEP_National_Elevation_Dataset/Zipped'
arcpy.env.snapRaster = './common_grid.tif'
arcpy.env.cellSize = './common_grid.tif'
arcpy.env.outputCoordinateSystem = arcpy.SpatialReference(5070)


def process_file(file):
    """
    Demonstrates the steps used to calculate terrain roughness index (TRI) using GDAL and the re-sampling and
    re-projection of the terrain rasters to the common 30m raster grid.
    :param file: DEM raster file from NED
    :return: None
    """
    print(file)

    # Unzip
    zf = zipfile.ZipFile(file)
    out_dir = os.path.splitext(file)[0]
    zf.extractall(out_dir)
    img_file = [os.path.join(out_dir,f) for f in os.listdir(out_dir) if f.endswith('.img')][0]

    # Calculate TRI
    tri_file = '{}_TRI.tif'.format(os.path.splitext(img_file)[0])
    tri_call = '{} TRI {} {} -alg Riley'.format(GDALDEM, img_file, tri_file)
    subprocess.call(tri_call)

    # Resample original both terrain files to 30m with cells matching common_grid.tif
    img_30 = '{}_30.tif'.format(os.path.splitext(img_file)[0])
    arcpy.Resample_management(img_file, img_30, cell_size=30, resampling_type='BILINEAR')
    tri_30 = '{}_30.tif'.format(os.path.splitext(tri_file)[0])
    arcpy.Resample_management(tri_file, tri_30, cell_size=30, resampling_type='BILINEAR')

    # Delete unzipped files upon completion
    all_files = os.listdir(out_dir)
    arcpy.env.workspace = out_dir
    for f in all_files:
        if os.path.basename(img_30) not in f and os.path.basename(tri_30) not in f:
            arcpy.Delete_management(f)


# Run all the files through
zip_files = [os.path.join(zip_dir, f) for f in os.listdir(zip_dir)]
counter = 0
for f in zip_files:
    counter += 1
    print(counter)
    process_file(f)
