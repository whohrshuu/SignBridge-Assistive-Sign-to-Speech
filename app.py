from flask import Flask, jsonify
import cv2
from cvzone.HandTrackingModule import HandDetector
import threading

app = Flask(__name__)

cap = cv2.VideoCapture(0)
detector = HandDetector(maxHands=1, detectionCon=0.8)

current_sign = "Waiting..."

def fingers_up(hand):
    lmList = hand["lmList"]
    handType = hand["type"]
    fingers = []

    if handType == "Right":
        fingers.append(1 if lmList[4][0] > lmList[3][0] else 0)
    else:
        fingers.append(1 if lmList[4][0] < lmList[3][0] else 0)

    for id in [8,12,16,20]:
        fingers.append(1 if lmList[id][1] < lmList[id-2][1] else 0)

    return fingers

def recognize_sign(fingers):

   
    if fingers == [1,1,1,1,1]: return "Hello"
    if fingers == [0,0,0,0,0]: return "Stop"
    if fingers == [0,1,0,0,0]: return "Help"
    if fingers == [0,1,1,0,0]: return "Water"
    if fingers == [0,1,1,1,0]: return "Food"
    if fingers == [0,1,1,1,1]: return "Thank You"
    if fingers == [1,0,0,0,0]: return "Yes"

    return "Unknown"

def run_detection():
    global current_sign

    while True:
        success, img = cap.read()
        if not success:
            break

        hands, img = detector.findHands(img)

        if hands:
            hand = hands[0]
            fingers = fingers_up(hand)
            sign = recognize_sign(fingers)
            current_sign = sign
        else:
            current_sign = "No Hand"

@app.route("/gesture")
def get_gesture():
    return jsonify({"gesture": current_sign})

if __name__ == "__main__":
    thread = threading.Thread(target=run_detection)
    thread.daemon = True
    thread.start()
    app.run(debug=True)