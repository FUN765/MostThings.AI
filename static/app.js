function showTab(tab) {
    ["video", "image", "chat"].forEach(name => {
        document.getElementById(name).hidden = name !== tab;
    });
}

async function sendRequest(url, data) {
    const response = await fetch(url, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(data)
    });

    const result = await response.json();

    if (!response.ok) {
        throw new Error(result.error || "Request failed");
    }

    return result;
}

async function makeImage() {
    const prompt = document.getElementById("imagePrompt").value;

    try {
        const result = await sendRequest("/generate-image", {
            prompt: prompt
        });

        document.getElementById("imageResult").innerHTML =
            `<img src="${result.image}" alt="Generated image">`;

    } catch(error) {
        alert(error.message);
    }
}

async function makeVideo() {
    const prompt = document.getElementById("videoPrompt").value;
    const duration = document.getElementById("duration").value;

    try {
        const image = await sendRequest("/generate-image", {
            prompt: prompt
        });

        document.getElementById("videoResult").innerHTML =
            "<p>Image created! Rendering video...</p>";

        const video = await sendRequest("/generate-video", {
            filename: image.filename,
            duration: duration
        });

        document.getElementById("videoResult").innerHTML = `
            <video controls autoplay loop src="${video.video}"></video>
            <p><a href="${video.video}" download="${video.filename}">
                Download Video
            </a></p>
        `;

    } catch(error) {
        alert(error.message);
    }
}

async function askAI() {
    const input = document.getElementById("question");
    const question = input.value.trim();

    if (!question) return;

    addMessage("You: " + question);
    input.value = "";

    try {
        const result = await sendRequest("/chat", {
            message: question
        });

        addMessage("AI: " + result.answer);

    } catch(error) {
        addMessage("AI: " + error.message);
    }
}

function addMessage(message) {
    const p = document.createElement("p");
    p.textContent = message;
    document.getElementById("messages").appendChild(p);
}

async function clearMemory() {
    try {
        await sendRequest("/clear-memory", {});
        document.getElementById("messages").innerHTML = "";
        addMessage("AI: Memory cleared.");
    } catch(error) {
        alert(error.message);
    }
}
