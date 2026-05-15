# SignBridge – Assistive Sign-to-Speech

An AI-powered assistive communication system that converts sign language gestures into speech in real time, helping bridge the communication gap between hearing/speaking individuals and the deaf or hard-of-hearing community.

---

## 🚀 Features

* Real-time sign language recognition
* Converts hand gestures into readable text
* Text-to-speech output for communication assistance
* User-friendly interface
* Fast and responsive detection system
* Assistive technology focused on accessibility and inclusion

---

## 🛠️ Tech Stack

### Frontend

* HTML
* CSS
* JavaScript

### Backend

* Python
* Flask

### AI / Machine Learning

* OpenCV
* MediaPipe
* TensorFlow / Keras

---

## 📂 Project Structure

```bash
SignBridge-Assistive-Sign-to-Speech/
│
├── static/
├── templates/
├── model/
├── app.py
├── requirements.txt
├── README.md
└── assets/
```

---

## ⚙️ Installation

### 1. Clone the repository

```bash
git clone https://github.com/whohrshuu/SignBridge-Assistive-Sign-to-Speech.git
```

### 2. Move into the project directory

```bash
cd SignBridge-Assistive-Sign-to-Speech
```

### 3. Create a virtual environment (optional but recommended)

```bash
python -m venv venv
```

### 4. Activate virtual environment

#### Windows

```bash
venv\Scripts\activate
```

#### Mac/Linux

```bash
source venv/bin/activate
```

### 5. Install dependencies

```bash
pip install -r requirements.txt
```

### 6. Run the project

```bash
python app.py
```

---

## 💡 How It Works

1. The webcam captures hand gestures in real time.
2. MediaPipe/OpenCV detects and tracks hand landmarks.
3. The trained ML model predicts the corresponding sign.
4. The predicted sign is converted into text.
5. Text-to-speech converts the output into audible speech.

---

## 📸 Screenshots



```bash
assets/homepage.png
<img width="1902" height="921" alt="homepage" src="https://github.com/user-attachments/assets/7679889d-6e43-43b4-b4b4-00d668d8f956" />
assets/detection.png
<img width="1893" height="917" alt="detection" src="https://github.com/user-attachments/assets/10073ed9-6dc8-46ef-b0fa-f6b359d266f7" />
```

---

## 🌍 Future Improvements

* Support for complete sentence formation
* Multi-language speech output
* Mobile application version
* More accurate gesture recognition
* Cloud deployment support

---

## 🤝 Contributing

Contributions are welcome.

1. Fork the repository
2. Create a new branch
3. Commit your changes
4. Push to your branch
5. Open a Pull Request

---

## 📜 License

This project is licensed under the MIT License.

---

## 👨‍💻 Author

**Harsh Bhagia**

* GitHub: [https://github.com/whohrshuu](https://github.com/whohrshuu)
* LinkedIn: [https://www.linkedin.com/in/harsh-bhagia-972365280/](https://www.linkedin.com/in/harsh-bhagia-972365280/)

---

## ⭐ Support

If you like this project, give it a star on GitHub ⭐
