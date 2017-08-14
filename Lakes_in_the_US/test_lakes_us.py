import lakes_us


def efficient_merge(out_fc, filter=''):
    fcs = [
        r'D:\Continental_Limnology\Data_Downloaded\National_Hydrography_Dataset\Unzipped_Original\NHD_H_0101_GDB.gdb\Hydrography\NHDWaterbody',
        r'D:\Continental_Limnology\Data_Downloaded\National_Hydrography_Dataset\Unzipped_Original\NHD_H_0102_GDB.gdb\Hydrography\NHDWaterbody',
        r'D:\Continental_Limnology\Data_Downloaded\National_Hydrography_Dataset\Unzipped_Original\NHD_H_0103_GDB.gdb\Hydrography\NHDWaterbody']

    lakes_us.efficient_merge(fcs, out_fc, filter)
