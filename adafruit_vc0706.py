# The MIT License (MIT)
#
# Copyright (c) 2017 Tony DiCola for Adafruit Industries
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
"""
`adafruit_vc0706`
====================================================

VC0706 serial TTL camera module.  Allows basic image capture and download of
image data from the camera over a serial connection.  See examples for demo
of saving image to a SD card (must be wired up separately).

* Author(s): Tony DiCola, Jason LeClare

Implementation Notes
--------------------

**Hardware:**

* Adafruit `TTL Serial JPEG Camera with NTSC Video
  <https://www.adafruit.com/product/397>`_ (Product ID: 397)

**Software and Dependencies:**

* Adafruit CircuitPython firmware for M0 and M4-based boards:
  https://github.com/adafruit/circuitpython/releases
"""
from os import listdir, chdir
from io import FileIO
from micropython import const

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_CircuitPython_VC0706.git"

_SERIAL = const(0x00)
_RESET = const(0x26)
_GEN_VERSION = const(0x11)
_SET_PORT = const(0x24)
_READ_FBUF = const(0x32)
_GET_FBUF_LEN = const(0x34)
_FBUF_CTRL = const(0x36)
_DOWNSIZE_CTRL = const(0x54)
_DOWNSIZE_STATUS = const(0x55)
_READ_DATA = const(0x30)
_WRITE_DATA = const(0x31)
_COMM_MOTION_CTRL = const(0x37)
_COMM_MOTION_STATUS = const(0x38)
_COMM_MOTION_DETECTED = const(0x39)
_MOTION_CTRL = const(0x42)
_MOTION_STATUS = const(0x43)
_TVOUT_CTRL = const(0x44)
_OSD_ADD_CHAR = const(0x45)

_STOPCURRENTFRAME = const(0x0)
_STOPNEXTFRAME = const(0x1)
_RESUMEFRAME = const(0x3)
_STEPFRAME = const(0x2)

# pylint doesn't like the lowercase x but it makes it more readable.
# pylint: disable=invalid-name
IMAGE_SIZE_640x480 = const(0x00)
IMAGE_SIZE_320x240 = const(0x11)
IMAGE_SIZE_160x120 = const(0x22)
# pylint: enable=invalid-name
_BAUDRATE_9600 = const(0xAEC8)
_BAUDRATE_19200 = const(0x56E4)
_BAUDRATE_38400 = const(0x2AF2)
_BAUDRATE_57600 = const(0x1C1C)
_BAUDRATE_115200 = const(0x0DA6)

_MOTIONCONTROL = const(0x0)
_UARTMOTION = const(0x01)
_ACTIVATEMOTION = const(0x01)

__SET_ZOOM = const(0x52)
__GET_ZOOM = const(0x53)

_CAMERA_DELAY = const(10)


class VC0706:
    """Driver for VC0706 serial TTL camera module.
    This version is for legacy code.
    :param ~busio.UART uart: uart serial or compatible interface
    :param int buffer_size: Receive buffer size
    """

    def __init__(self, uart, *, buffer_size=100):
        self._uart = uart
        self._buffer = bytearray(buffer_size)
        self._frame_ptr = 0
        self._command_header = bytearray(3)
        for _ in range(2):  # 2 retries to reset then check resetted baudrate
            for baud in (9600, 19200, 38400, 57600, 115200):
                self._uart.baudrate = baud
                if self._run_command(_RESET, b"\x00", 5):
                    break
            else:  # for:else rocks! http://book.pythontips.com/en/latest/for_-_else.html
                raise RuntimeError("Failed to get response from VC0706, check wiring!")

    @property
    def version(self):
        """Return camera version byte string."""
        # Clear buffer to ensure the end of a string can be found.
        self._send_command(_GEN_VERSION, b"\x01")
        readlen = self._read_response(self._buffer, len(self._buffer))
        return str(self._buffer[:readlen], "ascii")

    @property
    def baudrate(self):
        """Return the currently configured baud rate."""
        return self._uart.baudrate

    @baudrate.setter
    def baudrate(self, baud):
        """Set the baudrate to 9600, 19200, 38400, 57600, or 115200. """
        divider = None
        if baud == 9600:
            divider = _BAUDRATE_9600
        elif baud == 19200:
            divider = _BAUDRATE_19200
        elif baud == 38400:
            divider = _BAUDRATE_38400
        elif baud == 57600:
            divider = _BAUDRATE_57600
        elif baud == 115200:
            divider = _BAUDRATE_115200
        else:
            raise ValueError("Unsupported baud rate")
        args = [0x03, 0x01, (divider >> 8) & 0xFF, divider & 0xFF]
        self._run_command(_SET_PORT, bytes(args), 7)
        self._uart.baudrate = baud

    @property
    def image_size(self):
        """Get the current image size, will return a value of IMAGE_SIZE_640x480,
        IMAGE_SIZE_320x240, or IMAGE_SIZE_160x120.
        """
        if not self._run_command(_READ_DATA, b"\0x04\x04\x01\x00\x19", 6):
            raise RuntimeError("Failed to read image size!")
        return self._buffer[5]

    @image_size.setter
    def image_size(self, size):
        """Set the image size to a value of IMAGE_SIZE_640x480, IMAGE_SIZE_320x240, or
        IMAGE_SIZE_160x120.
        """
        if size not in (IMAGE_SIZE_640x480, IMAGE_SIZE_320x240, IMAGE_SIZE_160x120):
            raise ValueError(
                "Size must be one of IMAGE_SIZE_640x480, IMAGE_SIZE_320x240, or "
                "IMAGE_SIZE_160x120!"
            )
        return self._run_command(
            _WRITE_DATA, bytes([0x05, 0x04, 0x01, 0x00, 0x19, size & 0xFF]), 5
        )

    def set_img_size(self, size):
        """Literally the above, but for use internally."""
        if size not in (IMAGE_SIZE_640x480, IMAGE_SIZE_320x240, IMAGE_SIZE_160x120):
            raise ValueError(
                "Size must be one of IMAGE_SIZE_640x480, IMAGE_SIZE_320x240, or "
                "IMAGE_SIZE_160x120!"
            )
        return self._run_command(
            _WRITE_DATA, bytes([0x05, 0x04, 0x01, 0x00, 0x19, size & 0xFF]), 5
        )

    @property
    def frame_length(self):
        """Return the length in bytes of the currently capture frame/picture."""
        if not self._run_command(_GET_FBUF_LEN, b"\x01\x00", 9):
            return 0
        frame_length = self._buffer[5]
        frame_length <<= 8
        frame_length |= self._buffer[6]
        frame_length <<= 8
        frame_length |= self._buffer[7]
        frame_length <<= 8
        frame_length |= self._buffer[8]
        return frame_length

    def take_picture(self):
        """Tell the camera to store a picture. It still needs to be saved.
        Returns True if successful.
        """
        self._frame_ptr = 0
        return self._run_command(_FBUF_CTRL, bytes([0x1, _STOPCURRENTFRAME]), 5)

    def resume_video(self):
        """Tell the camera to resume being a camera after the video has stopped
        (Such as what happens when a picture is taken).
        """
        return self._run_command(_FBUF_CTRL, bytes([0x1, _RESUMEFRAME]), 5)

    def save_image(self, name="capture.jpg", overwrite=False):
        """Saves a picture that was stored. Optional arguments for overwriting
        the image.
        """
        # We don't want to overwrite unless we're told to.
        # This involves checking to see if a file exists.
        # Which requires checking if we were given a directory.
        if name[0] == "/":
            name = name[1:]  # Remove any leading slashes.
        name = name.split("/")  # Separate into directories.
        for directory in name[:-1]:  # Ignore the last one, it's the filename.
            chdir(directory)  # OS will fail if the directory doesn't exist.
        if name[-1] in listdir() and not overwrite:
            # File exists. We're told not to overwrite it.
            raise ValueError("File exists and overwrite is False!")
        # Size of picture.
        frame_length = self.frame_length
        # The file doesn't exist, or we're good to overwrite it.
        with open(name[-1], "wb") as outfile:
            while frame_length > 0:
                # Compute how much data is left to read as the lesser of remaining bytes
                # or the copy buffer size (32 bytes at a time).  Buffer size MUST be
                # a multiple of 4 and under 100.  Stick with 32!
                to_read = min(frame_length, 32)
                copy_buffer = bytearray(to_read)
                # Now read picture data into the copy buffer.
                if self.read_picture_into(copy_buffer) == 0:
                    raise RuntimeError("Failed to read picture frame data!")
                # Now write the data to the file, and decrement remaining bytes.
                outfile.write(copy_buffer)
                frame_length -= 32
        # Return to our original directory.
        for directory in name[:-1]:
            chdir("..")
        return True

    def read_picture_into(self, buf):
        """Read the next bytes of frame/picture data into the provided buffer.
        Returns the number of bytes written to the buffer (might be less than
        the size of the buffer).  Buffer MUST be a multiple of 4 and 100 or
        less.  Suggested buffer size is 32.
        """
        bufflen = len(buf)
        if bufflen > 256 or bufflen > (len(self._buffer) - 5):
            raise ValueError("Buffer is too large!")
        if bufflen % 4 != 0:
            raise ValueError("Buffer must be a multiple of 4! Try 32.")
        args = bytes(
            [
                0x0C,
                0x0,
                0x0A,
                0,
                0,
                (self._frame_ptr >> 8) & 0xFF,
                self._frame_ptr & 0xFF,
                0,
                0,
                0,
                bufflen & 0xFF,
                (_CAMERA_DELAY >> 8) & 0xFF,
                _CAMERA_DELAY & 0xFF,
            ]
        )
        if not self._run_command(_READ_FBUF, args, 5, flush=False):
            return 0
        if self._read_response(self._buffer, bufflen + 5) == 0:
            return 0
        self._frame_ptr += bufflen
        for i in range(bufflen):
            buf[i] = self._buffer[i]
        return bufflen

    def _run_command(self, cmd, args, resplen, flush=True):
        if flush:
            self._read_response(self._buffer, len(self._buffer))
        self._send_command(cmd, args)
        if self._read_response(self._buffer, resplen) != resplen:
            return False
        if not self._verify_response(cmd):
            return False
        return True

    def _read_response(self, result, numbytes):
        return self._uart.readinto(memoryview(result)[0:numbytes])

    def _verify_response(self, cmd):
        return (
            self._buffer[0] == 0x76
            and self._buffer[1] == _SERIAL
            and self._buffer[2] == cmd & 0xFF
            and self._buffer[3] == 0x00
        )

    def _send_command(self, cmd, args=None):
        self._command_header[0] = 0x56
        self._command_header[1] = _SERIAL
        self._command_header[2] = cmd & 0xFF
        self._uart.write(self._command_header)
        if args:
            self._uart.write(args)


class VC0706Camera:
    """Driver for VC0706 serial TTL camera module.
    This version re-does a few functions to make it work like the
    recently-implemented Camera module.
    :param ~busio.UART uart: uart serial or compatible interface
    :param int buffer_size: Receive buffer size
    """

    def __init__(self, uart, *, buffer_size=100):
        self._uart = uart
        self._buffer = bytearray(buffer_size)
        self._frame_ptr = 0
        self._command_header = bytearray(3)
        for _ in range(2):  # 2 retries to reset then check resetted baudrate
            for baud in (9600, 19200, 38400, 57600, 115200):
                self._uart.baudrate = baud
                if self._run_command(_RESET, b"\x00", 5):
                    break
            else:  # for:else rocks! http://book.pythontips.com/en/latest/for_-_else.html
                raise RuntimeError("Failed to get response from VC0706, check wiring!")

    @property
    def version(self):
        """Return camera version byte string."""
        # Clear buffer to ensure the end of a string can be found.
        self._send_command(_GEN_VERSION, b"\x01")
        readlen = self._read_response(self._buffer, len(self._buffer))
        return str(self._buffer[:readlen], "ascii")

    @property
    def baudrate(self):
        """Return the currently configured baud rate."""
        return self._uart.baudrate

    @baudrate.setter
    def baudrate(self, baud):
        """Set the baudrate to 9600, 19200, 38400, 57600, or 115200. """
        divider = None
        if baud == 9600:
            divider = _BAUDRATE_9600
        elif baud == 19200:
            divider = _BAUDRATE_19200
        elif baud == 38400:
            divider = _BAUDRATE_38400
        elif baud == 57600:
            divider = _BAUDRATE_57600
        elif baud == 115200:
            divider = _BAUDRATE_115200
        else:
            raise ValueError("Unsupported baud rate")
        args = [0x03, 0x01, (divider >> 8) & 0xFF, divider & 0xFF]
        self._run_command(_SET_PORT, bytes(args), 7)
        self._uart.baudrate = baud

    @property
    def image_size(self):
        """Get the current image size, will return a value of IMAGE_SIZE_640x480,
        IMAGE_SIZE_320x240, or IMAGE_SIZE_160x120.
        """
        if not self._run_command(_READ_DATA, b"\0x04\x04\x01\x00\x19", 6):
            raise RuntimeError("Failed to read image size!")
        return self._buffer[5]

    @image_size.setter
    def image_size(self, size):
        """Set the image size to a value of IMAGE_SIZE_640x480, IMAGE_SIZE_320x240, or
        IMAGE_SIZE_160x120.
        """
        if size not in (IMAGE_SIZE_640x480, IMAGE_SIZE_320x240, IMAGE_SIZE_160x120):
            raise ValueError(
                "Size must be one of IMAGE_SIZE_640x480, IMAGE_SIZE_320x240, or "
                "IMAGE_SIZE_160x120!"
            )
        return self._run_command(
            _WRITE_DATA, bytes([0x05, 0x04, 0x01, 0x00, 0x19, size & 0xFF]), 5
        )

    def set_img_size(self, size):
        """Literally the above, but for use internally."""
        if size not in (IMAGE_SIZE_640x480, IMAGE_SIZE_320x240, IMAGE_SIZE_160x120):
            raise ValueError(
                "Size must be one of IMAGE_SIZE_640x480, IMAGE_SIZE_320x240, or "
                "IMAGE_SIZE_160x120!"
            )
        return self._run_command(
            _WRITE_DATA, bytes([0x05, 0x04, 0x01, 0x00, 0x19, size & 0xFF]), 5
        )

    @property
    def frame_length(self):
        """Return the length in bytes of the currently capture frame/picture."""
        if not self._run_command(_GET_FBUF_LEN, b"\x01\x00", 9):
            return 0
        frame_length = self._buffer[5]
        frame_length <<= 8
        frame_length |= self._buffer[6]
        frame_length <<= 8
        frame_length |= self._buffer[7]
        frame_length <<= 8
        frame_length |= self._buffer[8]
        return frame_length

    def take_picture(self, buffer, width=640, height=480, fileformat=None):
        """Takes a picture and stores it into the given buffer.
        If the buffer is a file, it writes it. It'll happily pour it into
        a bytearray too, but other things will make the function sad.
        """
        # Check the buffer:
        if type(buffer) not in (FileIO, bytearray):
            raise ValueError("Buffer must be file or bytearray!")
        if isinstance(buffer, bytearray) == bytearray and len(buffer) > 0:
            raise ValueError("Buffer bytearray must be empty!")
        # Check and set image size.
        # Must be 640x480, 320x240, or 160x120
        if width == 640 and width / height == 4 / 3:
            self.set_img_size(IMAGE_SIZE_640x480)
        elif width == 320 and width / height == 4 / 3:
            self.set_img_size(IMAGE_SIZE_320x240)
        elif width == 160 and width / height == 4 / 3:
            self.set_img_size(IMAGE_SIZE_160x120)
        else:
            raise ValueError("Image size must be 640x480, 320x240, or 160x120!")
        # Check format
        # I need a better understanding of *what* to check for this.
        # if fileformat is not [INSERT CHECK HERE]:
        # raise ValueError("Image format must be JPG!")
        if fileformat is not None:
            raise ValueError("Please ignore fileFormat for now!")
        # OK, so now we have all of our checks out of the way. Time to set up the camera.
        # Now stop the camera.
        if not self.stop_video():
            self.resume_video()
            raise RuntimeError("Failed to take picture!")
        # Now we try to copy the image to the buffer.
        frame_length = self.frame_length
        while frame_length > 0:
            # Compute how much date is left to read.
            # Copy Buffer size MUST be a multiple of 4
            # and under 100. 32 works best.
            copy_buffer = bytearray(min(frame_length, 32))
            if self.read_picture_into(copy_buffer) == 0:
                raise RuntimeError("Failed to read picture frame data!")
            if isinstance(buffer, bytearray):
                # Add the buffer to the other buffer
                # This whole process really bytes
                buffer.extend(copy_buffer)
            elif isinstance(buffer, FileIO):
                # We have a file, so write bits.
                buffer.write(copy_buffer)
            frame_length -= 32
        # We've read the full buffer. We can be a video camera again.
        self.resume_video()
        return True

    def stop_video(self):
        """Tell the camera to stop its frame buffer and store the current image.
        Returns True if successful.
        """
        self._frame_ptr = 0
        return self._run_command(_FBUF_CTRL, bytes([0x1, _STOPCURRENTFRAME]), 5)

    def resume_video(self):
        """Tell the camera to resume being a camera after the video has stopped
        (Such as what happens when a picture is taken).
        """
        return self._run_command(_FBUF_CTRL, bytes([0x1, _RESUMEFRAME]), 5)

    def read_picture_into(self, buf):
        """Read the next bytes of frame/picture data into the provided buffer.
        Returns the number of bytes written to the buffer (might be less than
        the size of the buffer).  Buffer MUST be a multiple of 4 and 100 or
        less.  Suggested buffer size is 32.
        """
        bufflen = len(buf)
        if bufflen > 256 or bufflen > (len(self._buffer) - 5):
            raise ValueError("Buffer is too large!")
        if bufflen % 4 != 0:
            raise ValueError("Buffer must be a multiple of 4! Try 32.")
        args = bytes(
            [
                0x0C,
                0x0,
                0x0A,
                0,
                0,
                (self._frame_ptr >> 8) & 0xFF,
                self._frame_ptr & 0xFF,
                0,
                0,
                0,
                bufflen & 0xFF,
                (_CAMERA_DELAY >> 8) & 0xFF,
                _CAMERA_DELAY & 0xFF,
            ]
        )
        if not self._run_command(_READ_FBUF, args, 5, flush=False):
            return 0
        if self._read_response(self._buffer, bufflen + 5) == 0:
            return 0
        self._frame_ptr += bufflen
        for i in range(bufflen):
            buf[i] = self._buffer[i]
        return bufflen

    def _run_command(self, cmd, args, resplen, flush=True):
        if flush:
            self._read_response(self._buffer, len(self._buffer))
        self._send_command(cmd, args)
        if self._read_response(self._buffer, resplen) != resplen:
            return False
        if not self._verify_response(cmd):
            return False
        return True

    def _read_response(self, result, numbytes):
        return self._uart.readinto(memoryview(result)[0:numbytes])

    def _verify_response(self, cmd):
        return (
            self._buffer[0] == 0x76
            and self._buffer[1] == _SERIAL
            and self._buffer[2] == cmd & 0xFF
            and self._buffer[3] == 0x00
        )

    def _send_command(self, cmd, args=None):
        self._command_header[0] = 0x56
        self._command_header[1] = _SERIAL
        self._command_header[2] = cmd & 0xFF
        self._uart.write(self._command_header)
        if args:
            self._uart.write(args)
