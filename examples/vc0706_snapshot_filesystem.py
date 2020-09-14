"""VC0706 image capture to local storage.
Has options for CP internal storage, USB, and Pi hardware.
Note that if you use the CP internal storage you need to set it up
properly with a boot.py file!
For PC, you must wire up the VC0706 to a USB or hardware serial port.
Primarily for use with Linux/Raspberry Pi but also can work with Mac/Windows"""

import time
import adafruit_vc0706

# Set the target, or what we're running this on.
TARGET = "MC"  # CircuitPython internal filesystem configuration.
# TARGET = "PC" #USB configuration.
# TARGET = "PI" #Pi hardwired configuration.

# Set if we want the image to be overwritten.
# If FALSE it will check to see if the image is there and fail if it is.
# If TRUE it doesn't check anything and happily overwrites.
OVERWRITE = True  # Will overwrite!

# Set this to the path to the file name to save the captured image.
# Also set up the serial connection to the camera at the same time.
IMAGE_FILE = None
UART = None
if TARGET == "MC":
    import board  # MC Hardware UART

    UART = board.UART()
    IMAGE_FILE = "/image.jpg"  # CircuitPython.
elif TARGET == "PC":
    # USB UART
    # Be sure to modify this to the correct device! (Windows COM, etc)
    import serial

    UART = serial.Serial("/dev/ttyUSB0", baudrate=115200, timeout=0.25)
    IMAGE_FILE = "image.jpg"  # USB storage.
elif TARGET == "PI":
    # Pi Hardware UART
    import serial

    UART = serial.Serial("/dev/ttyS0", baudrate=115200, timeout=0.25)
    IMAGE_FILE = "/home/pi/image.jpg"  # Pi storage

# Setup VC0706 camera
vc0706 = adafruit_vc0706.VC0706(UART)

# Print the version string from the camera.
print("VC0706 version:")
print(vc0706.version)

# Set the image size.
IMAGE_SIZE = adafruit_vc0706.IMAGE_SIZE_640x480
# Or set IMAGE_SIZE_320x240 or
# IMAGE_SIZE_160x120
# take_and_save defaults to whatever you set it as.
# Note you can also read the property and compare against those values to
# Just use vc0706.image_size and compare it.
if IMAGE_SIZE == adafruit_vc0706.IMAGE_SIZE_640x480:
    print("Using 640x480 size image.")
elif IMAGE_SIZE == adafruit_vc0706.IMAGE_SIZE_320x240:
    print("Using 320x240 size image.")
elif IMAGE_SIZE == adafruit_vc0706.IMAGE_SIZE_160x120:
    print("Using 160x120 size image.")

# Take a picture.
print("Taking a picture in 3 seconds...")
time.sleep(3)
print("SNAP!")
print("Saving image. This may take some time.")
stamp = time.monotonic()
vc0706.take_and_save(IMAGE_FILE, OVERWRITE, IMAGE_SIZE)
print("Finished in %0.1f seconds!" % (time.monotonic() - stamp))
