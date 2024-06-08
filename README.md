# TransIP Dynamic DNS script
This script can be used to autmatically update the DNS entries of one or more domains when a dynamic IP address
is changed. This script should be run on the server that the DNS entries should point to. It should **not** be served
by a webserver! That is, **don't** put this in your `htdocs` or `www` folder or whatever.

When you use this script, it is advisable to set the Time To Live (TTL) of your DNS records to 1 hour to limit the
amount of downtime when the address changes.


## Setting up the script
1. Requirements: Python 3.x and the `cryptography` and `requests` packages (run: `pip install cryptography requests`).
2. Go to the TransIP Control Panel at https://www.transip.nl/cp/account/api/ (Account > API) and enable
   the API. Add a key pair to generate a private key, this must be generated without the "whitelisted" option!
   (After change to un unknown dynamic ip, this new ip is not in the whitelist!)
3. Copy-and-paste the generated private key into the definition of PRIVATE_KEY in the `dyndns.py` script.
4. Change the definitions of LOGIN and DOMAIN_MAIN_ENTRY to match your TransIP username and domain name(s).
   If you are going to have multiple servers logging into the same TransIP account, also make sure the value
   of LABEL is unique to avoid clashes.
5. **Change access to the script file**, so it can't be accessable from outside. **You don't want to leak your details!!!**
6. Call `dyndns.py` script on the command line whenever you want the DNS to be automatically updated. You can use
   `cron` to do this periodically for you.


## IPv6 support
To enable IPv6 support, you need to add one argument to the command line. This is the current IPv6 address:

     python dyndns.py 2001:db8::ff00:42:8329

Alternatively, you can set the argument to `online`. In that case, the script will query an online service for the IPv6
address.

     python dyndns.py online

Note that this method may result in a temporary IPv6 address (due to Privacy Extensions). It is therefore highly
recommended to supply a stable, SLAAC IPv6 address to this script directly. You can use the following command line to
use the current SLAAC IPv6 address from the `eth0` network interface:

     python dyndns.py "`ip addr show eth0 | grep -Poh '(?<=inet6\s)[0-9a-f:]+(?=/64)' | grep -vm 1 '^fe80'`"
