import sys
import subprocess

subprocess.run([
        'dbus-send', '--system',
        '--dest=org.freedesktop.NetworkManager',
        '--type=method_call',
        f'/org/freedesktop/NetworkManager/Devices/{sys.argv[1]}',
        'org.freedesktop.DBus.Properties.Set',
        'string:org.freedesktop.NetworkManager.Device',
        'string:Managed',
        'variant:boolean:false'
    ], check=True)  
