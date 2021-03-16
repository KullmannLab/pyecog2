
import logging
import time
import uuid

import Adafruit_BluefruitLE
import numpy as np

from gpiozero import LED
from time import sleep

led = LED(17)
led.on()

ble = Adafruit_BluefruitLE.get_provider()

VEND_UUID = uuid.UUID('0000f00d-1212-efde-1523-785fef13d123')
NTFY_CHAR_UUID      = uuid.UUID('0000beef-1212-efde-1523-785fef13d123')


# Main function implements the program logic so it can run in a background
# thread.  Most platforms require the main thread to handle GUI events and other
# asyncronous events like BLE actions.  All of the threading logic is taken care
# of automatically though and you just need to provide a main function that uses
# the BLE provider.
def main():
    # Clear any cached data because both bluez and CoreBluetooth have issues with
    # caching data and it going stale.
    print('Clearing cashed data...')
    ble.clear_cached_data()

    # Get the first available BLE network adapter and make sure it's powered on.
    print('Getting adapter...')
    adapter = ble.get_default_adapter()
    adapter.power_on()
    print('Using adapter: {0}'.format(adapter.name))

    # Disconnect any currently connected UART devices.  Good for cleaning up and
    # starting from a fresh state.
    print('Disconnecting any connected devices...')
    ble.disconnect_devices([])

    # Scan for UART devices.
    print('Searching for our device...')
    try:
        adapter.start_scan()
        # Search for the first UART device found (will time out after 60 seconds
        # but you can specify an optional timeout_sec parameter to change it).
        device = ble.find_device(service_uuids=[VEND_UUID])
        if device is None:
            raise RuntimeError('Failed to find device!')
    finally:
        # Make sure scanning is stopped before exiting.
        adapter.stop_scan()

    print('Connecting to device...')
    device.connect()  # Will time out after 60 seconds, specify timeout_sec parameter
                      # to change the timeout.

    # Once connected do everything else in a try/finally to make sure the device
    # is disconnected when done.
    led.blink()
    try:
        # Wait for service discovery to complete for at least the specified
        # service and characteristic UUID lists.  Will time out after 60 seconds
        # (specify timeout_sec parameter to override).
        
#         print('Discovering services...')
#         device.discover([VEND_UUID], [NTFY_CHAR_UUID])

        print('Discovering services ML...')
        char_list = device.discover_ML([VEND_UUID], [NTFY_CHAR_UUID])
        for char in char_list:
            if char.uuid == NTFY_CHAR_UUID:
                my_char = char
                print('found', my_char.uuid)
                
        # Find the UART service and its characteristics.
        
        serv = device.find_service(VEND_UUID)
        print('Discovering Characteristics...')
        rx = my_char
#         tx = uart.find_characteristic(TX_CHAR_UUID)

#         # Write a string to the TX characteristic.
#         print('Sending message to device...')
#         tx.write_value('Hello world!\r\n')

        # Function to receive RX characteristic changes.  Note that this will
        # be called on a different thread so be careful to make sure state that
        # the function changes is thread safe.  Use queue or other thread-safe
        # primitives to send data to other threads.

        with open('test_data.dat','w+b') as f:
        
            data_list = []
            
            def received(data):
            	# Transform 24 bit messages into 32 bit files
                f.write(bytes(sum(zip(data[0::3],data[1::3],data[2::3],np.zeros(len(data[0::3]),dtype='uint8')),())))
                np_data = np.array(data)
                data_list.append(np_data)
                print(np_data[3],np_data.shape)

            # Turn on notification of RX characteristics using the callback above.
            print('Subscribing to RX characteristic changes...')
            rx.start_notify(received)

            # Now just wait for 30 seconds to receive data.
            dtime = 60
            print('Waiting',dtime,'seconds to receive data from the device...')
            time.sleep(dtime)
            device.disconnect()
            data_list = np.array(data_list)
            print('final data size:',data_list.shape)
            print(np.diff(data_list[:,3])%256)

    except Exception:
        # Make sure device is disconnected on exit.
        device.disconnect()


# Initialize the BLE system.  MUST be called before other BLE calls!
print('Initializing ble...')
ble.initialize()

# Start the mainloop to process BLE events, and run the provided function in
# a background thread.  When the provided main function stops running, returns
# an integer status code, or throws an error the program will exit.
ble.run_mainloop_with(main)


