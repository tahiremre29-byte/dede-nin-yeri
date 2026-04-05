import urllib.request
import zipfile
import io
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

url = 'https://api.github.com/repos/tahiremre29-byte/dede-nin-yeri/actions/runs/23937950340/logs'
req = urllib.request.Request(url)
try:
    with urllib.request.urlopen(req, context=ctx) as response:
        z = zipfile.ZipFile(io.BytesIO(response.read()))
        # Find the log file for "1. Core Physics & Acoustic Tests" or similar
        for name in z.namelist():
            if "Core Physics" in name or "AI Network" in name or "build_and_test" in name:
                print(f"--- LOG FILE: {name} ---")
                log_data = z.read(name).decode(errors='replace')
                # Last 50 lines of log
                lines = log_data.split('\n')
                print('\n'.join(lines[-50:]))
                print("-" * 50)
except Exception as e:
    print(f"Hata log indirmesi: {e}")

