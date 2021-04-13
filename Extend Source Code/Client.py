from tkinter import *
from tkinter.ttk import Progressbar
import tkinter.messagebox
import tkinter.font
from PIL import Image, ImageTk
import socket, threading, sys, traceback, os
import copy
import time

from RtpPacket import RtpPacket

CACHE_FILE_NAME = "cache-"
CACHE_FILE_EXT = ".jpg"

BUFFER_SIZE = 16384


class Client:
    INIT = 0
    READY = 1
    PLAYING = 2
    state = INIT

    SETUP = 0
    PLAY = 1
    PAUSE = 2
    TEARDOWN = 3
    PDESCRIBE = 4

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
        self.buffer = {}
        self.bufferedFrames = [-1]  # list of number of buffered frames. -1 is just a dummy
        self.playingFrameNbr = 1  # The first frame of the movie is 1, not 0
        self.totalFrames = 1
        self.rtpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.setupMovie()
        while(self.state != self.READY):
            time.sleep(0.05)
        self.describeMovie()

    def createWidgets(self):
        """Build GUI."""
        bottomframe = Frame(self.master)
        bottomframe.pack(side=BOTTOM)

        # Create header and subheader
        headerFont = tkinter.font.Font(family='Helvetica', size=30, weight='bold')
        self.header = Label(self.master, text="", font=headerFont)
        self.header.pack(padx=16, pady=16)

        subheaderFont = tkinter.font.Font(family='Helvetica', size=25)
        self.subheader = Label(self.master, text="", font=subheaderFont)
        self.subheader.pack(padx=16, pady=(0, 18))

        # Create control buttons
        buttonFont = tkinter.font.Font(family='Helvetica', size=20)
        playb = Button(bottomframe, text='Play', font=buttonFont, command=self.playMovie, padx=8)
        playb.pack(side=LEFT, pady=6, padx=(8, 4))
        reverseb = Button(bottomframe, text='Backward', font=buttonFont, command=self.reverseMovie, padx=8)
        reverseb.pack(side=LEFT, pady=6, padx=(4, 4))
        pauseb = Button(bottomframe, text='Pause', font=buttonFont, command=self.pauseMovie, padx=8)
        pauseb.pack(side=LEFT, pady=6, padx=(4, 4))
        tearb = Button(bottomframe, text='Teardown', font=buttonFont, command=self.exitClient, padx=8)
        tearb.pack(side=LEFT, pady=6, padx=(4, 8))
        switchb = Button(bottomframe, text='Switch', font=buttonFont, command=self.switchMovie, padx=8)
        switchb.pack(side=LEFT, pady=6, padx=(4, 8))
        describeb = Button(bottomframe, text='Describe', font=buttonFont, command=self.describeMovie, padx=8)
        describeb.pack(side=LEFT, pady=6, padx=(4, 8))

        videoframe = Frame(self.master, width=280, height=280, background="black")
        videoframe.pack(side=TOP)
        videoplayer = Label(videoframe)
        videoplayer.pack(side=TOP)

        self.playProgressLabel = Label(self.master, text="", font=subheaderFont)
        self.playProgressLabel.pack(side=BOTTOM, pady=(0, 0), padx=(8, 8))
        self.playProgress = Progressbar(self.master, orient=HORIZONTAL, length=500, mode='determinate')
        self.playProgress.pack(side=BOTTOM, pady=(0, 16), padx=(8, 8))

        self.label = videoplayer

    def refreshHeader(self):  # Refresh UI header to current status
        if self.state == self.READY and self.requestSent == self.SETUP:
            self.header.configure(text='Setup completed')
            self.subheader.configure(text='')
        if self.state == self.PLAYING:
            self.header.configure(text='Playing video')
            self.subheader.configure(
                text='\nClick \"Pause\" to pause playing video\nClick \"Teardown\" to stop playing video and close this window')
        if self.state == self.READY and self.requestSent == self.PAUSE:
            self.header.configure(text='Video paused')
            self.subheader.configure(text='\nClick \"Play\" to continue playing video')
        if self.requestSent == self.PDESCRIBE:
            self.header.configure(text='Welcome to RTP player')
            self.subheader.configure(text='\nClick \"Play\" to start playing video')

    def setupMovie(self):
        """Setup button handler."""
        if self.state == self.INIT:
            self.sendRtspRequest(self.SETUP)
            self.refreshHeader()

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
            self.refreshHeader()

    # TODO, DONE

    def playMovie(self):
        """Play button handler."""
        if self.state == self.READY:
            # Create a new thread to listen for RTP packets
            threading.Thread(target=self.listenRtp).start()
            self.playEvent = threading.Event()
            self.playEvent.clear()
            self.sendRtspRequest(self.PLAY)
            self.refreshHeader()

    # TODO, DONE

    def reverseMovie(self):
        """"Reverse button handler"""
        if self.playingFrameNbr > 30:
            self.playingFrameNbr -= 30
        else:
            self.playingFrameNbr = 1

    def describeMovie(self):
        """Describe button handler."""
        self.sendRtspRequest(self.PDESCRIBE)
        self.refreshHeader()

    # TODO, DONE

    def listenRtp(self):
        """Listen for RTP packets, manages cache and update movie view"""
        while True:
            # Controls movie update
            if self.playingFrameNbr <= max(
                    self.bufferedFrames):  # Only update to new frame when the buffered frame number is higher than playing frame
                while (
                        self.playingFrameNbr not in self.bufferedFrames):  # Skip every frame thhat is not buffered until find one that is buffered
                    print('Skipped playing frame: ', self.playingFrameNbr)
                    self.playingFrameNbr += 1

                self.updateMovie(self.playingFrameNbr)  # Play available frame and update frame number
                self.playingFrameNbr += 1
            # Listen for D=RTP packets
            if max(self.bufferedFrames) < self.totalFrames:
                try:
                    data = self.rtpSocket.recv(BUFFER_SIZE)
                    if data:  # processing received data
                        rtpPacket = RtpPacket()
                        rtpPacket.decode(data)  # decode data

                        receivedFrameNumber = rtpPacket.seqNum()  # frame number is the same as sequence number

                        if receivedFrameNumber < max(
                                self.bufferedFrames):  # Check if packet arrived later than current frame
                            print('Packet arrived late: ', receivedFrameNumber)

                        self.writeFrame(rtpPacket.getPayload(), receivedFrameNumber)
                except:
                    # Stop listening upon requesting PAUSE or TEARDOWN
                    if self.playEvent.isSet():
                        break

                    # Upon receiving ACK for TEARDOWN request, close the RTP socket
                    if self.teardownAcked == 1:
                        self.rtpSocket.shutdown(socket.SHUT_RDWR)
                        self.rtpSocket.close()
                        break

            else:
                # Stop listening upon requesting PAUSE or TEARDOWN
                if self.playEvent.isSet():
                    break

                # Upon receiving ACK for TEARDOWN request, close the RTP socket
                if self.teardownAcked == 1:
                    self.rtpSocket.shutdown(socket.SHUT_RDWR)
                    self.rtpSocket.close()
                    break

                time.sleep(0.05)  # sleep to slow down video

    # TODO, DONE

    def writeFrame(self, data, frameNumber):
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

        try:
            # Python's variables are referenced by default. Use deep copy to create a new buffered frame
            self.buffer[str(frameNumber)] = copy.deepcopy(Image.open(cachename))  # Add new video frame to buffer
            self.bufferedFrames.append(frameNumber)
        except:
            print("Cannot write to buffer")

    # TODO, DONE

    def updateMovie(self, frameNumber):
        """Update the image file as video frame in the GUI."""
        try:
            photo = ImageTk.PhotoImage(self.buffer[str(frameNumber)])
        except:
            print("Could not open image", frameNumber)

        self.label.configure(image=photo, height=640)
        self.label.image = photo
        self.playProgress['value'] = (self.playingFrameNbr / self.totalFrames) * 100  # Update video playing status
        self.playProgressLabel.configure(text='Frame ' + str(self.playingFrameNbr) + ' of ' + str(self.totalFrames))

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

        # Teardown request
        elif requestCode == self.PDESCRIBE and not self.state == self.INIT:

            # Update RTSP sequence number
            self.rtspSeq = self.rtspSeq + 1

            # Write the RTSP request to be sent.
            request = 'PDESCRIBE ' + str(self.fileName) + ' RTSP/1.0\nCSeq: ' + str(self.rtspSeq) + '\nSession: ' + str(
                self.sessionId)

            # Keep track of the sent request.
            self.requestSent = self.PDESCRIBE

        # Send request
        self.rtspSocket.send(request.encode())
        print('Sent request: ', request)

    def recvRtspReply(self):
        """Receive RTSP reply from the server."""
        while True:
            reply = self.rtspSocket.recv(BUFFER_SIZE)

            if reply:
                self.parseRtspReply(reply.decode("utf-8"))
                self.refreshHeader()

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
                    elif self.requestSent == self.PDESCRIBE:
                        videoInfo = ''
                        videoInfo += '\n- Encoding type: ' + lines[3].split(' ')[1]
                        videoInfo += '\n- Session ID: ' + str(self.sessionId)
                        videoInfo += '\n- Video name: ' + lines[4].split(' ')[1]
                        videoInfo += '\n- Video size: ' + lines[5].split(' ')[1] + ' bits'
                        videoInfo += '\n- Total frames: ' + lines[6].split(' ')[1] + ' frames'
                        self.totalFrames = int(lines[6].split(' ')[1])
                        tkinter.messagebox.showinfo('Video Info', 'Video Information:\n' + videoInfo)

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

    def switchMovie(self):
        self.pauseMovie()

        self.smallwin = Tk()
        self.enterframe = Frame(self.smallwin)
        l = Label(self.enterframe, text="Enter the new movie name:")
        l.pack(side=TOP)
        self.entry = Entry(self.enterframe)
        self.entry.pack(side=TOP)
        b = Button(self.enterframe, text='Enter', command=self.switchMovieClose)
        b.pack(side=TOP)

        self.enterframe.pack(side=TOP)

    def switchMovieClose(self):
        self.fileName = self.entry.get()
        self.smallwin.destroy()

        # Destroy the old session
        self.sendRtspRequest(self.TEARDOWN)
        self.master.destroy()  # Close the gui window
        try:
            os.remove(CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT)
        except:
            print("cache image didnt get removed")

        # start new session
        newroot = Tk()
        self = Client(newroot, self.serverAddr, self.serverPort, self.rtpPort + 1, self.fileName)
        self.master.title("RTPClient")
        newroot.mainloop()
# TODO, DONE