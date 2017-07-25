# TransIP Dynamic DNS script
This script can be used to autmatically update the DNS entries of one or more domains when a dynamic IP address
is changed. This script should be run on the server that the DNS entries should point to. It should *not* be served
by a webserver! That is, *don't* put this in your `htdocs` or `www` folder or whatever.

When you use this script, it is advisable to set the Time To Live (TTL) of your DNS records to 1 hour to limit the
amount of downtime when the address changes.


## Setting up the script
1. This script uses the TransIP API. Download it from https://www.transip.nl/transip/api/ and put it on your server.
   Change the definition of TRANSIP_API_DIR in the `dyndns.php` script to point to the directory where you stored the
   API on your server.
2. Go to the TransIP Control Panel, https://www.transip.nl/cp/mijn-account/#api, (My account > API settings) and enable
   the API. Add a key pair to generate a private key, this must be generated without the "whitelisted" option!
   (After change to un unknown dynamic ip, this new ip is not in the whitelist!)
3. Copy-and-paste the generated private key into the definition of PRIVATE_KEY in the `dyndns.php` script.
4. Change the definitions of DOMAINS and USERNAME to match your domain names and TransIP username.
5. *Change access to the script file*, so it can't be accessable from outside. *You don't want to leak your details!!!*
6. Call `dyndns.php` script on the command line whenever you want the DNS to be automatically updated. You can use
   `cron` to do this periodically for you.


## IPv6 support
To enable IPv6 support, you need to add one argument to the command line. This is the current IPv6 address:

     php dyndns.php 2001:db8::ff00:42:8329

Alternatively, you can set the argument to `online`. In that case, the script will query an online service for the IPv6
address.

     php dyndns.php online

Note that this method may result in a temporary IPv6 address (due to Privacy Extensions). It is therefore highly
recommended to supply a stable, SLAAC IPv6 address to this script directly. You can use the following command line to
use the current SLAAC IPv6 address from the `eth0` network interface:

     php dyndns.php "`ip addr show dev eth0 | grep -Poh '(?<=inet6\s)\S+ff:fe[0-9a-f]{2}:[0-9a-f]{0,4}(?=/64)' | grep -vm 1 '^fe80'`"


## Final remarks
This script was originally inspired by [this post](https://www.transip.nl/forum/post/prm/82/2#3198) on the TransIP
Forum.
