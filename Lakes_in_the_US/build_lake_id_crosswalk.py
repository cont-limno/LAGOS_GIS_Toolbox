import csv, os, urllib
import arcpy


ALL_LAKES_FC = 'D:/Continental_Limnology/Data_Working/LAGOS_US_Predecessors.gdb/NHDWaterbody_merge202_jun30_deduped'
ALL_XREF_TABLE = 'D:/Continental_Limnology/Data_Working/LAGOS_US_Predecessors.gdb/NHDReachCrossReference_all_merged'
LAKES_XREF_TABLE = 'D:/Continental_Limnology/Data_Working/LAGOS_US_Predecessors.gdb/NHDReachCrossReference_lakes'
CONUS_LAKES_FC = 'D:/Continental_Limnology/Data_Working/LAGOS_US_Predecessors.gdb/NHDWaterbody_CONUS'
NHDPLUS_V21_WATERBODIES = r'D:\Not_ContLimno\NHDPlus V2\NHDPlusNationalData\NHDPlusV21_National_Seamless.gdb\NHDSnapshot\NHDWaterbody'
NLA_2007_URL = 'https://www.epa.gov/sites/production/files/2014-01/nla2007_sampledlakeinformation_20091113.csv'
NLA_2012_URL = 'https://www.epa.gov/sites/production/files/2016-12/nla2012_wide_siteinfo_08232016.csv'

# Step 1--Convert NLA URLs to datasets--reproducible
nla_2007 = urllib.URLopener(NLA_2007_URL)
