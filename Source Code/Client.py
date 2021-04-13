from tkinter import *
import tkinter.messagebox
from PIL import Image, ImageTk
import socket, threading, sys, traceback, os
import tkinter.font

import time
from RtpPacket import RtpPacket

CACHE_FILE_NAME = "cache-"
CACHE_FILE_EXT = ".jpg"


class Client:
    INIT = 0
    READY = 1
    PLAYING = 2
    state = INIT

    SETUP = 0
    PLAY = 1
    PAUSE = 2
    TEARDOWN = 3

    bitCount = 0

    # Initiation..
    def __init__(self, master, serveraddr, serverport, rtpport, filename):
        self.master = master
        self.master.protocol("WM_DELETE_WINDOW", self.handler)
        self.createWidgets()
        self.serverAddr = serveraddr
        self.serverPort = int(serverport)
        self.rtpPort = int(rtpport)
        self.fileName = filename
        self.rtspSeq = 0
        self.sessionId = 0
        self.requestSent = -1
        self.teardownAcked = 0
        self.connectToServer()
        self.frameNbr = 0
        self.rtpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def createWidgets(self):
        """Build GUI."""

        bottomframe = Frame(self.master)
        bottomframe.pack(side=BOTTOM)

        buttonFont = tkinter.font.Font(family='Helvetica', size=20)
        
        setupb = Button(bottomframe,text='Setup', font=buttonFont, command = self.setupMovie, padx=8)
        setupb.pack(side = LEFT, pady=6, padx=(8, 4))
        playb = Button(bottomframe, text='Play', font=buttonFont, command=self.playMovie, padx=8)
        playb.pack(side=LEFT, pady=6, padx=(8, 4))
        pauseb = Button(bottomframe, text='Pause', font=buttonFont, command=self.pauseMovie, padx=8)
        pauseb.pack(side=LEFT, pady=6, padx=(4, 4))
        tearb = Button(bottomframe, text='Teardown', font=buttonFont, command=self.exitClient, padx=8)
        tearb.pack(side=LEFT, pady=6, padx=(4, 8))

        videoframe = Frame(self.master)
        videoframe.pack(side=TOP)
        videoplayer = Label(videoframe)
        videoplayer.pack(side=BOTTOM)

        self.label = videoplayer

    def setupMovie(self):
        """Setup button handler."""
        if self.state == self.INIT:
            self.sendRtspRequest(self.SETUP)

    # TODO, DONE

    def exitClient(self):
        """Teardown button handler."""
        self.sendRtspRequest(self.TEARDOWN)
        self.master.destroy()  # Close the gui window
        os.remove(CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT)  # Delete the cache image from video

    # TODO, DONE

    def pauseMovie(self):
        """Pause button handler."""
        if self.state == self.PLAYING:
            self.sendRtspRequest(self.PAUSE)

    # TODO, DONE

    def playMovie(self):
        """Play button handler."""
        if self.state == self.READY:
            # Create a new thread to listen for RTP packets
            threading.Thread(target=self.listenRtp).start()
            self.playEvent = threading.Event()
            self.playEvent.clear()
            self.sendRtspRequest(self.PLAY)
    # TODO, DONE

    def listenRtp(self):
        """Listen for RTP packets."""
        while True:
            try:
                data = self.rtpSocket.recv(16384)
                if data:  # processing received data
                    rtpPacket = RtpPacket()
                    rtpPacket.decode(data)  # decode data

                    receivedFrameNumber = rtpPacket.seqNum()  # frame number is the same as sequence number

                    if receivedFrameNumber < self.frameNbr:  # Check if packet arrived later than current frame
                        print('Packet arrived late and discarded: ', receivedFrameNumber)  # discard packet
                    else:
                        self.frameNbr = receivedFrameNumber
                        self.updateMovie(self.writeFrame(rtpPacket.getPayload()))
            except:
                # Stop listening upon requesting PAUSE or TEARDOWN
                if self.playEvent.isSet():
                    break

                # Upon receiving ACK for TEARDOWN request, close the RTP socket
                if self.teardownAcked == 1:
                    self.rtpSocket.shutdown(socket.SHUT_RDWR)
                    self.rtpSocket.close()
                    break

    # TODO, DONE

    def writeFrame(self, data):
        """Write the received frame to a temp image file. Return the image file."""

        cachename = CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT

        try:
            cache = open(cachename, "wb")
        except:
            print("Cannot open cache")

        try:
            cache.write(data)
        except:
            print("Cannot write to cache")

        cache.close()

        return cachename

    # TODO, DONE

    def updateMovie(self, imageFile):
        """Update the image file as video frame in the GUI."""
        try:
            photo = ImageTk.PhotoImage(Image.open(imageFile))
        except:
            print("Could not open image", imageFile)

        # Time print per frame
        # print( time.perf_counter() )
        
        self.label.configure(image=photo, height=288)
        self.label.image = photo

    # TODO, DONE

    def connectToServer(self):
        """Connect to the Server. Start a new RTSP/TCP session."""
        self.rtspSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.rtspSocket.connect((self.serverAddr, self.serverPort))
        except:
            tkinter.messagebox.showwarning('Connection Failed', 'Connection to \'%s\' failed.' % self.serverAddr)

    # TODO, DONE

    def sendRtspRequest(self, requestCode):
        """Send RTSP request to the server."""

        # Prepare request
        request = ''
        if requestCode == self.SETUP and self.state == self.INIT:
            threading.Thread(target=self.recvRtspReply).start()

            # Update RTSP sequence number.
            self.rtspSeq = 1

            # Write the RTSP request to be sent.
            request = 'SETUP ' + str(self.fileName) + ' RTSP/1.0\nCSeq: ' + str(
                self.rtspSeq) + '\nTransport: RTP/UDP; client_port= ' + str(self.rtpPort)

            # Keep track of the sent request
            self.requestSent = self.SETUP

        # Play request
        elif requestCode == self.PLAY and self.state == self.READY:
            # Update RTSP sequence number.
            self.rtspSeq = self.rtspSeq + 1

            # Write the RTSP request to be sent.
            request = 'PLAY ' + str(self.fileName) + ' RTSP/1.0\nCSeq: ' + str(self.rtspSeq) + '\nSession: ' + str(
                self.sessionId)

            # Keep track of the sent request.
            self.requestSent = self.PLAY

        # Pause request
        elif requestCode == self.PAUSE and self.state == self.PLAYING:
            # Update RTSP sequence number
            self.rtspSeq += 1

            # Write the RTSP request to be sent
            request = 'PAUSE ' + str(self.fileName) + ' RTSP/1.0\nCSeq: ' + str(self.rtspSeq) + '\nSession: ' + str(
                self.sessionId)

            # Keep track of the sent request.
            self.requestSent = self.PAUSE

        # Teardown request
        elif requestCode == self.TEARDOWN and not self.state == self.INIT:

            # Update RTSP sequence number
            self.rtspSeq = self.rtspSeq + 1

            # Write the RTSP request to be sent.
            request = 'TEARDOWN ' + str(self.fileName) + ' RTSP/1.0\nCSeq: ' + str(self.rtspSeq) + '\nSession: ' + str(
                self.sessionId)

            # Keep track of the sent request.
            self.requestSent = self.TEARDOWN

        # Send request
        self.rtspSocket.send(request.encode())
        print('Sent request: ', request)

    def recvRtspReply(self):
        """Receive RTSP reply from the server."""
        while True:
            reply = self.rtspSocket.recv(4096)

            if reply:
                self.parseRtspReply(reply.decode("utf-8"))

            # Close the RTSP socket upon requesting Teardown
            if self.requestSent == self.TEARDOWN:
                self.rtspSocket.shutdown(socket.SHUT_RDWR)
                self.rtspSocket.close()
                break

    # TODO, DONE

    def parseRtspReply(self, data):
        """Parse the RTSP reply from the server."""
        lines = str(data).split('\n')
        seqNum = int(lines[1].split(' ')[1])

        # Process only if the server reply's sequence number is the same as the request's
        if seqNum == self.rtspSeq:
            session = int(lines[2].split(' ')[1])
            # New RTSP session ID
            if self.sessionId == 0:
                self.sessionId = session

            # Process only if the session ID is the same
            if self.sessionId == session:
                if int(lines[0].split(' ')[1]) == 200:
                    if self.requestSent == self.SETUP:
                        # Update RTSP state.
                        self.state = self.READY
                        # Open RTP port.
                        self.openRtpPort()
                    elif self.requestSent == self.PLAY:
                        self.state = self.PLAYING
                    elif self.requestSent == self.PAUSE:
                        self.state = self.READY
                        # The play thread exits. A new thread is created on resume.
                        self.playEvent.set()
                    elif self.requestSent == self.TEARDOWN:
                        self.state = self.INIT
                        # Flag the teardownAcked to close the socket.
                        self.teardownAcked = 1

    # TODO, DONE

    def openRtpPort(self):
        """Open RTP socket binded to a specified port."""
        # Create a new datagram socket to receive RTP packets from the server
        self.rtpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # Set the timeout value of the socket to 0.5sec
        self.rtpSocket.settimeout(0.5)

        try:
            # Bind the socket to the address using the RTP port given by the client user
            self.rtpSocket.bind(("", self.rtpPort))
        except:
            tkinter.messagebox.showwarning('Unable to Bind', 'Unable to bind PORT=%d' % self.rtpPort)

    def handler(self):
        """Handler on explicitly closing the GUI window."""
        self.pauseMovie()
        if tkinter.messagebox.askokcancel("Quit?", "Are you sure you want to quit?"):
            self.exitClient()
        else:  # When the user presses cancel, resume playing.
            self.playMovie()
# TODO, DONE