#!/usr/bin/env python3

import argparse
import base64
import ipaddress
import json
import logging
import secrets
import sys
from ipaddress import IPv4Address, IPv6Address
from typing import Optional, TypeVar, TextIO

import requests
from cryptography.hazmat.primitives.asymmetric.padding import PKCS1v15
from cryptography.hazmat.primitives.hashes import SHA512
from cryptography.hazmat.primitives.serialization import load_pem_private_key


LOG_FORMAT = "%(levelname)s %(message)s"
LOG_LEVEL = logging.INFO
IPV4_UNSPECIFIED = IPv4Address("0.0.0.0")
IPV6_UNSPECIFIED = IPv6Address("::")
IPV4_IDENT_URLS = (
    "https://v4.ident.me",
    "https://api4.ipify.org",
)
IPV6_IDENT_URLS = (
    "https://v6.ident.me",
    "https://api6.ipify.org",
)
TRANSIP_API_URL = "https://api.transip.nl/v6"
REQUEST_TIMEOUT = 10.0

AddressT = TypeVar("AddressT", IPv4Address, IPv6Address)

logger = logging.getLogger("transip-dyndns")


def get_nonce() -> str:
    return secrets.token_hex(16)


def encode_json(data: dict) -> bytes:
    return json.dumps(data).encode("ascii")


def sign_message(binary_message: bytes, private_key: TextIO) -> bytes:
    return load_pem_private_key(
        private_key.read().strip().encode("ascii"),
        password=None,
    ).sign(binary_message, padding=PKCS1v15(), algorithm=SHA512())


def get_access_token(label: str, username: str, private_key: TextIO) -> str:
    request_body: bytes = encode_json(
        {
            "login": username,
            "nonce": get_nonce(),
            "read_only": False,
            "expiration_time": "30 seconds",
            "label": label,
            "global_key": True,
        }
    )
    response = requests.post(
        f"{TRANSIP_API_URL}/auth",
        data=request_body,
        headers={
            "Content-Type": "application/json",
            "Signature": base64.b64encode(sign_message(request_body, private_key)),
        },
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()["token"]


def transip_request_get(endpoint: str, token: str) -> dict:
    response = requests.get(
        f"{TRANSIP_API_URL}/{endpoint}",
        headers={
            "Authorization": f"Bearer {token}",
        },
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def transip_request_patch(endpoint: str, token: str, data: dict) -> None:
    response = requests.patch(
        f"{TRANSIP_API_URL}/{endpoint}",
        data=encode_json(data),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()


def determine_ip_address(address_type: type[AddressT]) -> Optional[AddressT]:
    if address_type == IPv4Address:
        identify_urls = IPV4_IDENT_URLS
        version = 4
    else:
        identify_urls = IPV6_IDENT_URLS
        version = 6

    last_exc: Exception | None = None

    for url in identify_urls:
        try:
            response = requests.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            value = response.text.strip()
            return address_type(value)
        except requests.RequestException as exc:
            last_exc = exc
            logger.info(
                f"Failed to determine IPv{version} address using {url}, skipping"
            )
        except ipaddress.AddressValueError as exc:
            last_exc = exc
            logger.info(f"Got invalid response from {url}, skipping")

    if last_exc is not None:
        logger.exception(
            f"Failed to determine current IPv{version} address",
            exc_info=last_exc,
        )

    return None


def process_domain(
    domain: str,
    main_entry: str,
    ipv4: Optional[IPv4Address],
    ipv6: Optional[IPv6Address],
    token: str,
) -> None:
    try:
        dns_entries: list[dict] = transip_request_get(f"domains/{domain}/dns", token)[
            "dnsEntries"
        ]
    except requests.RequestException:
        logger.exception(f"Could not get current DNS config for {domain}")
        return

    # Find previously set IP addresses.
    old_ipv4: Optional[IPv4Address] = None
    old_ipv6: Optional[IPv6Address] = None

    for entry in dns_entries:
        if entry["name"] == main_entry:
            if entry["type"] == "A":
                old_ipv4 = IPv4Address(entry["content"])
            elif entry["type"] == "AAAA":
                old_ipv6 = IPv6Address(entry["content"])

    if ipv4 and not old_ipv4:
        logger.warning(f"Unable to determine previous IPv4 address for {domain}")

    if ipv6 and not old_ipv6:
        logger.warning(f"Unable to determine previous IPv6 address for {domain}")

    # Determine what needs to be changed.
    update_ipv4 = bool(old_ipv4 and ipv4 and old_ipv4 != ipv4)
    update_ipv6 = bool(old_ipv6 and ipv6 and old_ipv6 != ipv6)

    if not update_ipv4 and not update_ipv6:
        logger.info(f"No changes required for {domain}")
        return

    if update_ipv4:
        logger.info(f"Changing IPv4 address from {old_ipv4} to {ipv4} for {domain}")

    if update_ipv6:
        logger.info(f"Changing IPv6 address from {old_ipv6} to {ipv6} for {domain}")

    # Update all DNS entries that have the found IP addresses.
    for entry in dns_entries:
        update = False
        current_value: str = entry["content"]

        if update_ipv4 and current_value == str(old_ipv4):
            entry["content"] = str(ipv4)
            update = True
        elif update_ipv6 and current_value == str(old_ipv6):
            entry["content"] = str(ipv6)
            update = True

        if update:
            try:
                transip_request_patch(
                    f"domains/{domain}/dns", token, {"dnsEntry": entry}
                )
            except requests.RequestException:
                logger.exception(
                    f"Could not update DNS config for {domain} with {entry}"
                )
                continue


def domain_name(value: str) -> tuple[str, str]:
    items: list[str] = value.split(":")
    if not len(items) == 2:
        raise ValueError("Invalid domain name format.")
    domain, name = items
    return domain, name


def get_domain_queue(domains: list[tuple[str, str]]) -> dict[str, str]:
    queue: dict[str, str] = {}
    for domain, main_entry in domains:
        if domain in queue:
            raise ValueError(
                f"Duplicate domain {domain} specified. "
                "Please specify only one main DNS entry name per domain."
            )
        queue[domain] = main_entry
    return queue


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="transip-dyndns",
        description="TransIP Dynamic DNS script.",
    )
    parser.add_argument(
        "-l",
        "--label",
        metavar="LABEL",
        default="transip-dyndns",
        help=(
            "Custom name for your access tokens. If you are going to have "
            "multiple servers logging into the same TransIP account, also "
            "make sure the value of LABEL is unique to avoid clashes."
        ),
    )
    parser.add_argument(
        "-u",
        "--username",
        metavar="USERNAME",
        required=True,
        help="Your TransIP login username.",
    )
    parser.add_argument(
        "-k",
        "--private-key",
        type=argparse.FileType("r"),
        metavar="PATH",
        required=True,
        help=(
            "Path to a text file containing the private key. "
            "To get a private key, you should first generate "
            "a key pair using the TransIP control panel "
            "(https://www.transip.nl/cp/account/api)."
        ),
    )
    parser.add_argument(
        "-4",
        "--ipv4",
        type=IPv4Address,
        metavar="ADDRESS",
        nargs="?",
        const=IPV4_UNSPECIFIED,
        default=None,
        help=(
            "Update the IPv4 address. If no address is specified, "
            "it will be determined via an online service."
        ),
    )
    parser.add_argument(
        "-6",
        "--ipv6",
        type=IPv6Address,
        metavar="ADDRESS",
        nargs="?",
        const=IPV6_UNSPECIFIED,
        default=None,
        help=(
            "Update the IPv6 address. If no address is specified, "
            "it will be determined via an online service."
        ),
    )
    parser.add_argument(
        "-d",
        "--domain",
        type=domain_name,
        action="append",
        metavar="DOMAIN:NAME",
        required=True,
        help=(
            "Specify a domain for which to update the DNS records. "
            "The domain must be followed by the main DNS entry name, "
            "e.g. 'example.com:@' or 'example.com:www'. "
            "This option can be repeated for different domains."
        ),
    )

    args = parser.parse_args()

    if not args.ipv4 and not args.ipv6:
        parser.error("Please specify one of --ipv4 or --ipv6.")

    try:
        domain_queue = get_domain_queue(args.domain)
    except ValueError as exc:
        parser.error(str(exc))

    if args.ipv4 == IPV4_UNSPECIFIED:
        logger.info("Determining IPv4 address...")
        args.ipv4 = determine_ip_address(IPv4Address)

    if args.ipv4:
        logger.info(f"Your IPv4 address: {args.ipv4}")

    if args.ipv6 == IPV6_UNSPECIFIED:
        logger.info("Determining IPv6 address...")
        args.ipv6 = determine_ip_address(IPv6Address)

    if args.ipv6:
        logger.info(f"Your IPv6 address: {args.ipv6}")

    if not args.ipv4 and not args.ipv6:
        logger.error("Failed to determine any current IP address")
        sys.exit(1)

    assert args.ipv4 != IPV4_UNSPECIFIED
    assert args.ipv6 != IPV6_UNSPECIFIED

    try:
        token = get_access_token(args.label, args.username, args.private_key)
    except requests.RequestException:
        logger.error("Failed to get access token. Try again later.")
        sys.exit(2)

    for domain, main_entry in domain_queue.items():
        process_domain(domain, main_entry, args.ipv4, args.ipv6, token)


if __name__ == "__main__":
    logging.basicConfig(format=LOG_FORMAT, level=LOG_LEVEL)
    main()
