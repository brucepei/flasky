use strict;
use warnings;
use LWP::UserAgent;
use Data::Dumper;

update_status('MDM.LE.1.0', 'lpei1', '1.2.3.4', 'AP_AP_Traffic', 'tc_v0.11', 'build078', 0,  'enable_ap');

sub update_status {
    my ($project_name, $host_name, $ip_addr, $tc_name, $test_client, $build_version, $is_crash, $ta_name, $tc_result, $ta_result) = @_;
    my $URL = "http://127.0.0.1/mdm/td";

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
        print 1;
        return 1;
    } else {
        print $resp->message;
        print 0;
        return 0;
    }
}
