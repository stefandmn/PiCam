#!/usr/bin/env python

import cv
import sys
import time
import datetime



class Motion:

	def __init__(self):
		self.capture = cv.CaptureFromCAM(0)
		self.measureDisplay = True
		self.saveSamples = True
		self.NoOfFrames = 3

	def setResolution(self, width=640, height=480):
		cv.SetCaptureProperty(self.capture, cv.CV_CAP_PROP_FRAME_WIDTH, width)
		cv.SetCaptureProperty(self.capture, cv.CV_CAP_PROP_FRAME_HEIGHT, height)

	def log(self, text=None, frame=None):
		if self.measureDisplay:
			if text is None or text == "reset" or text == "init":
				if frame is not None and self.saveSamples:
					file = "/tmp/photo" + "-" + datetime.datetime.now().strftime("%Y%m%d%H%M%S%f") + "-" + "init" + ".png"
					cv.SaveImage(file, frame)
				self.measure_init = datetime.datetime.now()
				self.measure_next = self.measure_init
				print "\nStart getting Samples.."
			else:
				if text != "end":
					measure_now = datetime.datetime.now()
					diff = measure_now - self.measure_next
					print "\tSample: %s - %s micros" %(text, str(diff.microseconds))				
					if frame is not None and self.saveSamples:
						file = "/tmp/photo" + "-" + datetime.datetime.now().strftime("%Y%m%d%H%M%S%f") + "-" + text + ".png"
						cv.SaveImage(file, frame)
					self.measure_next = datetime.datetime.now()
				else:
					measure_now = datetime.datetime.now()
					diff = measure_now - self.measure_init
					print "Last Sample: %s micros" %(str(diff.microseconds))
					if frame is not None and self.saveSamples:
						cv.PutText(frame, "Sample: " + time.strftime("%d-%m-%Y %H:%M:%S", time.localtime()) + "-end",(10, cv.GetSize(frame)[1] - 10), cv.InitFont(cv.CV_FONT_HERSHEY_COMPLEX, .3, .3, 0.0, 1, cv.CV_AA ), (255, 255, 255))
						cv.SaveImage(file, frame)

	def run(self):
		try:
			counter = 0
			first = True

			while (self.NoOfFrames > 0 and counter < self.NoOfFrames) or self.NoOfFrames < 0:
				self.log()

				color_image = cv.QueryFrame(self.capture)
				self.log("QueryFrame", color_image)

				# Smooth to get rid of false positives
				cv.Smooth(color_image, color_image, cv.CV_GAUSSIAN, 3, 0)
				self.log("Smooth", color_image)

				if first:
					difference = cv.CloneImage(color_image)
					self.log("CloneImage 1=difference", difference)
					
					temp = cv.CloneImage(color_image)
					self.log("CloneImage 2=temp", temp)
					
					grey_image = cv.CreateImage(cv.GetSize(color_image), cv.IPL_DEPTH_8U, 1)
					self.log("CreateImage=grey_image", grey_image)
					
					moving_average = cv.CreateImage(cv.GetSize(color_image), cv.IPL_DEPTH_32F, 3)
					self.log("CreateImage=moving_average", moving_average)
					
					cv.ConvertScale(color_image, moving_average, 1.0, 0.0)
					self.log("ConvertScale=moving_average", moving_average)
					first = False
				else:
					cv.RunningAvg(color_image, moving_average, 0.020, None)
					self.log("RunningAvg=moving_average", moving_average)

				# Convert the scale of the moving average.
				cv.ConvertScale(moving_average, temp, 1.0, 0.0)
				self.log("ConvertScale=temp", temp)

				# Minus the current frame from the moving average.
				cv.AbsDiff(color_image, temp, difference)
				self.log("AbsDiff=difference", difference)

				# Convert the image to grayscale.
				cv.CvtColor(difference, grey_image, cv.CV_RGB2GRAY)
				self.log("CvtColor=grey_image", grey_image)

				# Convert the image to black and white.
				cv.Threshold(grey_image, grey_image, 70, 255, cv.CV_THRESH_BINARY)
				self.log("Threshold=grey_image", grey_image)

				# Dilate and erode to get people blobs
				cv.Dilate(grey_image, grey_image, None, 18)
				self.log("Dilate=grey_image", grey_image)
				cv.Erode(grey_image, grey_image, None, 10)
				self.log("Erode=grey_image", grey_image)

				storage = cv.CreateMemStorage(0)
				self.log("CreateMemStorage")
				contour = cv.FindContours(grey_image, storage, cv.CV_RETR_CCOMP, cv.CV_CHAIN_APPROX_SIMPLE)
				self.log("FindContours: " + str(len(list(contour))))

				points = []
				movementArea = 0
				
				while contour:
					bound_rect = cv.BoundingRect(list(contour))
					contour = contour.h_next()
					
					# Compute the bounding points to the boxes that will be drawn on the screen
					pt1 = (bound_rect[0], bound_rect[1])
					pt2 = (bound_rect[0] + bound_rect[2], bound_rect[1] + bound_rect[3])
					
					# Add this latest bounding box to the overall area that is being detected as movement
					movementArea += ( ( pt2[0] - pt1[0] ) * ( pt2[1] - pt1[1] ) )
					points.append(pt1)
					points.append(pt2)
					cv.Rectangle(color_image, pt1, pt2, cv.CV_RGB(255,0,0), 1)
					self.log("Draw contour")
				
				if movementArea > 0:
					print 'MA: ' + repr(movementArea)
					fname = "/tmp/" + "photo" + "-" + datetime.datetime.now().strftime("%Y%m%d%H%M%S%f") + ".png"
					cv.SaveImage(fname, color_image)
					self.log("SaveImage")

				self.log("end")
				counter += 1
				time.sleep(0.1)
		except KeyboardInterrupt:
			print '^C received, Shutting down server'
			sys.exit(0)
		

if __name__=="__main__":
	motion = Motion()
	motion.measureDisplay = True
	motion.saveSamples = True
	motion.NoOfFrames = 3
	motion.run()
