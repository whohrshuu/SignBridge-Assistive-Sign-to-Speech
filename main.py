import os
import cv2
import time
from cvzone.HandTrackingModule import HandDetector
import asl_logic

# ================== SETTINGS ==================
CAMERA_INDEX = 0   # iVCam confirmed working at index 0
# ==============================================

# Reduce MediaPipe logs
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

# Open camera (iVCam)
cap = cv2.VideoCapture(CAMERA_INDEX)

if not cap.isOpened():
    print("Camera not accessible. Start iVCam and try again.")
    exit()

detector = HandDetector(maxHands=1, detectionCon=0.8)
print("Webcam and Hand Detector initialized successfully.")

prev_lmList = None
sign_detected = "Waiting..."


# ================== MAIN LOOP ==================
while True:
    success, img = cap.read()
    if not success:
        print("Failed to read frame from webcam")
        break

    imgOutput = img.copy()
    hands, img = detector.findHands(img)

    sign_detected = "No Hand"

    if hands:
        hand = hands[0]
        lmList = hand["lmList"]

        handType = hand.get("type", "Right")

        static_sign = asl_logic.detect_static_asl_gesture(lmList, handType)
        sign_detected = asl_logic.detect_dynamic_sign(static_sign, prev_lmList, lmList, sign_detected)

        prev_lmList = lmList.copy()

        # Draw landmarks
        for lm in lmList:
            cv2.circle(imgOutput, (lm[0], lm[1]), 5, (0, 255, 0), cv2.FILLED)

    # Display result
    cv2.putText(
        imgOutput,
        f"ASL: {sign_detected}",
        (10, 60),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.2,
        (255, 0, 0),
        3
    )

    cv2.imshow("Hand Sign Recognition (iVCam)", imgOutput)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        print("Quitting.")
        break

cap.release()
cv2.destroyAllWindows()
