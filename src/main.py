# Copyright (c) farm-ng, inc. Amiga Development Kit License, Version 0.1
import argparse
import asyncio
import os
#Time module for waiting for images
import time
import datetime
import cv2
from typing import List

import grpc
# import internal libs
    #Defines message formats for communicating over the canbus network
from farm_ng.canbus import canbus_pb2
    #Client for communication over canbus
from farm_ng.canbus.canbus_client import CanbusClient
    #
from farm_ng.canbus.packet import AmigaControlState
    #Information about the amiga's current position and speed 
from farm_ng.canbus.packet import AmigaTpdo1
    #Send speed information 
from farm_ng.canbus.packet import make_amiga_rpdo1_proto
    #Recieve speed information
from farm_ng.canbus.packet import parse_amiga_tpdo1_proto
    #Defines formats for canbus messages of camera
from farm_ng.oak import oak_pb2
    #Cleint for communication with camera 
from farm_ng.oak.camera_client import OakCameraClient
    #Message formats and client for communication between farmng services
from farm_ng.service import service_pb2
from farm_ng.service.service_client import ClientConfig

from turbojpeg import TurboJPEG

    #Function that provides the tic changes on the default app
    
from ImageScanner import ops
# Must come before kivy imports
os.environ["KIVY_NO_ARGS"] = "1"

# gui configs must go before any other kivy import
from kivy.config import Config  # noreorder # noqa: E402

Config.set("graphics", "resizable", False)
Config.set("graphics", "width", "1280")
Config.set("graphics", "height", "800")
Config.set("graphics", "fullscreen", "false")
Config.set("input", "mouse", "mouse,disable_on_activity")
Config.set("kivy", "keyboard_mode", "systemanddock")

# kivy imports
from kivy.app import App  # noqa: E402
from kivy.graphics.texture import Texture  # noqa: E402
from kivy.lang.builder import Builder  # noqa: E402
from kivy.properties import StringProperty  # noqa: E402


class ImageScannerApp(App):
    """Base class for the main Kivy app."""
    def __init__(
        self, address: str, port1: int,
        # port2 : int, 
        #TESTING 2 CAMS
        # port3 : int,
        stream_every_n: int
        ) -> None:
        super().__init__()
        self.address = address
        #DEBUG
        print("app initialized")
        #Camera ports
        self.port1 = port1
        # self.port2 = port2
        #TESTING 2 CAMS
        # self.port3 = port3
        self.stream_every_n = stream_every_n
        self.image_decoder = TurboJPEG()
        
        
        self.take_pictures = False
        self.last_capture_time = 0
        self.counter: int = 0
        
        #Set up where the images will be saved. 
        self.data_dir = os.path.join(os.path.expanduser("~"), "my_data")
        os.makedirs(self.data_dir, exist_ok=True)

        self.tasks: List[asyncio.Task] = []

    def build(self):
        return Builder.load_file("res/main.kv")

    def on_exit_btn(self) -> None:
        """Kills the running kivy application."""
        App.get_running_app().stop()

    def update_speed(self):
        """This function updates the self.userSpeed based on the slider input"""
        if self.root is not None:
            self.userSpeed = self.root.ids.speed_slider.value
            self.root.ids.speed_label.text = f"{self.userSpeed}"
 
    def update_delay(self):
        """This function updates the self.pDelay (picture delay) based off the slider input"""
        if self.root is not None:
            self.pDelay = self.root.ids.delay_slider.value
            self.root.ids.delay_label.text = f"{self.pDelay}"
    def toggle_capture(self):
        """Will flip the boolean value of self.take_pictures"""
        if self.root is not None:
            if(self.root.ids.toggle_picture_button.state == 'down'):
                self.take_pictures = True
            else:
                self.take_pictures = False

        
    async def app_func(self):
        async def run_wrapper() -> None:
            # we don't actually need to set asyncio as the lib because it is
            # the default, but it doesn't hurt to be explicit
            await self.async_run(async_lib="asyncio")
            for task in self.tasks:
                task.cancel()
                
        #DEBUG
        print("got past wrapper")
            #Configuring the camera client for the first camera 
        config1 = ClientConfig(address = self.address, port = self.port1)
        client1 = OakCameraClient(config1)
        #DEBUG
        print("got past config of camera 1")
            #Configuring the camera client for cam 2
        # config2 = ClientConfig(address = self.address, port = self.port2)
        # client2 = OakCameraClient(config2)
        #DEBUG
        print("got past config of camera 2")
            #Configuring the camera client for cam 3
        #TESTING 2 CAMS
        # config3 = ClientConfig(address = self.address, port = self.port3)
        # client3 = OakCameraClient(config3)

            #stream the cameras' frames
        self.tasks.append(asyncio.ensure_future(self.stream_all(client1
                                                                # , client2
                                                                #TESTING 2 CAMS
                                                                # ,client3
                                                                )))



        return await asyncio.gather(run_wrapper(), *self.tasks)
    async def stream_all(self, client1: OakCameraClient
                        #  , client2: OakCameraClient
                        #  , client3: OakCameraClient
                        ):
        #DEBUG
        print("Got into stream all function")
        self.tasks = [
        asyncio.ensure_future(self.stream_camera(client1, 'camera_1'))
        # ,asyncio.ensure_future(self.stream_camera(client2, 'camera_2'))
        #TESTING 2 CAMS
        # ,asyncio.ensure_future(self.stream_camera(client3, 'camera_3'))
        ]
        await asyncio.gather(*self.tasks)

    async def stream_camera(self, client: OakCameraClient, view_name: str):
        """This task listens to one camera stream and puts just the rgb stream into the proper spot for the kv file"""
        while self.root is None:
            await asyncio.sleep(0.01)
        response_stream = None
        
        while True:
            #IMPORTANT: move this after finishing function 
            # if(self.take_pictures):
                # self.tasks.append(asyncio.ensure_future(self.picture_loop(client)))
            state = await client.get_state()
            if state.value not in [
                service_pb2.ServiceState.IDLE,
                service_pb2.ServiceState.RUNNING,
            ]:
                #Cancel the stream if it exists
                if response_stream is not None:
                    response_stream.cancel()
                    response_stream = None 
    # Remember to uncomment this
                print(f"{view_name} is not streaming or ready to stream")
                await asyncio.sleep(0.1)
                continue
            
            if response_stream == None:
                response_stream = client.stream_frames(every_n= self.stream_every_n)
            try:
                #Will not run until there is a value in response_stream
                response: oak_pb2.StreamFramesReply = await response_stream.read()
                #Checks that response is not false or None, and that the stream hasnt ended
                assert response and response != grpc.aio.EOF, "End of Stream" 
                
            except Exception as e:
                print("the error: ", e)
                response_stream.cancel()
                response_stream = None
                #loop starts over 
                continue
            
            #Get the sync frame (frame that the rest of the stream is based off)
            #Colon just means what data it is expecting to recieve
            frame: oak_pb2.OakSyncFrame = response.frame
            
            #Get image and show
            try: 
                #decode image
                try:
                    img = self.image_decoder.decode(
                    getattr(frame,'rgb').image_data
                    )
                except Exception as e:
                    print("Error on gettimg image frame, ", e)

                try:
                    texture = Texture.create(
                    #Creates the texture the height and width of img
                    size = (img.shape[1], img.shape[2]), icolorfmt = 'bgr'
                    )
                except Exception as e:
                    print("Error on texture creation", e)
                try: 
                    texture.flip_verticle()
                except Exception as e:
                    print("Flip failed", e)
                #Puts the image onto the texture variable, stored in blue green red format. 
                
                try:
                    texture.blit_buffer(
                    img.tobytes(),
                    colorfmt = 'bgr', 
                    bufferfmt = 'ubyte',
                    mipmap_generation = False,
                    )
                except Exception as e:
                    print("Billet buffer failed", e)
                
                #Puts the texture in the proper tab for the GUI (camera_1, camera_2, etc)
                try:
                    self.root.ids[view_name].texture = texture
                except Exception as e:
                    print("Failed on the texture application", e)
                
            except Exception as e:
                print("Error on texture generation", e)
            
            # #If the button is pressed down, take pictures.
            if(self.take_pictures):
                self.tasks.append(asyncio.ensure_future(self.picture_loop(client, img)))
            await asyncio.sleep(1.0)

            # increment the counter using internal libs and update the gui
            self.counter = ops.add(self.counter, 1)
            self.root.ids.counter_label.text = (
                f"{'Tic' if self.counter % 2 == 0 else 'Tac'}: {self.counter}"
            )
    
    async def picture_loop(self, client : OakCameraClient, img):
        """This function will be taking a picture if the current time is longer than the delay"""
        print("would be taking pictures right now")
        # get the current time using time.monotonic()
        self.current_time = time.monotonic()

        # check if enough time has passed since the last capture
        if self.take_pictures and self.current_time - self.last_capture_time >= self.pDelay:
            # convert image from bgr to rgb
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

            # save image to disk
            data_dir = os.path.join(os.path.expanduser("~"), "my_data")
            os.makedirs(data_dir, exist_ok=True)
            
            # get the current date and time
            current_file_time = datetime.datetime.now()
            # format the date and time as a string
            time_str = current_file_time.strftime("%Y-%m-%d_%H-%M-%S")
            # create the filename using the formatted date and time
            filename = f"{time_str}.jpg"
            # create the full path to the file
            filepath = os.path.join(self.data_dir, filename)
            # save the image to disk
            cv2.imwrite(filepath, img)

            # update the last capture time
            self.last_capture_time = self.current_time

        pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="Image-Scanner")

    # Add additional command line arguments here
    parser.add_argument('--port', type= int, required= True, help = 'The Camera Port')
        # Add additional command line arguments here
    # parser.add_argument('--port2', type= int, required= True, help = 'The Camera Port 2')
    #TESTING 2 CAMS
    # parser.add_argument('--port3', type= int, required= True, help = 'The Camera Port 3')
    parser.add_argument('--address', type= str, default = 'localhost', help = "The camera address")
    parser.add_argument('--stream-every-n', type=int, default = 2, help= 'Cam stream frequency')
    
    
    args = parser.parse_args()

    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(
            ImageScannerApp(args.address, args.port, 
                            # args.port2,
                            #TESTING 2 CAMS
                            # args.port3,
                            args.stream_every_n).app_func()
            )
    except asyncio.Cancelled:
        pass
    loop.close()
