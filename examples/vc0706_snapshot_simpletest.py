"""VC0706 image capture to SD card demo.
You must wire up the VC0706 to the board's serial port, and a SD card holder
to the board's SPI bus.  Use the Feather M0 Adalogger as it includes a SD
card holder pre-wired to the board--this sketch is setup to use the Adalogger!
In addition you MUST also install the following dependent SD card library:
https://github.com/adafruit/Adafruit_CircuitPython_SD
See the guide here for more details on using SD cards with CircuitPython:
https://learn.adafruit.com/micropython-hardware-sd-cards"""

import time
import board
import digitalio
import storage

import adafruit_sdcard
import adafruit_vc0706


# Configuration:
SD_CS_PIN = board.D10  # CS for SD card (SD_CS is for Feather Adalogger)
IMAGE_FILE = "/sd/image.jpg"  # Full path to file name to save captured image.
OVERWRITE = (
    True  # Will overwrite! You can set it to False and have it yell at you instead.
)

# Setup SPI bus (hardware SPI).
spi = board.SPI()

# Setup SD card and mount it in the filesystem.
sd_cs = digitalio.DigitalInOut(SD_CS_PIN)
sdcard = adafruit_sdcard.SDCard(spi, sd_cs)
vfs = storage.VfsFat(sdcard)
storage.mount(vfs, "/sd")

# Create a serial connection for the VC0706 connection, speed is auto-detected.
uart = board.UART()
# Setup VC0706 camera
vc0706 = adafruit_vc0706.VC0706(uart)

# Print the version string from the camera.
print("VC0706 version:")
print(vc0706.version)

# Set the baud rate to 115200 for fastest transfer (its the max speed)
vc0706.baudrate = 115200

# Set the image size.
vc0706.image_size = adafruit_vc0706.IMAGE_SIZE_640x480
# Or set IMAGE_SIZE_320x240 or
# IMAGE_SIZE_160x120
# Note you can also read the property and compare against those values to
# see the current size:
size = vc0706.image_size
if size == adafruit_vc0706.IMAGE_SIZE_640x480:
    print("Using 640x480 size image.")
elif size == adafruit_vc0706.IMAGE_SIZE_320x240:
    print("Using 320x240 size image.")
elif size == adafruit_vc0706.IMAGE_SIZE_160x120:
    print("Using 160x120 size image.")

# Take a picture.
print("Taking a picture in 3 seconds...")
time.sleep(3)
print("SNAP!")
print("Saving image. This may take some time.")
stamp = time.monotonic()
vc0706.take_and_save(IMAGE_FILE, OVERWRITE)
print("Finished in %0.1f seconds!" % (time.monotonic() - stamp))
