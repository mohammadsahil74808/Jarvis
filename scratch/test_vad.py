import webrtcvad
try:
    vad = webrtcvad.Vad(3)
    print("SUCCESS: webrtcvad is working!")
except Exception as e:
    print(f"FAILURE: {e}")
