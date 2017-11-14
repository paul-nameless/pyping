#!/usr/bin/env python3
import argparse
import os
import socket
import struct
import select
import time


ICMP_ECHO_REQUEST = 8


def checksum(source_string):
    """
    I'm not too confident that this is right but testing seems
    to suggest that it gives the same answers as in_cksum in ping.c
    """
    sum = 0
    countTo = (len(source_string) / 2) * 2
    count = 0
    while count < countTo:
        thisVal = source_string[count + 1] * \
            256 + source_string[count]
        sum = sum + thisVal
        sum = sum & 0xffffffff  # Necessary?
        count = count + 2

    if countTo < len(source_string):
        sum = sum + source_string[len(source_string) - 1]
        sum = sum & 0xffffffff  # Necessary?

    sum = (sum >> 16) + (sum & 0xffff)
    sum = sum + (sum >> 16)
    answer = ~sum
    answer = answer & 0xffff

    # Swap bytes. Bugger me if I know why.
    answer = answer >> 8 | (answer << 8 & 0xff00)

    return answer


def receive_one_ping(my_socket, ID, timeout):
    """
    receive the ping from the socket.
    """
    timeLeft = timeout
    while True:
        startedSelect = time.time()
        whatReady = select.select([my_socket], [], [], timeLeft)
        howLongInSelect = (time.time() - startedSelect)
        if whatReady[0] == []:  # Timeout
            return

        timeReceived = time.time()
        recPacket, addr = my_socket.recvfrom(1024)
        icmpHeader = recPacket[20:28]
        type, code, checksum, packetID, sequence = struct.unpack(
            "bbHHh", icmpHeader
        )
        # Filters out the echo request itself.
        # This can be tested by pinging 127.0.0.1
        # You'll see your own request
        if type != 8 and packetID == ID:
            bytesInDouble = struct.calcsize("d")
            timeSent = struct.unpack("d", recPacket[28:28 + bytesInDouble])[0]
            return timeReceived - timeSent

        timeLeft = timeLeft - howLongInSelect
        if timeLeft <= 0:
            return


def send_one_ping(my_socket, dest_addr, ID):
    """
    Send one ping to the given >dest_addr<.
    """
    dest_addr = socket.gethostbyname(dest_addr)

    # Header is type (8), code (8), checksum (16), id (16), sequence (16)
    my_checksum = 0

    # Make a dummy heder with a 0 checksum.
    header = struct.pack("bbHHh", ICMP_ECHO_REQUEST, 0, my_checksum, ID, 1)
    bytesInDouble = struct.calcsize("d")
    # data = (192 - bytesInDouble) * "Q"
    data = bytes((192 - bytesInDouble) * "Q", 'utf-8')
    data = struct.pack("d", time.time()) + data

    # Calculate the checksum on the data and the dummy header.
    my_checksum = checksum(header + data)

    # Now that we have the right checksum, we put that in. It's just easier
    # to make up a new header than to stuff it into the dummy.
    header = struct.pack(
        "bbHHh", ICMP_ECHO_REQUEST, 0, socket.htons(my_checksum), ID, 1
    )
    packet = header + data
    # 1 is and icmp protocol: socket.getprotobyname("icmp")
    my_socket.sendto(packet, (dest_addr, 1))


def ping(host, timeout):
    """
    Returns either the delay (in seconds) or none on timeout.
    """
    icmp = socket.getprotobyname("icmp")
    try:
        my_socket = socket.socket(socket.AF_INET, socket.SOCK_RAW, icmp)
    except socket.error as e:
        if e.errno == 1:
            # Operation not permitted
            msg = str(e) + (
                " - Note that ICMP messages can only be sent from processes"
                " running as root."
            )
            raise socket.error(msg)
        raise  # raise the original error

    my_ID = os.getpid() & 0xFFFF

    send_one_ping(my_socket, host, my_ID)
    delay = receive_one_ping(my_socket, my_ID, timeout)

    my_socket.close()
    return delay
    # return {
    #     'latency': 0,
    #     'host': host,
    #     'ip': ip,
    # }


def verbose_ping(host, timeout=1, count=4, interval=1):
    # ping ip (domain): 56 data bytes
    # 64 bytes from 192.168.1.1: icmp_seq=3 ttl=64 time=2.287 ms
    print("ping %s..." % host)
    for _ in range(count):
        try:
            delay = ping(host, timeout)
        except socket.gaierror as e:
            print("failed. (socket error: '%s')" % e)
            break

        if delay is None:
            print("failed. (timeout within %ssec.)" % timeout)
        else:
            delay = delay * 1000
            print("get ping in %0.4fms" % delay)
        if interval:
            time.sleep(interval)
    print()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'host',
        type=str,
        help='host to ping'
    )
    parser.add_argument(
        '-t',
        default=1,
        type=int,
        dest='timeout',
        help='timeout of each ping'
    )
    parser.add_argument(
        '-c',
        default=None,
        dest='count',
        type=int,
        help='number of pings'
    )
    parser.add_argument(
        '-i',
        default=1,
        type=int,
        dest='interval',
        help='interval between pings'
    )
    args = parser.parse_args()
    verbose_ping(args.host, args.timeout, args.count, args.interval)
    # verbose_ping("heise.de")
    # verbose_ping("google.com")
    # verbose_ping("a-test-url-taht-is-not-available.com")
    # verbose_ping("192.168.1.1")


if __name__ == '__main__':
    main()
