# Realtime Sign Language Translation

A real-time application for detecting and recognizing sign language gestures using a webcam feed.

## Table of Contents

- [Aim](#aim)
- [Project Overview](#project-overview)
- [Demo](#demo)
- [Features](#features)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
- [Usage](#usage)

## Aim

This project aims to create a sign language translator using machine learning techniques and Python programming. The application utilizes various modules, primarily Mediapipe, Landmark, and Random Forest algorithms to interpret and translate sign language gestures into text or spoken language.

## Project Overview

Sign language is a crucial form of communication for individuals with hearing impairments. This project focuses on bridging the communication gap by creating a tool that can interpret sign language gestures in real-time and convert them into understandable text or speech.

This project leverages Flask for the web interface and TensorFlow/Keras for the machine learning model to recognize sign language gestures in real-time from a webcam feed.

<img src="../docs/hand-signs-of-the-ASL-Language.png"  width="60%"/>

> American Sign Language Convention for Alphabets.

<img src="../docs/sign%20language%202.jpg"  width="60%"/>

> Custom Sign Language for Words / Sentences.

## Demo

Showcasing a demonstration of the Realtime Sign Language Detection 



https://github.com/user-attachments/assets/36d57256-4a54-4977-b54c-4cf615ab5204



## Features
* **Real-time sign language recognition**: Captures hand gestures using the Mediapipe library to track landmarks and movements.
* **Landmark analysis**: Utilizes Landmark module to extract key points and gestures from hand movements.
* **Machine learning translation**: Employs Random Forest algorithm to classify and interpret gestures into corresponding text.
* **Text-to-speech**: For better communication the text can be converted to spoken language using the speech synthesis.

## Getting Started
To get started with the Sign Language Translator, follow these steps:

### Prerequisites

1. **Python**: Provides a vast array of libraries and frameworks for machine learning, computer vision, and data processing.
2. **TensorFlow**: For building and training machine learning models.
3. **Scikit-learn**: For implementing the Random Forest algorithm for sign language recognition.
4. **Numpy**: For numerical computations and data manipulation.
5. **Mediapipe**: For real-time hand tracking and landmark detection.
6. **OpenCV**: For video processing and computer vision tasks.
7. **Flask**: Web framework to develop the application.
8. **Flask-SocketIO**: Adds low-latency bi-directional communication between clients and the server to Flask applications.

### Installation

1. Clone the repository:

```shell
git clone https://github.com/uzibytes/sign2text.git
```
```shell
cd sign2text
```

2. Create and activate a virtual environment:

  ```shell
  python -m venv venv
  ```
  ```shell
  source venv/bin/activate  # On Windows use `venv\Scripts\activate`
  ```

3. Install required libraries:

  ```shell
  pip install -r requirements.txt
  ```

4. Ensure a webcam is connected to your system.

## Usage

1. Start the Flask application:
    ```bash
    python app.py
    ```

2. Open your web browser and navigate to :
   ```bash
    http://127.0.0.1:5000/
    ```

4. The web interface will display the webcam feed and detected sign language gestures.






