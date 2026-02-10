@echo off

set /p par1=Please enter the internal ICC file name (use brackets like "x x x" for names with spaces): 
echo.
set /p par2=Please enter the (optional) copyright description (use brackets like "x x x" for names with spaces): 
echo.
set /p par3=Enter the name of the .ti3 file created by the chartread command: 
echo.
set /p par4=Please enter the desired external name of your printer profile: 
echo.

colprof -v -qh -i D50 -o 1931_2 -S AdobeRGB1998.icc -cmt -dpp -D%par1% -C%par2% %par3%

rename %par3%.icm %par4%.icm