# Fracking data re-shaping
# Module: GEO
# Date 2020-12-27
# Author: Nicole J Smith

library(tidyverse)
library(sf)
frk <-  read_csv("F:/Continental_Limnology/Data_Downloaded/Fracking/Pre-processed/FRAC_HUC8_US_forGEO.csv", col_types = cols(nperdecade = col_integer()))
hu8 <- read_sf('D:/Continental_Limnology/Data_Working/LAGOS_US_GIS_Data_v0.7.gdb', 'hu8')
hu4 <- read_sf('D:/Continental_Limnology/Data_Working/LAGOS_US_GIS_Data_v0.7.gdb', 'hu4')

frk_hu8 <- frk %>% 
  pivot_wider(names_from = c(decade, direction), values_from = nperdecade) %>% 
  rename_with(~paste0(.,"_n"), 3:10) %>%
  mutate(hu4_code = str_sub(hu8_code, 1, 4))

frk_hu4 <- frk_hu8 %>%
  group_by(hu4_code) %>%
  summarize(across(3:10, sum))

hu8_final <- hu8 %>%
  mutate(hu8_area_sqkm = hu8_area_ha * 0.01) %>%
  select(hu8_zoneid, hu8_sourceid_huc8, hu8_area_sqkm) %>%
  st_set_geometry(NULL) %>%
  left_join(frk_hu8, by = c("hu8_sourceid_huc8" = "hu8_code")) %>%
  mutate(across(5:12, ~replace_na(.x, 0))) %>%
  mutate(across(5:12, ~.x/hu8_area_sqkm, .names = "{hu8}_{col}persqkm")) %>%
  select(hu8_zoneid, 5:12, 14:21)

hu4_final <- hu4 %>%
  mutate(hu4_area_sqkm = hu4_area_ha * 0.01) %>%
  select(hu4_zoneid, hu4_sourceid_huc4, hu4_area_sqkm) %>%
  st_set_geometry(NULL) %>%
  left_join(frk_hu4, by = c("hu4_sourceid_huc4" = "hu4_code")) %>%
  mutate(across(4:11, ~replace_na(.x, 0))) %>%
  mutate(across(4:11, ~.x/hu4_area_sqkm, .names = "{col}persqkm")) %>%
  select(hu4_zoneid, 4:19)

write_csv(hu8_final, "D:/Continental_Limnology/Data_Working/Tool_Execution/2020-01-03_Zonal/hu8_fracking.csv")
write_csv(hu4_final, "D:/Continental_Limnology/Data_Working/Tool_Execution/2020-01-03_Zonal/hu4_fracking.csv")