import sys
from time import time

HEADER_SIZE = 12


class RtpPacket:
    header = bytearray(HEADER_SIZE)

    def __init__(self):
        pass

    def encode(self, version, padding, extension, cc, seqnum, marker, pt, ssrc, payload):
        """Encode the RTP packet with header fields and payload."""
        timestamp = int(time())
        header = bytearray(HEADER_SIZE)

    # TODO: Fill the header bytearray with RTP header fields, DONE
        # version: 2 bits
        # padding: 1 bit
        # extension: 1 bit
        # csrc count (cc): 4 bits
        # marker (m): 1 bit
        # payload type (pt): 7 bits
        # sequence number: 16 bits
        # timestamp: 32 bits
        # ssrc: 32 bits

        header[0] = (version << 6) | (padding << 5) | (extension << 4) | cc     #    vvpecccc
        header[1] = (marker << 7) | pt                                          #    mppppppp
        header[2] = seqnum >> 8 & 255                         # remove 8 rightmost bits, ssssssss
                                                              # 255 to make sure bits > 8 are zeros
        header[3] = seqnum & 255                              # remove 8 leftmost bits, ssssssss

        header[4] = timestamp >> 24 & 255                     # remove 24 rightmost bits, tttttttt
        header[5] = timestamp >> 16 & 255                     # remove 16 rightmost bits, 8 leftmost bits, tttttttt
        header[6] = timestamp >> 8 & 255                      # remove 8 rightmost bits, 16 leftmost bits, tttttttt
        header[7] = timestamp & 255                           # remove 24 leftmost bits, tttttttt

        header[8] = ssrc >> 24 & 255                          # remove 24 rightmost bits, ssssssss
        header[9] = ssrc >> 16 & 255                          # remove 16 rightmost bits, 8 leftmost bits, ssssssss
        header[10] = ssrc >> 8 & 255                          # remove 8 rightmost bits, 16 leftmost bits, ssssssss
        header[11] = ssrc & 255                               # remove 24 leftmost bits, ssssssss

        self.header = header                                   # set header
        
        # Get the payload from the argument
        self.payload = payload                                 # set payload


    def decode(self, byteStream):
        """Decode the RTP packet."""
        self.header = bytearray(byteStream[:HEADER_SIZE])
        self.payload = byteStream[HEADER_SIZE:]

    def version(self):
        """Return RTP version."""
        return int(self.header[0] >> 6)

    def seqNum(self):
        """Return sequence (frame) number."""
        seqNum = self.header[2] << 8 | self.header[3]
        return int(seqNum)

    def timestamp(self):
        """Return timestamp."""
        timestamp = self.header[4] << 24 | self.header[5] << 16 | self.header[6] << 8 | self.header[7]
        return int(timestamp)

    def payloadType(self):
        """Return payload type."""
        pt = self.header[1] & 127
        return int(pt)

    def getPayload(self):
        """Return payload."""
        return self.payload

    def getPacket(self):
        """Return RTP packet."""
        return self.header + self.payload