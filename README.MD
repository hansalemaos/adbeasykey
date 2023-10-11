# handles spaces, accents and other sneaky characters in ADB commands 

## Tested against Windows / Python 3.11 / Anaconda

## pip install adbeasykey

```python

from adbeasykey import AdbEasyKey
adbpath = r"C:\Android\android-sdk\platform-tools\adb.exe"
serial_number = "127.0.0.1:5555"
adb = AdbEasyKey(adbpath, serial_number, use_busybox=False) # if use_busybox is True, busybox will be used to decode the base64-encoded command
adb.connect_to_device_ps()
adb.connect_to_device_subprocess()
text = f'"it\'s me", he said then he went away "Montréal, über, 12.89, Mère, Françoise, noël, 889 groß"""'
adb.install_adb_keyboard()
adb.input_text_adb_keyboard_ps(
    text, change_back=True, sleeptime=(0, 0), add_exit=True
)  # preserves accents - suffix _ps is for use Windows Powershell
adb.input_text_adb_keyboard_subprocess(
    text, change_back=True, sleeptime=(0.1, 0.2), add_exit=True
)  # preserves accents
adb.keyevents.KEYCODE_A.press_ps()
adb.keyevents.KEYCODE_A.press_subproc()
adb.keyevents.KEYCODE_A.longpress_subproc()
adb.keyevents.KEYCODE_A.longpress_ps()
adb.input_text_ps(text)  # doesn't preserve accents
adb.input_text_ps(text, remove_accents=True)  # ç -> c
adb.input_text_ps(text, sleeptime=(0.1, 0.2), remove_accents=True) # one by one

adb.input_text_subprocess(text)  # doesn't preserve accents
adb.input_text_subprocess(text, remove_accents=True)  # ç -> c
adb.input_text_subprocess(text, sleeptime=(0.1, 0.2), remove_accents=True)
stdout, stderr = adb.adb_shell_ps("ls / -1 -R -i -H -las")
stdout, stderr = adb.adb_shell_ps("ls /data")  # no permission
stdout, stderr = adb.adb_shell_ps("ls /data", su=True)  # permission
stdout, stderr = adb.adb_shell_ps('mkdir "/sdcard/bub ö äß"')
stdout, stderr = adb.adb_shell_ps("ls /sdcard/")
stdout, stderr = adb.adb_shell_subprocess("ls / -1 -R -i -H -las")
stdout, stderr = adb.adb_shell_subprocess("ls /data")  # no permission
stdout, stderr = adb.adb_shell_subprocess("ls /data", su=True)  # permission
stdout, stderr = adb.adb_shell_subprocess('mkdir "/sdcard/#gx bub ö äß"')
stdout, stderr = adb.adb_shell_subprocess("ls /sdcard/")
stdout, stderr = adb.adb_ps(
    cmd=r"push C:\Users\hansc\Downloads\Roger LeRoy Miller, Daniel K. Benjamin, Douglass C. North - The Economics of Public Issues-Pearson College Div (2017).pdf /sdcard/Download/testbba.pdf"
)
stdout, stderr = adb.adb_subprocess(
    cmd=r"push C:\Users\hansc\Downloads\Roger LeRoy Miller, Daniel K. Benjamin, Douglass C. North - The Economics of Public Issues-Pearson College Div (2017).pdf /sdcard/Download/testbba.pdf"
)

stdout, stderr = adb.adb_shell_ps(
    "input swipe 600 600 0 0 1000\ninput swipe 0 0 600 600 1000",
)
adb.is_keyboard_shown()
adb.get_active_keyboard()
adb.change_to_adb_keyboard()
adb.change_keyboard(
    keyboard="com.android.inputmethod.latin/.LatinIME",
)

```