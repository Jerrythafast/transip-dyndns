#!/usr/bin/env python
PRIVATE_KEY = """
-----BEGIN PRIVATE KEY-----
copy-and-paste your private key here. don't forget to restrict access to this file!!!
-----END PRIVATE KEY-----"""
LOGIN = "username"
LABEL = "DynDNS30s"
TIMEOUT = 10.
DOMAIN_MAIN_ENTRY = {"mydomain.nl": "*", "myseconddomain.nl": "@"}


# pip install cryptography requests
import base64
import cryptography.hazmat.primitives.asymmetric.padding
import cryptography.hazmat.primitives.hashes
import cryptography.hazmat.primitives.serialization
import json
import re
import requests
import sys
import time


# This is used to check whether the specified IP address is valid.
# The IPv6 one comes from https://stackoverflow.com/a/17871737 (28 February 2016).
IPV4_REGEX = re.compile("^((25[0-5]|2[0-4][0-9]|[01]?[0-9]?[0-9])\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9]?[0-9])$")
IPV6_REGEX = re.compile("^(([0-9a-fA-F]{1,4}:){7,7}[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,7}:|([0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,5}(:[0-9a-fA-F]{1,4}){1,2}|([0-9a-fA-F]{1,4}:){1,4}(:[0-9a-fA-F]{1,4}){1,3}|([0-9a-fA-F]{1,4}:){1,3}(:[0-9a-fA-F]{1,4}){1,4}|([0-9a-fA-F]{1,4}:){1,2}(:[0-9a-fA-F]{1,4}){1,5}|[0-9a-fA-F]{1,4}:((:[0-9a-fA-F]{1,4}){1,6})|:((:[0-9a-fA-F]{1,4}){1,7}|:)|fe80:(:[0-9a-fA-F]{0,4}){0,4}%[0-9a-zA-Z]{1,}|::(ffff(:0{1,4}){0,1}:){0,1}((25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])|([0-9a-fA-F]{1,4}:){1,4}:((25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9]))$")


def format_exception(ex):
    return "%s: %s" % (type(ex).__name__, ex)

def print_message(message):
    """Write message to stderr, along with a timestamp."""
    sys.stderr.write("%s  %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), message))


try:
    import secrets
    def get_nonce():
        return secrets.token_hex(16)
except ImportError:
    import os
    def get_nonce():
        return os.urandom(16).hex()

def encode_json(data):
    return json.dumps(data).encode("ascii")

def sign_message(binary_message):
    return base64.b64encode(cryptography.hazmat.primitives.serialization.load_pem_private_key(
        PRIVATE_KEY.strip().encode("ascii"), password=None).sign(binary_message,
        padding=cryptography.hazmat.primitives.asymmetric.padding.PKCS1v15(),
        algorithm=cryptography.hazmat.primitives.hashes.SHA512()))

def request_token():
    request_body = encode_json({
        "login": LOGIN,
        "nonce": get_nonce(),
        "read_only": False,
        "expiration_time": "30 seconds",
        "label": LABEL,
        "global_key": True})
    resps = requests.post("https://api.transip.nl/v6/auth",
        data=request_body,
        headers={"Content-Type": "application/json", "Signature": sign_message(request_body)},
        timeout=TIMEOUT)
    resps.raise_for_status()
    return resps.json()["token"]

def request_get(endpoint, token):
    resps = requests.get("https://api.transip.nl/v6/" + endpoint,
        headers={"Authorization": "Bearer " + token},
        timeout=TIMEOUT)
    resps.raise_for_status()
    return resps.json()

def request_patch(endpoint, token, data):
    resps = requests.patch("https://api.transip.nl/v6/" + endpoint,
        data=encode_json(data),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + token},
        timeout=TIMEOUT)
    resps.raise_for_status()
    return resps.json()


if __name__ == "__main__":
    # Get IPv4 address.
    try:
        ipv4 = requests.get("https://v4.ipv6-test.com/api/myip.php", timeout=10.).text
    except:
        print_message("WARNING: Unable to determine current IPv4 address.")
        ipv4 = False
    else:
        if not IPV4_REGEX.match(ipv4):
            print_message("WARNING: Invalid IPv4 address obtained: '%s'" % ipv4)
            ipv4 = False

    # Get IPv6 address.
    ipv6 = False
    if len(sys.argv) > 1:
        if sys.argv[1] == "online":
            try:
                ipv6 = requests.get("https://v6.ipv6-test.com/api/myip.php", timeout=10.).text
            except:
                print_message("WARNING: Unable to determine current IPv6 address.")
        else:
            ipv6 = sys.argv[1]
        if ipv6 and not IPV6_REGEX.match(ipv6):
            print_message("WARNING: Invalid IPv6 address obtained: '%s'" % ipv6)
            ipv6 = False

    if not ipv4 and not ipv6:
        print_message("ERROR: Could not determine any current IP address.")
        sys.exit(1)

    # Log into API.
    try:
        token = request_token()
    except Exception as ex:
        print_message("ERROR: Could not get auth token. %s" % format_exception(ex))
        sys.exit(2)

    for domain, main_entry in DOMAIN_MAIN_ENTRY.items():
        # Get the current DNS entries from TransIP.
        try:
            dns = request_get("domains/%s/dns" % domain, token)["dnsEntries"]
        except Exception as ex:
            print_message("WARNING: Could not get current DNS config for %s. %s" % (domain, format_exception(ex)))
            continue

        # Find previously set IP addresses.
        oldIPv4 = False
        oldIPv6 = False
        for entry in dns:
            if entry["name"] == main_entry:
                if entry["type"] == "A":
                    oldIPv4 = entry["content"]
                elif entry["type"] == "AAAA":
                    oldIPv6 = entry["content"]
        if ipv4 and not oldIPv4:
            print_message("WARNING: Unable to determine previous IPv4 address for %s." % domain)
        if ipv6 and not oldIPv6:
            print_message("WARNING: Unable to determine previous IPv6 address for %s." % domain)

        # Determine what needs to be changed.
        updateIPv4 = oldIPv4 and ipv4 and oldIPv4 != ipv4
        updateIPv6 = oldIPv6 and ipv6 and oldIPv6 != ipv6
        if not updateIPv4 and not updateIPv6:
            print_message("No changes required for %s." % domain)
            continue
        if updateIPv4:
            print_message("Changing IPv4 address from %s to %s for %s." % (oldIPv4, ipv4, domain))
        if updateIPv6:
            print_message("Changing IPv4 address from %s to %s for %s." % (oldIPv6, ipv6, domain))

        # Update all DNS entries that have the found IP addresses.
        for entry in dns:
            update = False
            if updateIPv4 and entry["content"] == oldIPv4:
                entry["content"] = ipv4
                update = True
            elif updateIPv6 and entry["content"] == oldIPv6:
                entry["content"] = ipv6
                update = True
            if update:
                try:
                    request_patch("domains/%s/dns" % domain, token, entry)
                except Exception as ex:
                    print_message("WARNING: Could not update DNS config for %s with %r. %s" % (domain, entry, format_exception(ex)))
                    continue
