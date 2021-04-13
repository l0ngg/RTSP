import copy

class VideoStream:
	def __init__(self, filename):
		self.filename = filename
		self.totalFramelength = 0
		self.buffer = []
		try:
			self.file = open(filename, 'rb')
			framelength = self.file.read(5)		# Get the framelength from the first 5 bytes
			while(framelength):
				data = self.file.read(int(framelength))
				self.buffer.append(copy.deepcopy(data))
				self.totalFramelength += int(framelength)
				framelength = self.file.read(5)
		except:
			raise IOError
		self.frameNum = 0
		
	def nextFrame(self):
		"""Get next frame."""
		frame = self.buffer[self.frameNum]
		self.frameNum += 1
		return frame
		
	def frameNbr(self):
		"""Get frame number."""
		return self.frameNum			# The first frame is 1

	def totalFrameNbr(self):
		return len(self.buffer)

	def videoSize(self):
		return self.totalFramelength
	
	def videoName(self):
		return self.filename