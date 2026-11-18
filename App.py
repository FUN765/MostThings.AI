import os
import uuid
import sqlite3
import base64

from pathlib import Path
from flask import (
    Flask, render_template, request,
    jsonify, send_from_directory, session
)
from dotenv import load_dotenv
from openai import OpenAI
from PIL import Image, ImageOps
import imageio_ffmpeg

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "change-this-secret")

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

BASE = Path(__file__).parent
OUTPUT = BASE / "generated"
OUTPUT.mkdir(exist_ok=True)

DATABASE = BASE / "memory.db"

CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-6-luna")
IMAGE_MODEL = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-2.5-sunburst")


# DATABASE / AI MEMORY

def connect_db():
    return sqlite3.connect(DATABASE)


def initialize_database():
    with connect_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                role TEXT,
                message TEXT
            )
        """)


def remember(user_id, role, message):
    with connect_db() as db:
        db.execute(
            "INSERT INTO messages (user_id, role, message) VALUES (?, ?, ?)",
            (user_id, role, message)
        )


def get_memory(user_id):
    with connect_db() as db:
        rows = db.execute(
            """
            SELECT role, message FROM messages
            WHERE user_id = ?
            ORDER BY id DESC LIMIT 12
            """,
            (user_id,)
        ).fetchall()

    return [
        {"role": role, "content": message}
        for role, message in reversed(rows)
    ]


# HOME PAGE

@app.route("/")
def home():
    return render_template("index.html")


# AI CHATBOT

@app.route("/chat", methods=["POST"])
def chat():

    data = request.json
    question = data.get("message", "").strip()

    if not question:
        return jsonify({"error": "Enter a message."}), 400

    if len(question) > 4000:
        return jsonify({"error": "Message is too long."}), 400

    if "user_id" not in session:
        session["user_id"] = str(uuid.uuid4())

    user_id = session["user_id"]

    try:
        history = get_memory(user_id)

        response = client.responses.create(
            model=CHAT_MODEL,
            instructions=(
                "You are AI Video Studio, a helpful creative AI. "
                "Help users with video ideas, image prompts, "
                "editing advice and general questions."
            ),
            input=history + [
                {"role": "user", "content": question}
            ]
        )

        answer = response.output_text

        remember(user_id, "user", question)
        remember(user_id, "assistant", answer)

        return jsonify({"answer": answer})

    except Exception as error:
        return jsonify({"error": str(error)}), 500


# CLEAR MEMORY

@app.route("/clear-memory", methods=["POST"])
def clear_memory():

    user_id = session.get("user_id")

    if user_id:
        with connect_db() as db:
            db.execute(
                "DELETE FROM messages WHERE user_id = ?",
                (user_id,)
            )

    return jsonify({"success": True})


# IMAGE GENERATOR

@app.route("/generate-image", methods=["POST"])
def generate_image():

    prompt = request.json.get("prompt", "").strip()

    if not prompt:
        return jsonify({"error": "Enter an image prompt."}), 400

    if len(prompt) > 2000:
        return jsonify({"error": "Prompt is too long."}), 400

    try:
        result = client.images.generate(
            model=IMAGE_MODEL,
            prompt=prompt
        )

        image_data = result.data[0].b64_json

        if not image_data:
            raise ValueError("No image was returned.")

        image_bytes = base64.b64decode(image_data)

        filename = uuid.uuid4().hex + ".png"

        (OUTPUT / filename).write_bytes(image_bytes)

        return jsonify({
            "image": "/generated/" + filename,
            "filename": filename
        })

    except Exception as error:
        return jsonify({"error": str(error)}), 500


# IMAGE TO VIDEO GENERATOR

@app.route("/generate-video", methods=["POST"])
def generate_video():

    data = request.json

    filename = Path(data.get("filename", "")).name

    duration = int(data.get("duration", 5))

    if duration < 3 or duration > 10:
        return jsonify({"error": "Duration must be 3-10 seconds."}), 400

    image_path = OUTPUT / filename

    if not image_path.is_file() or image_path.suffix != ".png":
        return jsonify({"error": "Generate an image first."}), 400

    try:
        video_name = uuid.uuid4().hex + ".mp4"
        video_path = OUTPUT / video_name

        create_video(image_path, video_path, duration)

        return jsonify({
            "video": "/generated/" + video_name,
            "filename": video_name
        })

    except Exception as error:
        return jsonify({"error": str(error)}), 500


def create_video(image_path, video_path, duration):

    width = 1280
    height = 720
    fps = 24

    with Image.open(image_path) as original:
        image = ImageOps.fit(
            original.convert("RGB"),
            (width, height),
            method=Image.Resampling.LANCZOS
        )

    writer = imageio_ffmpeg.write_frames(
        str(video_path),
        (width, height),
        fps=fps,
        codec="libx264",
        pix_fmt_out="yuv420p",
        quality=8
    )

    writer.send(None)

    try:
        total_frames = duration * fps

        for frame in range(total_frames):

            progress = frame / max(total_frames - 1, 1)

            zoom = 1 + (0.10 * progress)

            crop_width = int(width / zoom)
            crop_height = int(height / zoom)

            left = (width - crop_width) // 2
            top = (height - crop_height) // 2

            current = image.crop((
                left,
                top,
                left + crop_width,
                top + crop_height
            ))

            current = current.resize(
                (width, height),
                Image.Resampling.LANCZOS
            )

            writer.send(current.tobytes())

    finally:
        writer.close()


# DISPLAY GENERATED FILES

@app.route("/generated/<path:filename>")
def generated(filename):
    return send_from_directory(OUTPUT, filename)


# START WEBSITE

initialize_database()

if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )
