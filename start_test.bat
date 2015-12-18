@echo off
echo "Starting QMITP"
rem start "" "C:\Program Files (x86)\Qualcomm\QMITestPro\Bin\QMITestPro.exe"
rem timeout /t 15
rem taskkill /f /im QMITestPro.exe

echo ###############################################################
echo # Start MDM test
echo ###############################################################
echo.


rem start C:\mdm_scripts\TC_bt_concurrent.bat
rem start C:\mdm_scripts\TC_wlan_concurrent.bat

:start
set filename=check_mdm_crash-stdout-%DATE:~-4%-%DATE:~4,2%-%DATE:~7,2%-%TIME:~0,2%%TIME:~3,2%%TIME:~6,2%.log
set filename=log\%filename: =0%
echo %filename%


perl C:\mdm_scripts\check_mdm_crash.pl | tee -a %filename%
call C:\mdm_scripts\TC_ipef_traffic_unload.bat

REM perl -w Rigel.pl $xmlfile= C:\mdm_xmls\AP_STA_ref_conn_disconn.xml| tee %filename%
REM perl -w Rigel.pl $xmlfile= C:\mdm_xmls\AP_ref_conn_disconn.xml| tee %filename%

REM call C:\mdm_scripts\TC_ap_restart_50.bat
REM call C:\mdm_scripts\TC_ap_sta_restart_50.bat
REM call C:\mdm_scripts\TC_ap_mode_switch.bat


goto :start
@echo on

