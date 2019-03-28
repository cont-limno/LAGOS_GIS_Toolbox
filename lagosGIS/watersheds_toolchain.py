from datetime import datetime as dt
from os import path
import os
import subprocess as sp
from time import sleep
from zipfile import ZipFile
import arcpy
import nhdplushr_tools as nt

TOOL_ORDER = ('update_grid_codes', 'add_lake_seeds', 'fix_hydrodem', 'fel', 'fdr',
              'delineate_catchments', 'accumulate')
# Locations of main directories (unique to machine)

# this is the result of the lakes_in_the_us/doit.py
LAGOS_LAKES = r'D:\Continental_Limnology\Data_Working\LAGOS_US_GIS_Data_v0.5.gdb\Lakes\LAGOS_US_All_Lakes_1ha'
HU4 = r'D:\Continental_Limnology\Data_Working\LAGOS_US_GIS_Data_v0.5.gdb\Spatial_Classifications\hu4'

# straight as downloaded from web in mid-March 2019
NHDPLUS_ZIPPED_DIR = 'F:\Continental_Limnology\Data_Downloaded\NHDPlus_High_Resolution\Zipped'
NHDPLUS_UNZIPPED_DIR = 'F:\Continental_Limnology\Data_Downloaded\NHDPlus_High_Resolution\Unzipped_Original'

# a directory wherever you want to store the outputs
# each subregion will have its own geodatabase created and saved
OUTPUTS_PARENT_DIR = 'D:\Continental_Limnology\Data_Working\Tool_Execution\Watersheds'

# your 7z path, probably the same
SEVENZ = r'''"C:\Program Files\7-Zip\7z.exe"'''

# ArcGIS map template path
MXD = "C:\Program Files (x86)\ArcGIS\Desktop10.3\MapTemplates\Standard Page Sizes\North American (ANSI) Page Sizes\Letter (ANSI A) Portrait.mxd"

class Paths:
    """
    Define job control paths for the 4-digit HUC4.

    :param str huc4: 4-digit HUC4 for the geodatabase to be processed.

    """
    def __init__(self, huc4, hr=True):
        self.huc4 = huc4
        self.hr = hr
        self.gdb_zip = path.join(NHDPLUS_ZIPPED_DIR, 'NHDPLUS_H_{}_HU4_GDB.zip'.format(huc4))
        self.rasters_zip = path.join(NHDPLUS_ZIPPED_DIR, 'NHDPLUS_H_{}_HU4_RASTER.7z'.format(huc4))

        # NHD items that don't exist at start
        self.gdb = path.join(NHDPLUS_UNZIPPED_DIR, 'NHDPLUS_H_{}_HU4_GDB.gdb'.format(huc4))
        self.rasters_dir = path.join(NHDPLUS_UNZIPPED_DIR, 'HRNHDPlusRasters{}'.format(huc4))
        self.waterbody = path.join(self.gdb, 'NHDWaterbody')
        self.hydrodem = path.join(self.rasters_dir, 'hydrodem.tif')
        self.catseed = path.join(self.rasters_dir, 'catseed.tif')
        self.fdr = path.join(self.rasters_dir, 'fdr.tif')

        # output items that don't exist at start
        self.out_dir = path.join(OUTPUTS_PARENT_DIR, 'watersheds_{}'.format(huc4))
        self.out_gdb = path.join(self.out_dir, 'watersheds_{}.gdb'.format(huc4))
        self.gridcode = path.join(self.out_gdb, 'lagos_gridcode_{}'.format(huc4))
        self.lagos_catseed = path.join(self.out_dir, 'lagos_catseed_{}.tif'.format(huc4))
        self.lagos_burn = path.join(self.out_dir, 'lagos_burn_{}.tif'.format(huc4))
        self.lagos_fel = path.join(self.out_dir, 'lagos_hydrodem_{}_fel.tif'.format(huc4))
        self.lagos_fdr = path.join(self.out_dir, 'lagos_fdr_{}.tif'.format(huc4))
        self.local_catchments = path.join(self.out_gdb, 'lagos_catchments_{}'.format(huc4))
        self.sheds_base = path.join(self.out_gdb, 'lagos_watersheds_{}'.format(huc4))
        self.iws_sheds = path.join(self.out_gdb, 'lagos_watersheds_{}_interlake'.format(huc4))
        self.network_sheds = path.join(self.out_gdb, 'lagos_watersheds_{}_network'.format(huc4))

    def exist(self):
        """Check whether NHDPlus data available locally in order to proceed."""
        return path.exists(self.gdb_zip) and path.exists(self.rasters_zip)

    def test_zips(self):
        """Return logical indicating whether initial paths exist."""
        test_gdb = ZipFile(self.gdb_zip, 'r').testzip()
        if test_gdb:
            print('{} has a bad file: {}'.format(self.gdb_zip, test_gdb))

        sevenz_cmd = '{} t {}'.format(SEVENZ, self.rasters_zip)
        print sevenz_cmd
        test_raster = sp.call(sevenz_cmd)

        # supposedly 7-zip returns 2 if the archive is invalid
        if test_gdb or test_raster > 0:
            return False
        else:
            return True

    def unzip(self):
        if not path.exists(self.gdb):
            with ZipFile(self.gdb_zip, 'r') as z:
                z.extractall(NHDPLUS_UNZIPPED_DIR)

        if not path.exists(self.rasters_dir):
            os.mkdir(self.rasters_dir)

        if not path.exists(self.catseed):
            sevenz_cmd = '{} e {} -o{} catseed.* fdr.* hydrodem* -r'.format(SEVENZ, self.rasters_zip, self.rasters_dir)
            sz_result = sp.call(sevenz_cmd, stdout=sp.PIPE, stderr=sp.STDOUT)
            if sz_result > 0:
                print("Problem with 7-zip. Error code {}".format(sz_result.returncode))

    def log(self, file, error_msg=''):
        """Format a comma-separated line for recording paths to logging file."""
        items = [self.huc4,
                 self.hr,
                 self.gdb_zip,
                 self.rasters_zip,
                 'NHDWaterbody; catseed.tif; fdr.tif',
                 LAGOS_LAKES,
                 self.gridcode,
                 self.lagos_catseed,
                 self.local_catchments,
                 self.iws_sheds,
                 self.network_sheds,
                 'add_waterbody_nhdpid(); update_grid_codes(); add_lake_seeds(); delineate_catchments();',
                 error_msg]
        line = ','.join([str(i) for i in items]) + '\n'
        with open(file, 'a') as file:
            file.write(line)

    def photograph(self):
        if not path.exists(self.out_dir):
            os.mkdir(self.out_dir)
        hmin = float(arcpy.GetRasterProperties_management(self.hydrodem, 'MINIMUM').getOutput(0))
        hmax = float(arcpy.GetRasterProperties_management(self.hydrodem, 'MAXIMUM').getOutput(0)) - 500000

        vals = {self.catseed:[0, 1, -32768, 50, 50], self.fdr: [0, 128, 255, 25, 25], self.hydrodem: [hmin, hmax, -2147483648, 50, 50]}
        for tif, values in vals.items():
            jpg = path.join(self.out_dir, '{}_{}.jpg'.format(path.splitext(path.basename(tif))[0], self.huc4))
            gdal_cmd = 'gdal_translate -a_nodata {} -of JPEG -co worldfile=yes -b 1 -b 1 -b 1 -scale {} {} 0 255 -outsize {}% {}% {} {}'.\
                format(values[2], values[0], values[1], values[3], values[4], tif, jpg)
            print gdal_cmd
            sp.call(gdal_cmd, stdout=sp.PIPE, stderr=sp.STDOUT)


def run(huc4, last_tool='accumulate', wait = False):
    paths = Paths(huc4)

    if last_tool:
        stop_index = TOOL_ORDER.index(last_tool)
    # Check that we have the data, otherwise log only the HUC4 (empty line) and skip
    if not paths.exist():
        raise Exception("NHDPlus HR paths do not exist on local machine.")

    if not path.exists(paths.out_dir):
        os.mkdir(paths.out_dir)
    if not path.exists(paths.out_gdb):
        arcpy.CreateFileGDB_management(path.dirname(paths.out_gdb), path.basename(paths.out_gdb))

    start_time = dt.now()

    if not path.exists(paths.catseed) and not path.exists(paths.gdb):
        arcpy.AddMessage('Unzipping started at {}...'.format(dt.now().strftime("%Y-%m-%d %H:%M:%S")))
        paths.unzip()

    # If the tool output doesn't exist yet, and the job control agrees it should be run, try running.
    # If the tool fails, continue after logging the error to the CSV.

    tool_count = 0
    # add_waterbody_nhdpid
    if not arcpy.Exists(paths.gridcode) and stop_index >= 0:
        arcpy.AddMessage('Adding NHDPlusIDs to waterbodies started at {}...'.format(dt.now().strftime("%Y-%m-%d %H:%M:%S")))
        nt.add_waterbody_nhdpid(paths.waterbody, LAGOS_LAKES)
        tool_count +=1


    # update_grid_codes
    if not arcpy.Exists(paths.gridcode) and stop_index >= 0:
        arcpy.AddMessage('Updating grid codes started at {}...'.format(dt.now().strftime("%Y-%m-%d %H:%M:%S")))
        nt.update_grid_codes(paths.gdb, paths.gridcode)
        tool_count += 1

    # add_lake_seeds
    if not arcpy.Exists(paths.lagos_catseed) and stop_index >= 1:
        arcpy.AddMessage('Adding lake seeds started at {}...'.format(dt.now().strftime("%Y-%m-%d %H:%M:%S")))
        nt.add_lake_seeds(paths.catseed, paths.gdb, paths.gridcode, LAGOS_LAKES, paths.lagos_catseed)
        tool_count += 1

    # fix_hydrodem
    if not arcpy.Exists(paths.lagos_burn) and stop_index >= 2:
        arcpy.AddMessage('Fixing hydrodem burn started at {}...'.format(dt.now().strftime("%Y-%m-%d %H:%M:%S")))
        nt.fix_hydrodem(paths.hydrodem, paths.lagos_catseed, paths.lagos_burn)
        tool_count += 1

    # fill
    if not arcpy.Exists(paths.lagos_fel) and stop_index >= 3:
        pit_start = dt.now()
        arcpy.AddMessage(
            'Pit Remove started at {}...'.format(dt.now().strftime("%Y-%m-%d %H:%M:%S")))
        pitremove_cmd = 'mpiexec -n 8 pitremove -z {} -fel {}'.format(paths.lagos_burn, paths.lagos_fel)
        sp.call(pitremove_cmd, stdout=sp.PIPE, stderr=sp.STDOUT)
        tool_count += 1
        pit_diff = dt.now() - pit_start
        arcpy.AddMessage('Pit Remove finished in {} seconds'.format(pit_diff.seconds))


    # fdr
    if not arcpy.Exists(paths.lagos_fdr) and stop_index >= 4:
        arcpy.CheckOutExtension('Spatial')
        arcpy.AddMessage('Flow direction started at {}...'.format(dt.now().strftime("%Y-%m-%d %H:%M:%S")))
        flow_dir = arcpy.sa.FlowDirection(paths.lagos_fel)
        # enforce same bounds as NHD fdr, so catchments have same HU4 boundary
        # TODO: For non-hr, clip to HU4 instead
        flow_dir_clipped = arcpy.sa.Con(arcpy.sa.IsNull(paths.fdr), paths.fdr, flow_dir)
        flow_dir_clipped.save(paths.lagos_fdr)
        arcpy.CheckInExtension('Spatial')
        tool_count += 1

    # delineate_catchments
    if not arcpy.Exists(paths.local_catchments) and stop_index >= 5:
        arcpy.AddMessage('Delineating catchments started at {}...'.format(dt.now().strftime("%Y-%m-%d %H:%M:%S")))
        nt.delineate_catchments(paths.lagos_fdr, paths.lagos_catseed, paths.gridcode, paths.local_catchments)
        tool_count += 1


    # both interlake and network watersheds
    if not arcpy.Exists(paths.iws_sheds) and stop_index >= 6:

        # wait for predecessor to exist
        # useful to split this step into 2nd process. in_memory objects won't interfere, should be safe
        if wait:
            cat_exists = arcpy.Exists(paths.local_catchments)
            while not cat_exists:
                sleep(10)
        arcpy.AddMessage(
            'Accumulating watersheds started at {}...'.format(dt.now().strftime("%Y-%m-%d %H:%M:%S")))
        nt.aggregate_watersheds(paths.local_catchments, paths.gdb, LAGOS_LAKES, paths.sheds_base, 'both')
        tool_count += 1

    time_diff = dt.now() - start_time
    print('Completed {} tools for {} in {} minutes'.format(tool_count, huc4, time_diff.seconds/60))


def make_run_list(master_HU4):
    """Make a run list that will output one huc4 from most regions first, for QA purposes."""
    regions = ['{:02d}'.format(i) for i in range(1,19)]
    subregions2 = ['{:02d}'.format(i) for i in range(1,31)]
    template = []
    for s in subregions2:
        template.extend(['{}{}'.format(r, s) for r in regions])
    huc4 = [r[0] for r in arcpy.da.SearchCursor(master_HU4, 'hu4_huc4')]
    return [i for i in template if i in huc4]


run_list = make_run_list(HU4)
log_file = r"D:\Continental_Limnology\Data_Working\Tool_Execution\Watersheds\watersheds_log.csv"
for huc4 in run_list:
    p = Paths(huc4)
    try:
        last_tool = 'accumulate'
        run(p.huc4, last_tool)
        p.log(log_file, '{}: SUCCESS'.format(last_tool))
        p.photograph()
    except Exception as e:
        p.log(log_file, repr(e))
        print(e)
        continue

# TODO: Update mosaic feature
