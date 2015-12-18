use strict;
use warnings;
use Data::Dumper;
use XML::Simple;
use File::Spec;
use File::Path qw(mkpath rmtree);
use LWP::UserAgent;
use ASIA_Main;

my $log_file = 'check_mdm_crash.log';
my $Update_Test_Status_URL = "http://10.231.194.75:8080/mdm/tbd";
our $APS = "APS.1";
our ($Phone, $Phone8k);
my $hostname = uc(`hostname`);   # Global variable
my $local_ip = get_ip('192.168.3.');

chomp($hostname);
my $current_file = __FILE__;
if ($current_file =~ /([^\\\/]+)$/) {
    $current_file = $1;
    printlog("Current file name $current_file!");
}

our $ACS_JiraConfig = "c:\\dropbox\\CrashScope.xml";   # If defined in RigelStationParams, it would override command line

our $APS_USB_Upload_Root_Directory;   # Not in files, only command line
our $ACS_MetaBuild;
read_xml_conf('c:\\Rigel\\RigelStationParams.xml');

my @time = localtime(time);
my $crash_log_timestamp = "$local_ip($hostname)\_" . ($time[5]+1900) . "_" . ($time[4]+1) . "_$time[3]_$time[2]_$time[1]_$time[0]";
$APS_USB_Upload_Root_Directory = File::Spec->catfile($APS_USB_Upload_Root_Directory, $crash_log_timestamp);

my $QPSTLaunched = 0;
launch_QPST();
mkpath($APS_USB_Upload_Root_Directory);
ASIA_Initialize();

my $USBUploadMode= "PassiveForAllocation";
printlog("USBUploadMode= $USBUploadMode");
my $APSResourceNumber;
printlog("Allocate $APS");
my @ResourceList = ( "Phone",      $APS,     { Persistence => $PERSISTENT_NEW, UsbUploadMode => $USBUploadMode} );
$APSResourceNumber = $APS;
$APSResourceNumber =~ /\.(\d+)$/;
$APSResourceNumber = $1;

my $DeviceID = $hostname . "_" . $APSResourceNumber;
printlog("DeviceID= $DeviceID");

my $NumTimesToTryAPSAlloc = 3;
printlog("Rack PDU not present, attempt APS allocation 3 times");

for (my $i = 1; $i <= $NumTimesToTryAPSAlloc; $i++) {
   PushErrorLevel($ERR_NONE);
   printlog("APS allocation attempt # $i");
   eval {GetResources(@ResourceList);};
   PopErrorLevel();
   if ($@) {
        if ($i < $NumTimesToTryAPSAlloc) {
            printlog("APS allocation failed but lpei required to try again");
            @ResourceList = ( "Phone",      $APS,     { Persistence => $PERSISTENT_NEW, COMPort => 'FINDSINGLE', UsbUploadMode => $USBUploadMode} );
            sleep(60);
        } else {
            printlog({msg => "APS allocation failed", subject => "Failed to allocate APS", exitCode => 20});
        }
   } else {
      printlog("APS allocation successful");
      last;
   }
}

my $ModemCOMPort = $Phone->GetComPortInfo();
if ($ModemCOMPort =~ /(COM\d+)/) {
   $ModemCOMPort = $1;
}
printlog("GetComPortInfo: $ModemCOMPort");

# if (CheckPhoneHealth({Phone => $Phone}) =~ /download/) {
    # $Phone->Reset(); 
    # printlog("Phone crashed!");
# }


check_crash_dir($APS_USB_Upload_Root_Directory);

ExitTestCase();



sub update_status {
    my ($project_name, $host_name, $ip_addr, $tc_name, $test_client, $build_version, $is_crash, $ta_name, $tc_result, $ta_result) = @_;
    my $URL = $Update_Test_Status_URL;

    my $lwp = LWP::UserAgent->new;
    $lwp->timeout(10);
    my $resp = $lwp->post( $URL, {
        project_name => $project_name,
        host_name => $host_name,
        ip_addr => $ip_addr,
        tc_name => $tc_name,
        test_client => $test_client,
        build_verion => $build_version,
        is_crash => $is_crash,
        ta_name => $ta_name,
        tc_result => $tc_result,
        ta_result => $ta_result,
    } );
    if ($resp->is_success) {
        printlog("Update test status ok!");
        return 1;
    } else {
        printlog("Update test status nok: " . $resp->message . "!");
        return 0;
    }
}

sub read_xml_conf {
    my $phonexmlfile = shift;
    printlog("Reading in phone XML file: $phonexmlfile");
    if (!-e $phonexmlfile) {
        printlog("XML file does not exist: $phonexmlfile");
        die "Couldn't open: $phonexmlfile";
    }
    my $phonexmlDetails_href = XMLin($phonexmlfile, ForceArray => ['testPhone'], KeyAttr => [], ContentKey => 'Value', KeepRoot => 1);
    if (!defined $phonexmlDetails_href) {
        printlog("Couldn't open: $phonexmlfile");
        die "Couldn't open: $phonexmlfile";
    }
    if (defined $phonexmlDetails_href->{testPhone}[0]->{ACS_MetaBuildPath}) {
        my $ACS_MetaBuildPath = $phonexmlDetails_href->{testPhone}[0]->{ACS_MetaBuildPath};
        if (open(ACS, $ACS_MetaBuildPath)) {
            my @line = <ACS>;
            close(ACS);
            my $line = join(" ", @line);
            my $t = ($line =~ /ACS_MetaBuild\s*=\s*((([\w_\.\-\\\#]+))|("[^"]+"))/);
            if ($t) {
                $ACS_MetaBuild = $1 ? $1 : $3;
                $ACS_MetaBuild =~ s/^ *//g;
                $ACS_MetaBuild =~ s/ *$//g;
                $ACS_MetaBuild =~ s/"//g;
            }
            printlog("Set ACS_MetaBuild=$ACS_MetaBuild!");
        } else {
            printlog("Could not open ACS_MetaBuild file: $ACS_MetaBuildPath");
            die "Could not open ACS_MetaBuild file: $ACS_MetaBuildPath";
        }
    } else {
        printlog("ACS_MetaBuildPath is not defined in $phonexmlfile!");
        die "ACS_MetaBuildPath is not defined in $phonexmlfile!";
    }
    if ($phonexmlDetails_href->{testPhone}[0]->{APS_USB_Upload_Root_Directory}) {
       $APS_USB_Upload_Root_Directory = $phonexmlDetails_href->{testPhone}[0]->{APS_USB_Upload_Root_Directory};
       printlog("Set APS_USB_Upload_Root_Directory=$APS_USB_Upload_Root_Directory!");
    }
    unless ($APS_USB_Upload_Root_Directory && $ACS_MetaBuild) {
        die "Not define ACS_MetaBuild or APS_USB_Upload_Root_Directory!";
    }
}

sub get_ip {
    my ($prefix) = shift;
    my $ip_output = `ipconfig`;
    my $local_ip;
    while ($ip_output =~ /IPv4\s+Address.*($prefix\S*)/gi) {
        if ($local_ip) {
            printlog("Find more than one IP address: $local_ip, $1, ignore the later one!");
        } else {
            $local_ip = $1;
        }
    }
    unless ($local_ip) {
        printlog("Failed to find any IP address with prefix '$prefix'!");
    }
    return $local_ip;
}

sub launch_QPST {
   my $configApp = "\\Program Files (x86)\\Qualcomm\\QPST\\bin\\QPSTConfig.exe";
   my @tasklist = `tasklist`;
   my @qpst = grep(/QPSTServer/i, @tasklist);
   if ($#qpst < 0) {
      printlog("QPST server not running, launching");
      system(1, $configApp);
      Sleep(5000);
      $QPSTLaunched = 1;
   } else {
      printlog("QPST server already running");
   }
}

sub check_crash_dir {
    my $dir = shift;
    my $crash_dump_dir = '';
    my $dump_exists = 0;
    my $files_num = 0;
    
    opendir( my $dh, $dir ) or return;
    my @files = readdir($dh);
    close $dh;
    foreach my $file (@files) {
        next if $file =~ /^\.+$/;
        my $dump_dir = File::Spec->catfile($dir, $file);
        if( $file =~ /$current_file/ && -d $dump_dir ) {
            $crash_dump_dir = $dump_dir;
            last;
        }
    }
    if ($crash_dump_dir) {
        printlog("Found dump dir $crash_dump_dir, check if it has dump files!");
        opendir( my $dump_dh, $crash_dump_dir ) or return;
        my @dump_files = readdir($dump_dh);
        close $dump_dh;
        foreach my $dump_file (@dump_files) {
            next if $dump_file =~ /^\.+$/;
            my $dump_dir = File::Spec->catfile($crash_dump_dir, $dump_file);
            if( $dump_file =~ /Dump_Files/i && -d $dump_dir ) {
                $dump_exists = 1;
                printlog("Found dump dir $dump_dir!");
            }
            $files_num++;
            printlog("Found dump file $dump_file, and dump files=$files_num!");
        }
    }
    if ($dump_exists || $files_num > 2) {
        printlog("Found dump dir or more than 2 files($files_num), not delete them!");
        printlog("Move all log files to $dir!");
        system("copy /y *.log $dir");
        system("del /s /q *.log");
        system("copy /y log\\*.log $dir");
        system("del /s /q log\\*.log");
        update_status('MDM.LE.1.0', $hostname, $local_ip, 'TC_iperf_traffic_en', 'tc_v0.0.1', 'build083', 1);
    } else {
        printlog("Not Found dump files and dump files=$files_num, so delete $dir!");
        rmtree($dir);
        update_status('MDM.LE.1.0', $hostname, $local_ip, 'TC_iperf_traffic_en', 'tc_v0.0.1', 'build083', 0);
    }
}

#####################################################################################
# CheckPhoneHealth - Check phone is up or download mode
#
# Input parameters: $Parameters_href - hash reference
#                        ->{Phone} - APS handle
# Returns: $PhoneState - "normal", "download" or "gone"
#####################################################################################
sub CheckPhoneHealth {
   my $p_href = shift;
   my $Phone = $p_href->{Phone};

   my $PhoneState;

   printlog("Check phone health");

   # Get phone state
   my $PhoneStatus = $Phone->IsPhoneDiagReady(10);
   if ($PhoneStatus->{Status} == 1) {
      $PhoneState = "normal";
   } else {  # Status is 0
      if ($PhoneStatus->{ModeDescription} =~ /Download/i) {
         $PhoneState = "download";
      } elsif ($PhoneStatus->{ModeDescription} =~ /sahara/i) {
         $PhoneState = "download";
      } elsif ($PhoneStatus->{ModeDescription} =~ /mode unknown/i) {
         $PhoneState = "download";
      } elsif ($PhoneStatus->{ModeDescription} =~ /SomeComError/i) {
         $PhoneState = "download";
      } else {
         $PhoneState = "gone";
      }
   }

   printlog("Found phone in state: $PhoneState ($PhoneStatus->{Status})", "$PhoneStatus->{StatusDescription}, $PhoneStatus->{ModeDescription}");
   printlog("Phone state: $PhoneState");

   return($PhoneState);
}

sub printlog {
    my @time = localtime(time);
    my $msg = "[" . ($time[4]+1) . "-$time[3] $time[2]:$time[1]:$time[0]]" . join("\n", @_, "");
    print $msg;
    if ($log_file) {
        open(my $fh, '>>', $log_file) or return;
        print $fh $msg;
    }
}
