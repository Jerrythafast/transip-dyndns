<?php
/**
* How to use:
* 1. This script uses the TransIP API, which can be downloaded from https://www.transip.nl/transip/api/
*    Change the definition of TRANSIP_API_DIR below to point to the directory where you stored the API on your server.
* 2. Go to the TransIP CP, https://www.transip.nl/cp/mijn-account/#api, (My account > API settings) and enable the API.
*    Add a key pair to generate a private key, this must be generated without the "whitelisted" option!
*    (After change to un unknown dynamic ip, this new ip is not in the whitelist!)
* 3. Copy-and-paste the generated private key into the definition of PRIVATE_KEY in this script.
* 4. Change the definitions of DOMAINS and USERNAME to match your domain names and TransIP username.
* 5. Change access to this file, so it can't be accessable from outside. You don't want to leak your details!!!
* 6. Call this script from the PHP CLI. If you have one, supply the IPv6 address as an argument, e.g.,:
*
*      php dyndns.php 2001:db8::ff00:42:8329
*
*    If the IPv6 argument is 'online', this script will query an online service for the IPv6 address.
*
*      php dyndns.php online
*
*    Note that this may result in a temporary IPv6 address (due to Privacy Extensions). It is therefore recommended to
*    supply a SLAAC IPv6 address to this script directly. E.g., to use the current SLAAC address of the 'eth0' adapter:
*
*      php dyndns.php "`ip addr show dev eth0 | grep -Poh '(?<=inet6\s)\S+ff:fe[0-9a-f]{2}:[0-9a-f]{0,4}(?=/64)' | grep -vm 1 '^fe80'`"
*
* 7. You'll probably want to set up something that calls this script every once in a while. For example, set it up to
*    run at :30 every hour using cron. Run the command
*
*      crontab -e
*
*    And then add the following line at the bottom of the file (assuming you put this script in /opt):
*
*      30 * * * * /usr/bin/php /opt/dyndns.php "`/sbin/ip addr show dev wlan0 | /bin/grep -Poh '(?<=inet6\s)\S+ff:fe[0-9a-f]{2}:[0-9a-f]{0,4}(?=/64)' | /bin/grep -vm 1 '^fe80'`" >> /opt/log.txt 2>&1
*
* 8. It is advisable to set the Time To Live (TTL) of your DNS records to 1 hour to limit the amount of downtime
*    when the address changes.
*/

// SETTINGS
define('TRANSIP_API_DIR', 'Transip');  // Without trailing slash.
define('DOMAINS', ['mydomain.nl', 'myseconddomain.nl']);
define('USERNAME', 'username');
define('PRIVATE_KEY', '-----BEGIN PRIVATE KEY-----
copy-and-paste your private key here. don't forget to restrict access to this file!!!
-----END PRIVATE KEY-----
');
error_reporting(E_ERROR);


// This is used to check whether the specified IP address is valid.
// The IPv6 one comes from http://stackoverflow.com/a/17871737 (28 February 2016).
define('IPV4_REGEX', '/^((25[0-5]|2[0-4][0-9]|[01]?[0-9]?[0-9])\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9]?[0-9])$/');
define('IPV6_REGEX', '/^(([0-9a-fA-F]{1,4}:){7,7}[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,7}:|([0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,5}(:[0-9a-fA-F]{1,4}){1,2}|([0-9a-fA-F]{1,4}:){1,4}(:[0-9a-fA-F]{1,4}){1,3}|([0-9a-fA-F]{1,4}:){1,3}(:[0-9a-fA-F]{1,4}){1,4}|([0-9a-fA-F]{1,4}:){1,2}(:[0-9a-fA-F]{1,4}){1,5}|[0-9a-fA-F]{1,4}:((:[0-9a-fA-F]{1,4}){1,6})|:((:[0-9a-fA-F]{1,4}){1,7}|:)|fe80:(:[0-9a-fA-F]{0,4}){0,4}%[0-9a-zA-Z]{1,}|::(ffff(:0{1,4}){0,1}:){0,1}((25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])|([0-9a-fA-F]{1,4}:){1,4}:((25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9]))$/');


function print_message($message, $exit=false){
    echo date("Y-m-d H:i:s  ") . $message . PHP_EOL;
    if(!empty($exit))
        exit();
}

// Get IPv4 address.
$ipv4 = file_get_contents('http://v4.ipv6-test.com/api/myip.php');
if($ipv4 === false)
    print_message("WARNING: Unable to determine current IPv4 address.");
elseif(!preg_match(IPV4_REGEX, $ipv4)){
    print_message("WARNING: Invalid IPv4 address obtained: " . $ipv4 . ".");
    $ipv4 = false;
}

// Get IPv6 address.
$ipv6 = false;
if(!empty($argv) && isset($argv[1])){
    if($argv[1] == "online")
        $ipv6 = file_get_contents('http://v6.ipv6-test.com/api/myip.php');
    else
        $ipv6 = $argv[1];

    if($ipv6 === false)
        print_message("WARNING: Unable to determine current IPv6 address.");
    elseif(!preg_match(IPV6_REGEX, $ipv6)){
        print_message("WARNING: Invalid IPv6 address obtained: " . $ipv6 . ".");
        $ipv6 = false;
    }
}

if($ipv4 === false && $ipv6 === false)
    print_message("ERROR: Could not determine any current IP address.", true);


// Include the required files from the API and set login details.
require_once(TRANSIP_API_DIR . '/DomainService.php');
Transip_ApiSettings::$login = USERNAME;
Transip_ApiSettings::$privateKey = PRIVATE_KEY;

// Get the current DNS entries from TransIP.
try{
    $domainInfos = Transip_DomainService::batchGetInfo(DOMAINS);
}
catch(SoapFault $f){
    print_message("ERROR: Could not get current DNS config. " . $f->getMessage(), true);
}

foreach($domainInfos as $domainInfo){
    // Find previously set IP addresses.
    $oldIPv4 = false;
    $oldIPv6 = false;
    foreach($domainInfo->dnsEntries as $dnsEntry){
        if($dnsEntry->type == Transip_DnsEntry::TYPE_A && $dnsEntry->name == '@')
            $oldIPv4 = $dnsEntry->content;
        elseif($dnsEntry->type == Transip_DnsEntry::TYPE_AAAA && $dnsEntry->name == '@')
            $oldIPv6 = $dnsEntry->content;
    }
    if($ipv4 !== false && $oldIPv4 === false)
        print_message("WARNING: Unable to determine previous IPv4 address for " . $domainInfo->name . ".");
    if($ipv6 !== false && $oldIPv6 === false)
        print_message("WARNING: Unable to determine previous IPv6 address for " . $domainInfo->name . ".");

    // Determine what needs to be changed.
    $updateIPv4 = ($oldIPv4 !== false && $ipv4 !== false && $oldIPv4 != $ipv4);
    $updateIPv6 = ($oldIPv6 !== false && $ipv6 !== false && $oldIPv6 != $ipv6);
    if(!$updateIPv4 && !$updateIPv6){
        print_message("No changes required for " . $domainInfo->name . ".");
        continue;
    }
    if($updateIPv4)
        print_message("Changing IPv4 address from " . $oldIPv4 . " to " . $ipv4 . " for " . $domainInfo->name . ".");
    if($updateIPv6)
        print_message("Changing IPv6 address from " . $oldIPv6 . " to " . $ipv6 . " for " . $domainInfo->name . ".");

    // Update all DNS entries that have the found IP addresses.
    foreach($domainInfo->dnsEntries as $dnsEntry){
        if($updateIPv4 && $dnsEntry->content == $oldIPv4)
            $dnsEntry->content = $ipv4;
        elseif($updateIPv6 && $dnsEntry->content == $oldIPv6)
            $dnsEntry->content = $ipv6;
    }
    try{
        Transip_DomainService::setDnsEntries($domainInfo->name, $domainInfo->dnsEntries);
        print_message("DNS updated for " . $domainInfo->name . ".");
    }
    catch(SoapFault $f){
        print_message("ERROR: DNS not updated for " . $domainInfo->name . ". " . $f->getMessage());
    }
}

?>
